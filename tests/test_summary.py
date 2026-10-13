"""summary 契约 Schema v2 的离线单元测试：全部用合成事件，不依赖缓存与网络。"""
import json

import pandas as pd
import pytest

from src.analysis.summary import build_match_summary


def _pass_event(eid, team, player, recipient, x, y, end, length,
                outcome=None, cross=False, through_ball=False,
                shot_assist=False, goal_assist=False, possession=1):
    """构造一个 Pass 事件 dict。outcome=None 表示传球成功（NaN）。"""
    return {
        'id': eid, 'index': eid, 'period': 1, 'timestamp': '00:00:00.000',
        'minute': 0, 'second': 0, 'possession': possession, 'duration': 0.0,
        'type': {'id': 30, 'name': 'Pass'},
        'possession_team': {'id': 1, 'name': team},
        'team': {'id': 1, 'name': team},
        'player': {'id': 1, 'name': player},
        'location': [float(x), float(y)],
        'tactics': {'formation': 433.0},
        'pass': {
            'end_location': [float(end[0]), float(end[1])],
            'length': float(length),
            'outcome': {'id': 9, 'name': outcome} if outcome else {'id': None, 'name': None},
            'recipient': {'id': 2, 'name': recipient},
            'type': {'id': None, 'name': None},
            'cross': cross,
            'through_ball': through_ball,
            'shot_assist': shot_assist,
            'goal_assist': goal_assist,
        },
        'shot': None, 'carry': None, 'duel': None,
    }


def _shot_event(eid, team, player, x, y, outcome, minute, possession=1):
    """构造一个 Shot 事件 dict。"""
    return {
        'id': eid, 'index': eid, 'period': 1, 'timestamp': '00:00:00.000',
        'minute': minute, 'second': 0, 'possession': possession, 'duration': 0.0,
        'type': {'id': 16, 'name': 'Shot'},
        'possession_team': {'id': 1, 'name': team},
        'team': {'id': 1, 'name': team},
        'player': {'id': 1, 'name': player},
        'location': [float(x), float(y)],
        'tactics': {'formation': 433.0},
        'pass': None,
        'shot': {'outcome': {'id': 1, 'name': outcome} if outcome else {'id': None, 'name': None}},
        'carry': None, 'duel': None,
    }


def _other_event(eid, team, player, type_name, x, y, possession=1,
                 carry_end=None, duel_outcome=None):
    """构造 Carry / Duel / Interception / Pressure 等非 Pass/Shot 事件。"""
    return {
        'id': eid, 'index': eid, 'period': 1, 'timestamp': '00:00:00.000',
        'minute': 0, 'second': 0, 'possession': possession, 'duration': 0.0,
        'type': {'id': 1, 'name': type_name},
        'possession_team': {'id': 1, 'name': team},
        'team': {'id': 1, 'name': team},
        'player': {'id': 1, 'name': player},
        'location': [float(x), float(y)],
        'tactics': {'formation': 433.0},
        'pass': None, 'shot': None,
        'carry': {'end_location': [float(carry_end[0]), float(carry_end[1])]}
        if carry_end else None,
        'duel': {'outcome': {'id': 1, 'name': duel_outcome}}
        if duel_outcome else None,
    }


@pytest.fixture
def fixture_data():
    """合成一场 TeamA vs TeamB，覆盖契约各统计口径的边界取值。"""
    events = []

    # ---- TeamA 传球：P1 2 次、P2 2 次、P3 1 次（覆盖成功/失败/长传/助攻）----
    events.append(_pass_event(1, 'TeamA', 'P1', 'P2', 40, 20, (100, 30), 20,
                              possession=1))
    events.append(_pass_event(2, 'TeamA', 'P1', 'P2', 60, 40, (110, 40), 40,
                              through_ball=True, shot_assist=True, possession=1))
    events.append(_pass_event(3, 'TeamA', 'P2', 'P1', 60, 60, (90, 20), 15,
                              outcome='Incomplete', cross=True,
                              goal_assist=True, possession=2))
    events.append(_pass_event(4, 'TeamA', 'P2', 'P1', 30, 40, (70, 30), 25,
                              possession=2))
    events.append(_pass_event(5, 'TeamA', 'P3', 'P1', 20, 50, (50, 40), 5,
                              outcome='Out', possession=2))

    # ---- TeamA 射门：覆盖 Goal/Saved/Post/Off T/Blocked/Wayward/NaN ----
    events.append(_shot_event(6, 'TeamA', 'P1', 110, 40, 'Goal', minute=10, possession=1))
    events.append(_shot_event(7, 'TeamA', 'P1', 100, 20, 'Saved', minute=20, possession=1))
    events.append(_shot_event(8, 'TeamA', 'P2', 110, 20, 'Post', minute=30, possession=2))
    events.append(_shot_event(9, 'TeamA', 'P2', 90, 60, 'Off T', minute=40, possession=2))
    events.append(_shot_event(10, 'TeamA', 'P2', 80, 40, 'Blocked', minute=50, possession=2))
    events.append(_shot_event(11, 'TeamA', 'P2', 70, 30, 'Wayward', minute=60, possession=2))
    events.append(_shot_event(12, 'TeamA', 'P3', 110, 40, None, minute=70, possession=2))

    # ---- TeamA Carry / Duel / Interception / Pressure ----
    events.append(_other_event(13, 'TeamA', 'P1', 'Carry', 30, 40,
                               possession=1, carry_end=(105, 40)))
    events.append(_other_event(14, 'TeamA', 'P3', 'Carry', 40, 40,
                               possession=2, carry_end=(50, 40)))
    events.append(_other_event(15, 'TeamA', 'P1', 'Duel', 60, 40,
                               possession=1, duel_outcome='Success In Play'))
    events.append(_other_event(16, 'TeamA', 'P1', 'Duel', 60, 40,
                               possession=1, duel_outcome='Lost Out'))
    events.append(_other_event(17, 'TeamA', 'P2', 'Duel', 60, 40,
                               possession=2, duel_outcome='Won'))
    events.append(_other_event(18, 'TeamA', 'P2', 'Duel', 60, 40,
                               possession=2, duel_outcome=None))
    events.append(_other_event(19, 'TeamA', 'P1', 'Interception', 85, 40, possession=1))
    events.append(_other_event(20, 'TeamA', 'P1', 'Pressure', 90, 30, possession=1))

    # ---- TeamB 事件（对手统计 + 控球份额分母）----
    events.append(_pass_event(21, 'TeamB', 'Q1', 'Q2', 20, 20, (40, 30), 10,
                              possession=3))
    events.append(_pass_event(22, 'TeamB', 'Q1', 'Q2', 30, 30, (50, 40), 20,
                              outcome='Incomplete', possession=3))

    matches = [{
        'match_id': 1,
        'match_date': '2020-01-01',
        'competition': {'competition_name': 'Test League'},
        'season': {'season_name': '2019/2020'},
        'home_team': {'home_team_name': 'TeamA'},
        'away_team': {'away_team_name': 'TeamB'},
        'home_score': 1,
        'away_score': 0,
    }]

    return pd.json_normalize(events), matches


def test_schema_keys_complete(fixture_data):
    """S1 键结构：顶层与各子结构的键名必须与契约 Schema v2 完全一致。"""
    events_df, matches = fixture_data
    summary = build_match_summary(events_df, matches, 'TeamA')

    assert set(summary.keys()) == {
        'match', 'focus_team', 'opponent', 'team', 'opponent_team',
        'style', 'attack_preference', 'core_players', 'players', 'shot_list',
    }
    assert set(summary['match'].keys()) == {
        'match_id', 'date', 'competition', 'season',
        'home_team', 'away_team', 'home_score', 'away_score',
    }
    team_keys = {
        'goals', 'shots', 'shots_on_target', 'passes', 'passes_completed',
        'pass_accuracy_pct', 'possessions', 'possession_share_pct',
        'final_third_passes', 'box_entries', 'pass_edges',
    }
    assert set(summary['team'].keys()) == team_keys
    assert set(summary['opponent_team'].keys()) == team_keys
    assert set(summary['style'].keys()) == {
        'formation', 'avg_pass_length', 'long_ball_ratio_pct',
        'passes_per_possession', 'press_events_opp_third',
    }
    assert set(summary['attack_preference'].keys()) == {
        'left_pct', 'center_pct', 'right_pct', 'crosses', 'through_balls',
        'avg_shot_distance', 'shots_inside_box', 'shots_outside_box',
    }
    assert set(summary['core_players'][0].keys()) == {
        'name', 'score', 'passes', 'pass_accuracy_pct', 'key_passes',
        'shots', 'goals', 'touches', 'network_degree', 'duels_won',
        'interceptions',
    }
    assert set(summary['players'][0].keys()) == {
        'name', 'passes', 'pass_accuracy_pct', 'avg_x', 'avg_y',
        'shots', 'goals', 'key_passes',
    }
    assert set(summary['shot_list'][0].keys()) == {
        'minute', 'player', 'x', 'y', 'outcome', 'is_goal',
    }


def test_shots_on_target_classification(fixture_data):
    """射正归类：Goal/Saved/Post 归为射正，其余（Off T/Blocked/Wayward/NaN）不计。"""
    events_df, matches = fixture_data
    summary = build_match_summary(events_df, matches, 'TeamA')

    assert summary['team']['shots'] == 7
    assert summary['team']['shots_on_target'] == 3
    assert summary['team']['goals'] == 1


def test_core_players_top5_and_score_formula(fixture_data):
    """core_players 取综合分前 5，score 公式逐项验证。"""
    events_df, matches = fixture_data
    summary = build_match_summary(events_df, matches, 'TeamA')

    core = summary['core_players']
    assert len(core) == 3  # 合成数据只有 3 名球员，应全部入选且不超过 5
    assert core[0]['name'] == 'P1'
    # P1: goals=1, key_passes=1, shots=2, network_degree=2, passes=2
    assert core[0]['score'] == pytest.approx(1 * 5 + 1 * 3 + 2 * 1 + 2 * 0.5 + 2 * 0.05)
    assert core[0]['passes'] == 2
    assert core[0]['network_degree'] == 2

    assert core[1]['name'] == 'P2'
    # P2: goals=0, key_passes=1, shots=4, network_degree=1, passes=2
    assert core[1]['score'] == pytest.approx(0 * 5 + 1 * 3 + 4 * 1 + 1 * 0.5 + 2 * 0.05)

    # 排序必须按 score 降序
    assert core[0]['score'] >= core[1]['score'] >= core[2]['score']


def test_left_center_right_sum_to_100(fixture_data):
    """左中右占比：left + center + right 必须等于 100.0。"""
    events_df, matches = fixture_data
    summary = build_match_summary(events_df, matches, 'TeamA')

    att = summary['attack_preference']
    total = round(att['left_pct'] + att['center_pct'] + att['right_pct'], 1)
    assert total == pytest.approx(100.0)
    assert att['right_pct'] == pytest.approx(round(100.0 - att['left_pct'] - att['center_pct'], 1))


def test_unknown_team_raises_value_error(fixture_data):
    """team_name 不在事件数据中时抛 ValueError，提示信息为中文并列出实际球队。"""
    events_df, matches = fixture_data
    with pytest.raises(ValueError, match='不存在'):
        build_match_summary(events_df, matches, 'TeamC')


def test_summary_is_json_serializable(fixture_data):
    """S6：json.dumps(summary) 不报错，证明所有数值均为原生 Python 类型。"""
    events_df, matches = fixture_data
    summary = build_match_summary(events_df, matches, 'TeamA')
    dumped = json.dumps(summary, ensure_ascii=False)
    assert isinstance(dumped, str)
    assert json.loads(dumped)['focus_team'] == 'TeamA'
