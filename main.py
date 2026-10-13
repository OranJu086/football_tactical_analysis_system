"""命令行入口。

用法:
    .venv/bin/python main.py [match_id] [球队名]

无参数时从 data/raw/statsbomb/matches.json 推断 match_id，
兼容旧的"跑当前已下载比赛"体验。
"""
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')  # 无界面渲染后端，保证 headless/服务器环境也能运行

import matplotlib.pyplot as plt

from src.pipeline import analyze_match
from src.utils.config import (
    MATCHES_PATH,
    FIGURES_DIR, REPORTS_DIR,
    PASS_NETWORK_PATH, SHOT_MAP_PATH, HEATMAP_PATH, REPORT_PATH,
)

DEFAULT_TEAM = 'Manchester United'


def infer_match_id():
    """从旧版单场数据目录推断 match_id（仅用于无参数兼容入口）。"""
    if not os.path.exists(MATCHES_PATH):
        raise SystemExit(
            f"未找到 {MATCHES_PATH}，请先运行 "
            f".venv/bin/python download_match.py <match_id> 或直接传入 match_id"
        )
    with open(MATCHES_PATH, 'r', encoding='utf-8') as f:
        matches = json.load(f)
    if not matches:
        raise SystemExit(f"{MATCHES_PATH} 为空，请先下载比赛数据")
    match_id = matches[0].get('match_id')
    if match_id is None:
        raise SystemExit(f"{MATCHES_PATH} 中缺少 match_id 字段")
    match_id = int(match_id)
    print(f"[提示] 未指定 match_id，从 {MATCHES_PATH} 推断: {match_id}")
    return match_id


def save_result(result):
    """把 AnalysisResult 写入 outputs/ 下的图表与报告。"""
    os.makedirs(FIGURES_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    result.pass_fig.savefig(PASS_NETWORK_PATH, dpi=300)
    plt.close(result.pass_fig)
    print(f"  [ok] {PASS_NETWORK_PATH}")

    result.shot_fig.savefig(SHOT_MAP_PATH, dpi=300)
    plt.close(result.shot_fig)
    print(f"  [ok] {SHOT_MAP_PATH}")

    result.heat_fig.savefig(HEATMAP_PATH, dpi=300)
    plt.close(result.heat_fig)
    print(f"  [ok] {HEATMAP_PATH}")

    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(result.report_text)
    print(f"[report] 已生成: {REPORT_PATH}")


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv

    if args:
        match_id = int(args[0])
    else:
        match_id = infer_match_id()

    team_name = args[1] if len(args) > 1 else os.environ.get('FTAS_TEAM_NAME', DEFAULT_TEAM)
    if team_name == DEFAULT_TEAM:
        print(f"[提示] 未指定球队，使用默认球队: {DEFAULT_TEAM}"
              f"（可用命令行参数或环境变量 FTAS_TEAM_NAME 覆盖）")

    print(f"加载并分析 match_id={match_id}（球队: {team_name}）...")
    result = analyze_match(match_id, team_name)
    save_result(result)

    print("\n全部完成！")


if __name__ == '__main__':
    main()
