"""统计摘要层：把一场比赛的事件与元信息压缩成契约 Schema v2 的 summary JSON。

设计约定：
- 所有统计都基于 StatsBomb 事件数据的扁平化 DataFrame（pd.json_normalize 产物）。
- 传球口径统一走 src.preprocessing.event_cleaner.clean_pass_events 解析出的
  x / y / end_x / end_y，与本项目传球网络保持一致。
- 所有数值必须是原生 Python 类型（int / float / bool / str），保证 json.dumps 可用。
- 浮点指标统一 round(x, 1)；整数指标统一 int()。
"""
import pandas as pd

from src.preprocessing.event_cleaner import clean_pass_events

# 球门中心（StatsBomb 坐标，单位：码）
GOAL_CENTER = (120.0, 40.0)

# 禁区（18 码区）：x>=102 且 18<=y<=62（任务书口径）
BOX_X_MIN = 102.0
BOX_Y_MIN = 18.0
BOX_Y_MAX = 62.0

# 进攻三区：x>=80（任务书口径）
FINAL_THIRD_X = 80.0

# 长传阈值：pass.length >= 35 码（StatsBomb 常用长传定义，源码字段 pass.length 单位为码）
LONG_BALL_THRESHOLD = 35.0

# 左右中三分区边界：<26.7 左路，26.7~53.3 中路，>53.3 右路（任务书口径）
LEFT_Y_MAX = 26.7
RIGHT_Y_MIN = 53.3

# 射正归类：按实际打印 shot.outcome.name 的 unique() 取值，
# 3749552 = [nan,'Saved','Off T','Blocked','Wayward','Post']，
# 18245   = [nan,'Blocked','Off T','Saved','Post','Goal']。
# 归为射正的取值：Goal（进球）、Saved（被扑）、Post（中柱，即 Saved to Post）。
SHOT_ON_TARGET_OUTCOMES = {'Goal', 'Saved', 'Post'}

# 对抗成功归类：按实际打印 duel.outcome.name 的 unique() 取值，
# ['Success In Play','Lost Out','Lost In Play','Success Out','Won']。
# 归为成功的取值：Success In Play / Success Out / Won（Won 为空中对抗获胜）。
DUEL_WON_OUTCOMES = {'Success In Play', 'Success Out', 'Won'}

# 前场压迫类防守事件：按实际打印 type.name 的 unique() 取值选定
# Pressure / Ball Recovery / Interception / Duel / Block 均属于防守行为。
PRESS_TYPES = {'Pressure', 'Ball Recovery', 'Interception', 'Duel', 'Block'}

# 进攻事件类型：左右中占比只统计 Pass + Carry + Shot（任务书口径）
ATTACK_TYPES = {'Pass', 'Carry', 'Shot'}

# 非触球元事件：计算 touches 时剔除（换人/阵型/半场/伤停等不产生触球）
META_TYPES = {
    'Starting XI', 'Half Start', 'Half End', 'Tactical Shift',
    'Player On', 'Player Off', 'Substitution', 'Injury Stoppage',
}


def _r1(value):
    """四舍五入到 1 位小数并转成原生 float。"""
    return round(float(value), 1)


def _pct(numerator, denominator):
    """百分比：分子/分母*100，四舍五入 1 位小数；分母为 0 时返回 0.0。"""
    if not denominator:
        return 0.0
    return _r1(numerator / denominator * 100.0)


def _team_events(events_df, team_name):
    """本队全部事件。"""
    return events_df[events_df['team.name'] == team_name]


def _team_passes(events_df, team_name):
    """本队传球：复用 clean_pass_events 解析出 x/y/end_x/end_y 后按队伍过滤。

    来源字段：type.name == 'Pass'，起点 location，终点 pass.end_location。
    """
    passes = clean_pass_events(events_df)
    return passes[passes['team.name'] == team_name].copy()


def _possession_counts(events_df):
    """按 possession 字段去重后，用 possession_team.name 计数双方控球次数。

    任务书口径：优先用 possession 字段按 possession_team 去重计数。
    来源字段：possession（控球序号）、possession_team.name（控球方）。
    """
    # 每个 possession 序号代表一段连续控球，去重后按控球方统计
    poss = events_df.drop_duplicates(subset=['possession'])
    counts = poss['possession_team.name'].value_counts()
    return counts


def _parse_location(value):
    """把 location 列表解析为 (x, y)；非法值返回 (None, None)。"""
    if isinstance(value, list) and len(value) >= 2:
        return float(value[0]), float(value[1])
    return None, None


def _parse_end_location(value):
    """把 pass.end_location / carry.end_location 列表解析为 (x, y)。"""
    return _parse_location(value)


def _in_box(x, y):
    """终点是否落入禁区：x>=102 且 18<=y<=62（任务书口径）。"""
    if x is None or y is None:
        return False
    return x >= BOX_X_MIN and BOX_Y_MIN <= y <= BOX_Y_MAX


def _team_shots(events_df, team_name):
    """本队射门事件（type.name == 'Shot'），并附带起点 x/y 与射门距离。

    射门距离 = 射门点 (x,y) 到球门中心 (120,40) 的欧氏距离（任务书口径）。
    """
    shots = _team_events(events_df, team_name)
    shots = shots[shots['type.name'] == 'Shot'].copy()
    xy = shots['location'].apply(_parse_location)
    shots['_x'] = xy.apply(lambda t: t[0])
    shots['_y'] = xy.apply(lambda t: t[1])
    shots['_distance'] = (
        (shots['_x'] - GOAL_CENTER[0]) ** 2
        + (shots['_y'] - GOAL_CENTER[1]) ** 2
    ) ** 0.5
    shots['_is_goal'] = shots['shot.outcome.name'] == 'Goal'
    shots['_on_target'] = shots['shot.outcome.name'].isin(SHOT_ON_TARGET_OUTCOMES)
    return shots


def _team_stats(events_df, team_name):
    """计算 team / opponent_team 结构的全部指标。

    返回 dict：goals / shots / shots_on_target / passes / passes_completed /
    pass_accuracy_pct / possessions / possession_share_pct /
    final_third_passes / box_entries / pass_edges。
    """
    team_events = _team_events(events_df, team_name)
    passes = _team_passes(events_df, team_name)
    shots = _team_shots(events_df, team_name)

    # 传球成功 = pass.outcome.name 为空（NaN）；来源字段 pass.outcome.name
    passes_total = len(passes)
    passes_completed = int(passes['pass.outcome.name'].isna().sum())

    # 控球次数：possession 去重后本队控球段数；份额 = 本队 / 双方总和 * 100
    poss_counts = _possession_counts(events_df)
    team_possessions = int(poss_counts.get(team_name, 0))
    total_possessions = int(poss_counts.sum())
    possession_share_pct = _pct(team_possessions, total_possessions)

    # 进攻三区传球：传球终点 end_x >= 80（clean_pass_events 产出的 end_x）
    final_third_passes = int((passes['end_x'] >= FINAL_THIRD_X).sum())

    # box_entries：本队 Pass 终点 + Carry 终点落入禁区（x>=102 且 18<=y<=62）
    pass_end = passes['pass.end_location'].apply(_parse_end_location)
    pass_in_box = pass_end.apply(lambda t: _in_box(t[0], t[1]))
    carries = team_events[team_events['type.name'] == 'Carry'].copy()
    carry_end = carries['carry.end_location'].apply(_parse_end_location)
    carry_in_box = carry_end.apply(lambda t: _in_box(t[0], t[1]))
    box_entries = int(pass_in_box.sum() + carry_in_box.sum())

    # 传球网络边数：本队传球中不同的 (player.name, pass.recipient.name) 组合数
    pass_edges = int(
        passes.dropna(subset=['player.name', 'pass.recipient.name'])
        .groupby(['player.name', 'pass.recipient.name'])
        .ngroups
    )

    return {
        'goals': int(shots['_is_goal'].sum()),
        'shots': int(len(shots)),
        'shots_on_target': int(shots['_on_target'].sum()),
        'passes': int(passes_total),
        'passes_completed': int(passes_completed),
        'pass_accuracy_pct': _pct(passes_completed, passes_total),
        'possessions': team_possessions,
        'possession_share_pct': possession_share_pct,
        'final_third_passes': final_third_passes,
        'box_entries': box_entries,
        'pass_edges': pass_edges,
    }


def _formation(events_df, team_name):
    """本队阵型：tactics.formation 的众数，格式化为 '4-3-3' 这类字符串。

    来源字段：tactics.formation（float，如 433.0 -> '4-3-3'）。
    """
    team_events = _team_events(events_df, team_name)
    formations = team_events['tactics.formation'].dropna()
    if formations.empty:
        return '未知'
    value = int(formations.mode().iloc[0])
    digits = str(value)
    if not digits.isdigit() or len(digits) < 2:
        return '未知'
    return '-'.join(digits)


def _player_pass_rows(events_df, team_name):
    """本队球员传球表：按传球数降序（与现有报告"各球员传球次数"同一顺序）。

    每行字段：name / passes / pass_accuracy_pct / avg_x / avg_y /
    shots / goals / key_passes。
    - passes = 该球员 clean_pass_events 后的传球数（含成功与失败）
    - pass_accuracy_pct = 成功传球 / 总传球 * 100（成功 = pass.outcome.name 为 NaN）
    - avg_x / avg_y = 传球起点 x / y 均值
    - shots / goals = 该球员射门数 / 进球数
    - key_passes = pass.shot_assist 或 pass.goal_assist 为 True 的次数
      （3749552 无 pass.goal_assist 列，缺失列按 False 兜底）
    """
    passes = _team_passes(events_df, team_name).dropna(subset=['player.name'])
    shots = _team_shots(events_df, team_name).dropna(subset=['player.name'])
    events = _team_events(events_df, team_name).dropna(subset=['player.name'])

    # key_passes 来源字段：pass.shot_assist / pass.goal_assist；
    # pass.goal_assist 并非所有数据集都存在（3749552 缺失），缺失按 False 兜底
    shot_assist = (
        passes['pass.shot_assist'].fillna(False).astype(bool)
        if 'pass.shot_assist' in passes.columns
        else pd.Series(False, index=passes.index)
    )
    goal_assist = (
        passes['pass.goal_assist'].fillna(False).astype(bool)
        if 'pass.goal_assist' in passes.columns
        else pd.Series(False, index=passes.index)
    )
    passes['_key_pass'] = shot_assist | goal_assist

    # 触球 = 本队该球员的非元事件数（口径见 META_TYPES 注释）
    touch_events = events[~events['type.name'].isin(META_TYPES)]

    rows = []
    grouped = passes.groupby('player.name', sort=False)
    for name, group in grouped:
        total = len(group)
        completed = int(group['pass.outcome.name'].isna().sum())
        player_shots = shots[shots['player.name'] == name]
        player_events = touch_events[touch_events['player.name'] == name]

        rows.append({
            'name': str(name),
            'passes': int(total),
            'pass_accuracy_pct': _pct(completed, total),
            'avg_x': _r1(group['x'].mean()),
            'avg_y': _r1(group['y'].mean()),
            'shots': int(len(player_shots)),
            'goals': int(player_shots['_is_goal'].sum()),
            'key_passes': int(group['_key_pass'].sum()),
            '_touches': int(len(player_events)),
            '_duels_won': _player_duels_won(events, name),
            '_interceptions': _player_interceptions(events, name),
            '_network_degree': _network_degree(passes, name),
        })

    rows.sort(key=lambda r: (-r['passes'], r['name']))
    return rows, passes


def _player_duels_won(team_events, name):
    """该球员对抗成功次数：type.name == 'Duel' 且
    duel.outcome.name ∈ {Success In Play, Success Out, Won}。
    """
    duels = team_events[
        (team_events['player.name'] == name)
        & (team_events['type.name'] == 'Duel')
    ]
    if duels.empty or 'duel.outcome.name' not in duels.columns:
        return 0
    return int(duels['duel.outcome.name'].isin(DUEL_WON_OUTCOMES).sum())


def _player_interceptions(team_events, name):
    """该球员拦截次数：type.name == 'Interception' 的事件数。"""
    interceptions = team_events[
        (team_events['player.name'] == name)
        & (team_events['type.name'] == 'Interception')
    ]
    return int(len(interceptions))


def _network_degree(passes, name):
    """该球员传球网络度数：在传球边（player.name <-> pass.recipient.name，双向）
    中连接的不同队友数，即"传出对象 ∪ 接球来源"的去重人数。
    """
    edges = passes.dropna(subset=['player.name', 'pass.recipient.name'])
    sent = set(edges[edges['player.name'] == name]['pass.recipient.name'])
    received = set(edges[edges['pass.recipient.name'] == name]['player.name'])
    return len(sent | received)


def _core_players(rows):
    """core_players：综合分前 5 名。

    score = goals*5 + key_passes*3 + shots*1 + network_degree*0.5 + passes*0.05
    （任务书公式），四舍五入保留 1 位小数；并列时按传球数降序、再按姓名排序。
    """
    scored = []
    for r in rows:
        score = (
            r['goals'] * 5
            + r['key_passes'] * 3
            + r['shots'] * 1
            + r['_network_degree'] * 0.5
            + r['passes'] * 0.05
        )
        scored.append({
            'name': r['name'],
            'score': _r1(score),
            'passes': r['passes'],
            'pass_accuracy_pct': r['pass_accuracy_pct'],
            'key_passes': r['key_passes'],
            'shots': r['shots'],
            'goals': r['goals'],
            'touches': r['_touches'],
            'network_degree': r['_network_degree'],
            'duels_won': r['_duels_won'],
            'interceptions': r['_interceptions'],
        })
    scored.sort(key=lambda r: (-r['score'], -r['passes'], r['name']))
    return scored[:5]


def _public_player_rows(rows):
    """players 列表：只保留契约字段，顺序即传球数降序（rows 已排序）。"""
    return [
        {
            'name': r['name'],
            'passes': r['passes'],
            'pass_accuracy_pct': r['pass_accuracy_pct'],
            'avg_x': r['avg_x'],
            'avg_y': r['avg_y'],
            'shots': r['shots'],
            'goals': r['goals'],
            'key_passes': r['key_passes'],
        }
        for r in rows
    ]


def _shot_list(events_df, team_name):
    """shot_list：本队每脚射门一行。

    字段：minute（四舍五入为 int）、player、x、y（1 位小数）、
    outcome（shot.outcome.name，NaN 记为 'Unknown'）、is_goal（outcome == 'Goal'）。
    """
    shots = _team_shots(events_df, team_name)
    result = []
    for _, s in shots.iterrows():
        x, y = _parse_location(s['location'])
        minute = s.get('minute')
        outcome = s.get('shot.outcome.name')
        if not isinstance(outcome, str):
            outcome = 'Unknown'
        result.append({
            'minute': int(round(float(minute))) if pd.notna(minute) else 0,
            'player': str(s.get('player.name')) if pd.notna(s.get('player.name')) else '未知',
            'x': _r1(x) if x is not None else 0.0,
            'y': _r1(y) if y is not None else 0.0,
            'outcome': outcome,
            'is_goal': bool(outcome == 'Goal'),
        })
    return result


def _style(events_df, team_name, team_stats):
    """style 结构。

    - formation = tactics.formation 众数格式化
    - avg_pass_length = 本队传球 pass.length 均值（clean_pass_events 后）
    - long_ball_ratio_pct = pass.length >= 35 码的传球占比 * 100
    - passes_per_possession = 本队传球数 / 本队控球次数
    - press_events_opp_third = 本队防守类事件（Pressure/Ball Recovery/
      Interception/Duel/Block）中起点 x >= 80 的次数
    """
    passes = _team_passes(events_df, team_name)
    team_events = _team_events(events_df, team_name)

    avg_pass_length = _r1(passes['pass.length'].mean()) if len(passes) else 0.0

    long_balls = int((passes['pass.length'] >= LONG_BALL_THRESHOLD).sum())
    long_ball_ratio_pct = _pct(long_balls, len(passes))

    possessions = team_stats['possessions']
    passes_per_possession = (
        _r1(team_stats['passes'] / possessions) if possessions else 0.0
    )

    press = team_events[team_events['type.name'].isin(PRESS_TYPES)]
    press_x = press['location'].apply(
        lambda v: _parse_location(v)[0]
    )
    press_events_opp_third = int((press_x >= FINAL_THIRD_X).sum())

    return {
        'formation': _formation(events_df, team_name),
        'avg_pass_length': avg_pass_length,
        'long_ball_ratio_pct': long_ball_ratio_pct,
        'passes_per_possession': passes_per_possession,
        'press_events_opp_third': press_events_opp_third,
    }


def _attack_preference(events_df, team_name):
    """attack_preference 结构。

    - 左/中/右占比：进攻事件（Pass + Carry + Shot）按起点 y 三分区
      <26.7 / 26.7~53.3 / >53.3；left_pct 与 center_pct 四舍五入 1 位小数，
      right_pct = 100 - left_pct - center_pct（保证三者和为 100.0）。
    - crosses = pass.cross 为 True 的次数；through_balls = pass.through_ball 为 True 的次数
    - avg_shot_distance = 射门点到 (120,40) 欧氏距离均值
    - shots_inside_box = 射门起点落入禁区（x>=102 且 18<=y<=62）的次数
    - shots_outside_box = 其余射门次数
    """
    team_events = _team_events(events_df, team_name)
    attack = team_events[team_events['type.name'].isin(ATTACK_TYPES)]
    y_values = attack['location'].apply(lambda v: _parse_location(v)[1]).dropna()

    total = len(y_values)
    left = int((y_values < LEFT_Y_MAX).sum())
    center = int(((y_values >= LEFT_Y_MAX) & (y_values <= RIGHT_Y_MIN)).sum())
    right = total - left - center

    left_pct = _pct(left, total)
    center_pct = _pct(center, total)
    right_pct = _r1(100.0 - left_pct - center_pct)

    passes = _team_passes(events_df, team_name)
    crosses = int(
        passes['pass.cross'].fillna(False).astype(bool).sum()
        if 'pass.cross' in passes.columns else 0
    )
    through_balls = int(
        passes['pass.through_ball'].fillna(False).astype(bool).sum()
        if 'pass.through_ball' in passes.columns else 0
    )

    shots = _team_shots(events_df, team_name)
    avg_shot_distance = _r1(shots['_distance'].mean()) if len(shots) else 0.0
    inside = shots.apply(
        lambda s: _in_box(s['_x'], s['_y']), axis=1
    )
    shots_inside_box = int(inside.sum())
    shots_outside_box = int(len(shots) - shots_inside_box)

    return {
        'left_pct': left_pct,
        'center_pct': center_pct,
        'right_pct': right_pct,
        'crosses': crosses,
        'through_balls': through_balls,
        'avg_shot_distance': avg_shot_distance,
        'shots_inside_box': shots_inside_box,
        'shots_outside_box': shots_outside_box,
    }


def build_match_summary(events_df, matches, team_name):
    """构建契约 Schema v2 的 summary JSON（原生 Python 类型，可直接 json.dumps）。

    team_name 在 events 中不存在时抛 ValueError（中文提示实际球队列表）。
    """
    # 球队存在性校验：team_name 必须出现在事件数据的 team.name 中
    actual_teams = events_df['team.name'].dropna().unique().tolist()
    if team_name not in actual_teams:
        raise ValueError(
            f"球队 '{team_name}' 不存在于本场事件数据中；"
            f"实际球队为: {actual_teams}"
        )

    # 比赛元信息：matches 为单元素列表（data_source 只保留本场）
    m = matches[0]
    home_team = m['home_team']['home_team_name']
    away_team = m['away_team']['away_team_name']
    opponent = away_team if team_name == home_team else home_team

    team_stats = _team_stats(events_df, team_name)
    opponent_stats = _team_stats(events_df, opponent)

    rows, _ = _player_pass_rows(events_df, team_name)

    summary = {
        'match': {
            'match_id': int(m['match_id']),
            'date': str(m['match_date']),
            'competition': str(m['competition']['competition_name']),
            'season': str(m['season']['season_name']),
            'home_team': str(home_team),
            'away_team': str(away_team),
            'home_score': int(m['home_score']),
            'away_score': int(m['away_score']),
        },
        'focus_team': str(team_name),
        'opponent': str(opponent),
        'team': team_stats,
        'opponent_team': opponent_stats,
        'style': _style(events_df, team_name, team_stats),
        'attack_preference': _attack_preference(events_df, team_name),
        'core_players': _core_players(rows),
        'players': _public_player_rows(rows),
        'shot_list': _shot_list(events_df, team_name),
    }
    return summary
