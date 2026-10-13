"""离线自检脚本：校验 data/cache 下每场预置比赛七件套齐备且可构建摘要。

用法:
    .venv/bin/python scripts/smoke_test.py

行为:
    - 不访问网络、不调用 LLM、不读取 Key
    - 对 data/cache 下每个 match_id 子目录:
      读取 events/matches/lineups 三份 JSON -> build_match_summary 重建摘要
      -> 校验七件套（3 JSON + 3 PNG + summary.json + narrative.json）齐备
      -> 打印 PASS 或 FAIL（含原因）
    - 任意一场 FAIL 则进程退出码为 1，全部 PASS 为 0
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CACHE_DIR = Path(os.environ.get("FTAS_CACHE_DIR", str(PROJECT_ROOT / "data" / "cache")))

FIGURE_NAMES = ("pass_network", "shot_map", "heatmap")

SEVEN_ITEMS = [
    "events.json",
    "matches.json",
    "lineups.json",
    "summary.json",
    "narrative.json",
    "figures/pass_network.png",
    "figures/shot_map.png",
    "figures/heatmap.png",
]


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_seven(cache_dir):
    """校验七件套文件齐备且非空，返回 (是否齐备, 缺失列表)。"""
    missing = []
    for rel in SEVEN_ITEMS:
        path = cache_dir / rel
        if not path.is_file():
            missing.append(rel)
            continue
        if path.stat().st_size == 0:
            missing.append(f"{rel}(空文件)")
    return not missing, missing


def check_match(cache_dir):
    """对单场缓存做离线自检，返回 (PASS/FAIL, 详情)。"""
    match_id = cache_dir.name
    try:
        ok, missing = _check_seven(cache_dir)
        if not ok:
            return False, f"七件套缺失: {missing}"

        events = _read_json(cache_dir / "events.json")
        matches = _read_json(cache_dir / "matches.json")
        lineups = _read_json(cache_dir / "lineups.json")  # noqa: F841 - 只读校验可解析
        summary_disk = _read_json(cache_dir / "summary.json")
        narrative_disk = _read_json(cache_dir / "narrative.json")

        if not isinstance(events, list) or not events:
            return False, "events.json 为空或不是列表"
        if not isinstance(matches, list) or not matches:
            return False, "matches.json 为空或不是列表"

        team_name = summary_disk.get("focus_team") or matches[0]["home_team"]["home_team_name"]

        from src.analysis.summary import build_match_summary

        events_df = pd.json_normalize(events)
        summary = build_match_summary(events_df, matches, team_name)

        if not isinstance(summary, dict) or "focus_team" not in summary:
            return False, "build_match_summary 返回结果异常"
        if summary["focus_team"] != team_name:
            return False, f"focus_team 不一致: {summary['focus_team']} != {team_name}"

        narrative = narrative_disk.get("narrative") if isinstance(narrative_disk, dict) else None
        if not isinstance(narrative, str) or not narrative.strip():
            return False, "narrative.json 缺少非空 narrative 字段"

        home = summary["match"]["home_team"]
        away = summary["match"]["away_team"]
        score = f"{summary['match']['home_score']}-{summary['match']['away_score']}"
        return True, (
            f"{home} {score} {away}（focus={team_name}，"
            f"events={len(events)}，players={len(summary['players'])}）"
        )
    except Exception as exc:  # noqa: BLE001 - 自检应捕获所有异常并判 FAIL
        return False, f"{type(exc).__name__}: {exc}"


def main():
    if not CACHE_DIR.is_dir():
        print(f"FAIL 缓存目录不存在: {CACHE_DIR}")
        sys.exit(1)

    match_dirs = sorted(
        [p for p in CACHE_DIR.iterdir() if p.is_dir() and (p / "events.json").is_file()]
    )
    if not match_dirs:
        print(f"FAIL 未找到任何预置比赛（{CACHE_DIR} 下无含 events.json 的子目录）")
        sys.exit(1)

    failed = 0
    for cache_dir in match_dirs:
        ok, detail = check_match(cache_dir)
        if ok:
            print(f"PASS {cache_dir.name} | {detail}")
        else:
            failed += 1
            print(f"FAIL {cache_dir.name} | {detail}")

    print("-" * 60)
    print(f"共 {len(match_dirs)} 场: {len(match_dirs) - failed} PASS, {failed} FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
