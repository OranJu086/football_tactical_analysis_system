"""可复用的分析管线：加载数据、构建传球网络/射门/热力图、生成报告。

返回内存中的 matplotlib Figure 与报告文本，不写磁盘，
供 CLI（main.py）与网页（web_app.py）共用。
"""
from dataclasses import dataclass

import matplotlib
matplotlib.use('Agg')  # 无界面渲染后端，必须在导入 pyplot 前设置

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import pandas as pd

from src.data_loader.statsbomb_loader import load_events, load_matches
from src.preprocessing.event_cleaner import clean_pass_events
from src.analysis.pass_network import build_pass_network
from src.analysis.shot_map import extract_shots
from src.analysis.heatmap import extract_positions
from src.visualization.pitch import create_pitch
from src.visualization.plot_utils import draw_pass_network
from src.visualization.shot_plot import draw_shot_map
from src.visualization.heatmap_plot import draw_heatmap


@dataclass
class AnalysisResult:
    """一次分析的全部产物（内存态）。"""
    matches: list
    avg_pos: pd.DataFrame
    edges: pd.DataFrame
    shots: pd.DataFrame
    events: pd.DataFrame
    report_text: str
    pass_fig: Figure
    shot_fig: Figure
    heat_fig: Figure


def build_report(matches, avg_pos, edges, shots, team_name):
    """生成文字版比赛分析报告文本（不写文件）。"""
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

    return "\n".join(lines) + "\n"


def analyze_match(events_path, matches_path, team_name):
    """执行完整分析，返回 AnalysisResult（图与报告均在内存中）。"""
    df = load_events(events_path)
    matches = load_matches(matches_path)

    passes = clean_pass_events(df)
    avg_pos, edges = build_pass_network(passes, team_name)

    shots = extract_shots(df, team_name)
    events = extract_positions(df, team_name)

    # 传球网络图
    pitch, fig, ax = create_pitch()
    draw_pass_network(pitch, ax, avg_pos, edges)
    pass_fig = fig

    # 射门分布图
    pitch, fig, ax = create_pitch()
    draw_shot_map(pitch, ax, shots)
    shot_fig = fig

    # 活动热力图
    pitch, fig, ax = create_pitch()
    draw_heatmap(pitch, ax, events)
    heat_fig = fig

    report_text = build_report(matches, avg_pos, edges, shots, team_name)

    return AnalysisResult(
        matches=matches,
        avg_pos=avg_pos,
        edges=edges,
        shots=shots,
        events=events,
        report_text=report_text,
        pass_fig=pass_fig,
        shot_fig=shot_fig,
        heat_fig=heat_fig,
    )
