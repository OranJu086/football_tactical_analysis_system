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

from src.data_source import ensure_match_data
from src.preprocessing.event_cleaner import clean_pass_events
from src.analysis.pass_network import build_pass_network
from src.analysis.shot_map import extract_shots
from src.analysis.heatmap import extract_positions
from src.analysis.summary import build_match_summary
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
    summary: dict
    report_text: str
    pass_fig: Figure
    shot_fig: Figure
    heat_fig: Figure


def build_report(summary):
    """基于 summary 渲染文字版比赛分析报告文本（不写文件）。

    报告内容全部取自 summary，文本格式与旧版逐字一致。
    """
    lines = []

    # 比赛信息
    m = summary['match']
    lines.append("=" * 50)
    lines.append(f"比赛: {m['home_team']} {m['home_score']} - {m['away_score']} "
                 f"{m['away_team']}")
    lines.append(f"日期: {m['date']}")
    lines.append(f"赛事: {m['competition']} {m['season']}")
    lines.append(f"分析球队: {summary['focus_team']}")
    lines.append("=" * 50)

    # 传球网络
    players = summary['players']
    top = players[0]
    lines.append("\n【传球网络】")
    lines.append(f"参与传球球员数: {len(players)}")
    lines.append(f"传球关系(边)数: {summary['team']['pass_edges']}")
    lines.append(f"传球最多: {top['name']} ({int(top['passes'])} 次)")
    lines.append("\n各球员传球次数:")
    for p in players:
        lines.append(f"  {p['name']}: {int(p['passes'])}")

    # 射门
    lines.append("\n【射门】")
    lines.append(f"射门次数: {summary['team']['shots']}")
    lines.append(f"进球数: {summary['team']['goals']}")

    return "\n".join(lines) + "\n"


def analyze_match_from_frames(events_df, matches, team_name):
    """基于已持有的 DataFrame 与比赛元信息执行完整分析，返回 AnalysisResult。"""
    passes = clean_pass_events(events_df)
    avg_pos, edges = build_pass_network(passes, team_name)

    shots = extract_shots(events_df, team_name)
    events = extract_positions(events_df, team_name)

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

    summary = build_match_summary(events_df, matches, team_name)
    report_text = build_report(summary)

    return AnalysisResult(
        matches=matches,
        avg_pos=avg_pos,
        edges=edges,
        shots=shots,
        events=events,
        summary=summary,
        report_text=report_text,
        pass_fig=pass_fig,
        shot_fig=shot_fig,
        heat_fig=heat_fig,
    )


def analyze_match(match_id: int, team_name: str):
    """按 match_id 取数（缓存命中或回源下载）后执行完整分析。"""
    data = ensure_match_data(match_id)
    return analyze_match_from_frames(data.events_df, data.matches, team_name)
