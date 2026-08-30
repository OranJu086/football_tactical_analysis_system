import matplotlib
matplotlib.use('Agg')  # 无界面渲染后端，保证 headless/服务器环境也能运行

import matplotlib.pyplot as plt
import os

from src.data_loader.statsbomb_loader import load_events, load_matches
from src.preprocessing.event_cleaner import clean_pass_events
from src.analysis.pass_network import build_pass_network
from src.analysis.shot_map import extract_shots
from src.analysis.heatmap import extract_positions
from src.visualization.pitch import create_pitch
from src.visualization.plot_utils import draw_pass_network
from src.visualization.shot_plot import draw_shot_map
from src.visualization.heatmap_plot import draw_heatmap
from src.utils.config import (
    DATA_PATH, MATCHES_PATH, TEAM_NAME,
    FIGURES_DIR, REPORTS_DIR,
    PASS_NETWORK_PATH, SHOT_MAP_PATH, HEATMAP_PATH, REPORT_PATH,
)


def write_report(matches, avg_pos, edges, shots, team_name):
    """
    生成文字版比赛分析报告，写入 outputs/reports/match_analysis.txt
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    lines = []

    # 比赛信息
    if matches:
        m = matches[0]
        home = m['home_team']['home_team_name']
        away = m['away_team']['away_team_name']
        score = f"{m['home_score']} - {m['away_score']}"
        lines.append("=" * 50)
        lines.append(f"比赛: {home} {score} {away}")
        lines.append(f"日期: {m['match_date']}")
        lines.append(f"赛事: {m['competition']['competition_name']} "
                     f"{m['season']['season_name']}")
        lines.append(f"分析球队: {team_name}")
        lines.append("=" * 50)

    # 传球网络
    top = avg_pos.sort_values('pass_count', ascending=False).iloc[0]
    lines.append("\n【传球网络】")
    lines.append(f"参与传球球员数: {len(avg_pos)}")
    lines.append(f"传球关系(边)数: {len(edges)}")
    lines.append(f"传球最多: {top['player.name']} ({int(top['pass_count'])} 次)")
    lines.append("\n各球员传球次数:")
    for _, row in avg_pos.sort_values('pass_count', ascending=False).iterrows():
        lines.append(f"  {row['player.name']}: {int(row['pass_count'])}")

    # 射门
    goals = int(shots['is_goal'].sum())
    lines.append("\n【射门】")
    lines.append(f"射门次数: {len(shots)}")
    lines.append(f"进球数: {goals}")

    text = "\n".join(lines) + "\n"
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"[report] 已生成: {REPORT_PATH}")


def main():
    print("加载事件数据...")
    df = load_events(DATA_PATH)
    matches = load_matches(MATCHES_PATH)

    os.makedirs(FIGURES_DIR, exist_ok=True)

    # ========== 1. 传球网络 ==========
    print("分析传球网络...")
    passes = clean_pass_events(df)
    avg_pos, edges = build_pass_network(passes, TEAM_NAME)

    pitch, fig, ax = create_pitch()
    draw_pass_network(pitch, ax, avg_pos, edges)
    plt.savefig(PASS_NETWORK_PATH, dpi=300)
    plt.close()
    print(f"  [ok] {PASS_NETWORK_PATH}")

    # ========== 2. 射门分布 ==========
    print("分析射门分布...")
    shots = extract_shots(df, TEAM_NAME)
    pitch, fig, ax = create_pitch()
    draw_shot_map(pitch, ax, shots)
    plt.savefig(SHOT_MAP_PATH, dpi=300)
    plt.close()
    print(f"  [ok] {SHOT_MAP_PATH}")

    # ========== 3. 活动热力图 ==========
    print("生成活动热力图...")
    events = extract_positions(df, TEAM_NAME)
    pitch, fig, ax = create_pitch()
    draw_heatmap(pitch, ax, events)
    plt.savefig(HEATMAP_PATH, dpi=300)
    plt.close()
    print(f"  [ok] {HEATMAP_PATH}")

    # ========== 4. 文字报告 ==========
    write_report(matches, avg_pos, edges, shots, TEAM_NAME)

    print("\n全部完成！")


if __name__ == '__main__':
    main()
