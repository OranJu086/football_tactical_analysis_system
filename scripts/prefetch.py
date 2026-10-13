"""预置演示比赛数据脚本。

用法:
    .venv/bin/python scripts/prefetch.py

目标:
    保证 data/cache/{match_id}/ 下每场演示比赛七件套齐备:
    events.json / matches.json / lineups.json /
    figures/{pass_network,shot_map,heatmap}.png / summary.json / narrative.json

数据获取顺序（每类文件独立尝试）:
    1. 本地缓存命中直接跳过
    2. fastly.jsdelivr 镜像（events/matches）
    3. api.github.com（lineups 或全部，raw media type）
    4. raw.githubusercontent.com（本机一般不通，兜底）

幂等约定:
    narrative.json 已存在则跳过生成，不重复调用 LLM、不重复扣费；
    summary 与三张图已存在时同样跳过，避免重复计算。
"""
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 让 matplotlib 使用项目内可写缓存目录，避免默认缓存目录不可写的告警
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".mplcache"))

import matplotlib

matplotlib.use("Agg")  # 无界面渲染后端，必须在导入 pyplot 前设置

import matplotlib.pyplot as plt

CACHE_DIR = Path(os.environ.get("FTAS_CACHE_DIR", str(PROJECT_ROOT / "data" / "cache")))
INDEX_PATH = Path(
    os.environ.get("FTAS_MATCH_INDEX_PATH", str(PROJECT_ROOT / "data" / "match_index.json"))
)

# 演示比赛清单: 前两场为必须场次，其后为可选热门场次
DEMO_MATCHES = [
    {"match_id": 3749552, "team_name": "Manchester United", "prompt": "分析战术风格"},
    {"match_id": 18245, "team_name": "Liverpool", "prompt": "分析战术风格"},
    {"match_id": 3773661, "team_name": "Barcelona", "prompt": "分析战术风格"},
]
REQUIRED_MATCH_IDS = {3749552, 18245}

FIGURE_NAMES = ("pass_network", "shot_map", "heatmap")

# 下载超时: 连接 30s / 读取 300s（events.json 约 3.5MB，走镜像较慢）
REQUEST_TIMEOUT = (30, 300)

JSDELIVR_BASE = "https://fastly.jsdelivr.net/gh/statsbomb/open-data@master/data"
GITHUB_API_BASE = "https://api.github.com/repos/statsbomb/open-data/contents/data"
RAW_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"


def _match_cache_dir(match_id):
    return CACHE_DIR / str(match_id)


def _seven_ready(cache_dir):
    """判断七件套是否全部齐备。"""
    required = [
        cache_dir / "events.json",
        cache_dir / "matches.json",
        cache_dir / "lineups.json",
        cache_dir / "summary.json",
        cache_dir / "narrative.json",
        cache_dir / "figures" / "pass_network.png",
        cache_dir / "figures" / "shot_map.png",
        cache_dir / "figures" / "heatmap.png",
    ]
    return all(p.is_file() and p.stat().st_size > 0 for p in required)


def _load_index():
    if not INDEX_PATH.is_file():
        return {}
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _atomic_write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _candidate_urls(kind, match_id, meta):
    """返回 (来源标签, URL) 候选列表，顺序即尝试顺序。"""
    if kind == "events":
        path = f"events/{match_id}.json"
        return [
            ("jsdelivr", f"{JSDELIVR_BASE}/{path}"),
            ("github_api", f"{GITHUB_API_BASE}/{path}"),
            ("raw", f"{RAW_BASE}/{path}"),
        ]
    if kind == "matches":
        path = f"matches/{meta['competition_id']}/{meta['season_id']}.json"
        return [
            ("jsdelivr", f"{JSDELIVR_BASE}/{path}"),
            ("github_api", f"{GITHUB_API_BASE}/{path}"),
            ("raw", f"{RAW_BASE}/{path}"),
        ]
    if kind == "lineups":
        path = f"lineups/{match_id}.json"
        return [
            ("github_api", f"{GITHUB_API_BASE}/{path}"),
            ("jsdelivr", f"{JSDELIVR_BASE}/{path}"),
            ("raw", f"{RAW_BASE}/{path}"),
        ]
    raise ValueError(f"未知数据类别: {kind}")


def _download_kind(kind, match_id, meta):
    """按候选顺序下载一类数据，返回 (数据, 来源标签)；全部失败返回 (None, None)。"""
    for source, url in _candidate_urls(kind, match_id, meta):
        headers = {"Accept": "application/vnd.github.raw"} if source == "github_api" else {}
        try:
            print(f"  [尝试] {kind} <- {source}: {url}")
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if kind == "matches":
                match = next(
                    (m for m in data if str(m.get("match_id")) == str(match_id)), None
                )
                if match is None:
                    raise ValueError("响应中不存在该比赛")
                data = [match]
            print(f"  [下载] {kind} <- {source} 成功 ({len(response.content)} bytes)")
            return data, source
        except Exception as exc:  # noqa: BLE001 - 逐个来源尝试，失败换下一个
            print(f"  [miss] {kind} <- {source} 失败: {type(exc).__name__}: {exc}")
    return None, None


def _ensure_data_files(match_id, meta):
    """确保三份原始数据 JSON 就绪；本地命中跳过，miss 逐类回源。"""
    cache_dir = _match_cache_dir(match_id)
    kinds = {
        "events": cache_dir / "events.json",
        "matches": cache_dir / "matches.json",
        "lineups": cache_dir / "lineups.json",
    }
    all_ok = True
    for kind, path in kinds.items():
        if path.is_file() and path.stat().st_size > 0:
            print(f"  [缓存] {kind}.json 已存在，跳过")
            continue
        data, source = _download_kind(kind, match_id, meta)
        if data is None:
            print(f"  [失败] {kind}.json 无法下载")
            all_ok = False
            continue
        _atomic_write_json(path, data)
    return all_ok


def _jsonable(value):
    """把 numpy/pandas 类型递归转成 JSON 可序列化的原生类型。"""
    import numpy as np

    if isinstance(value, dict):
        return {str(key): _jsonable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _ensure_analysis_artifacts(match_id, team_name, prompt):
    """生成 summary 与三张图（缺失时），再生成 narrative（已存在则跳过）。"""
    from src.pipeline import analyze_match

    cache_dir = _match_cache_dir(match_id)
    summary_path = cache_dir / "summary.json"
    figures_ready = all(
        (cache_dir / "figures" / f"{name}.png").is_file() for name in FIGURE_NAMES
    )

    if summary_path.is_file() and figures_ready:
        print("  [缓存] summary.json + 三张图已存在，跳过")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        result = analyze_match(match_id, team_name)
        summary = _jsonable(result.summary)
        _atomic_write_json(summary_path, summary)
        for name, fig in (
            ("pass_network", result.pass_fig),
            ("shot_map", result.shot_fig),
            ("heatmap", result.heat_fig),
        ):
            fig_path = cache_dir / "figures" / f"{name}.png"
            fig_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(fig_path, dpi=300)
            plt.close(fig)
            print(f"  [生成] {fig_path.relative_to(CACHE_DIR)}")

    narrative_path = cache_dir / "narrative.json"
    if narrative_path.is_file() and narrative_path.stat().st_size > 0:
        print("  [缓存] narrative.json 已存在，跳过（不扣费）")
        return True

    from src.llm.client import LLMUnavailable, analyze as llm_analyze

    try:
        narrative = llm_analyze(summary, prompt)
    except LLMUnavailable as exc:
        print(f"  [失败] narrative 生成失败: {exc}")
        return False

    narrative_data = {
        "narrative": narrative,
        "source": "prefetch",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_write_json(narrative_path, narrative_data)
    print("  [生成] narrative.json 已生成")
    return True


def prefetch_one(match_id, team_name, prompt):
    """预置单场比赛，返回是否七件套齐备。"""
    print(f"\n=== match_id={match_id}（{team_name}）===")
    cache_dir = _match_cache_dir(match_id)

    if _seven_ready(cache_dir):
        print("  [缓存] 七件套齐备，已存在，跳过")
        return True

    index = _load_index()
    meta = index.get(str(match_id))
    if meta is None:
        print(f"  [失败] 索引中不存在 match_id={match_id}，无法回源下载")
        return False
    home = meta.get("home", "")
    away = meta.get("away", "")
    print(f"  [信息] {home} {meta.get('home_score', 0)}-{meta.get('away_score', 0)} {away} "
          f"({meta.get('date', '')}, {meta.get('competition', '')})")

    if not _ensure_data_files(match_id, meta):
        return False
    return _ensure_analysis_artifacts(match_id, team_name, prompt)


def main():
    t0 = time.time()
    results = {}
    for item in DEMO_MATCHES:
        match_id = item["match_id"]
        ok = prefetch_one(match_id, item["team_name"], item["prompt"])
        results[match_id] = ok

    ready = [mid for mid, ok in results.items() if ok]
    failed = [mid for mid, ok in results.items() if not ok]
    missing_required = [mid for mid in REQUIRED_MATCH_IDS if not results.get(mid)]

    print("\n" + "=" * 60)
    print(f"[汇总] 就绪 {len(ready)}/{len(DEMO_MATCHES)} 场: {ready}")
    if failed:
        print(f"[汇总] 失败场次: {failed}")
    if missing_required:
        print(f"[汇总] 必须场次缺失: {missing_required}")
        print(f"[汇总] 耗时 {time.time() - t0:.1f}s，退出码 1")
        sys.exit(1)

    print(f"[汇总] 耗时 {time.time() - t0:.1f}s，全部必须场次就绪")
    sys.exit(0)


if __name__ == "__main__":
    main()
