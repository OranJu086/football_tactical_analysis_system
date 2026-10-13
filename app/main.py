"""FTAS FastAPI 服务。

运行时配置全部通过环境变量注入，示例见项目根目录 .env.example。
仅 /api/analyze 按 IP 限流；web/ 存在时把静态页挂载到根路径。
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic_settings import BaseSettings, SettingsConfigDict
from slowapi.errors import RateLimitExceeded

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 让 matplotlib 使用项目内可写缓存目录，避免默认缓存目录不可写的告警
os.environ.setdefault("MPLCONFIGDIR", str(_PROJECT_ROOT / ".mplcache"))


class Settings(BaseSettings):
    """应用运行时配置：字段名与 .env.example 中的键一一对应。"""

    app_port: int = 8000
    ftas_cache_dir: str = "data/cache"
    openai_base_url: str = "https://api.deepseek.com/v1"
    openai_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout: int = 60
    llm_max_retries: int = 3
    rate_limit_per_min: int = 60
    max_prompt_chars: int = 8000

    # 支持从 .env 读取，并忽略未定义的额外环境变量
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()

# 在导入数据层之前同步缓存目录，保证 src.data_source 与本服务使用同一目录
os.environ.setdefault("FTAS_CACHE_DIR", settings.ftas_cache_dir)

from download_match import INDEX_PATH, load_index  # noqa: E402
from src.data_source import DataSourceError  # noqa: E402
from src.llm.client import LLMUnavailable, analyze as llm_analyze  # noqa: E402
from src.llm.prompts import validate_output  # noqa: E402
from src.pipeline import analyze_match  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402

from app.limiter import limiter  # noqa: E402
from app.schemas import AnalyzeRequest  # noqa: E402
from app.team_matcher import TeamCatalog, normalize_name  # noqa: E402

# 图名白名单（与 REST 契约一致）
FIGURE_NAMES = ("pass_network", "shot_map", "heatmap")

# 输入框自动补全的限流额度：前端虽有 200ms 防抖，连续打字仍会密集请求，
# 因此这里比 /api/analyze 宽松得多，避免正常输入就把额度耗尽。
SUGGEST_RATE_LIMIT = "300/minute"

app = FastAPI(title="FTAS 健康检查服务")
app.state.limiter = limiter

# 前端静态资源与图片接口走 no-cache：浏览器每次向服务端确认一次，
# 内容没变时返回 304，改完前端代码或重跑分析后不会再看到旧文件。
_NO_CACHE_PATHS = {"/", "/index.html", "/app.js", "/style.css"}


@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    """给前端页面与图片加 no-cache 响应头，避免浏览器复用旧版本。"""
    response = await call_next(request)
    path = request.url.path
    if path in _NO_CACHE_PATHS or path.startswith("/api/figure/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


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


def _match_cache_dir(match_id: int) -> Path:
    """match_id 对应的缓存子目录。"""
    return Path(settings.ftas_cache_dir) / str(match_id)


def _figure_path(match_id: int, name: str) -> Path:
    """指定图名的 PNG 缓存路径。"""
    return _match_cache_dir(match_id) / "figures" / f"{name}.png"


def _analysis_payload(match_id, team_name, summary, narrative, source, t0):
    """构造 /api/analyze 的成功响应体。"""
    elapsed_ms = int((time.time() - t0) * 1000)
    return {
        "match_id": match_id,
        "team_name": team_name,
        "summary": _jsonable(summary),
        "figures": {
            "pass_network": f"/api/figure/{match_id}/pass_network.png",
            "shot_map": f"/api/figure/{match_id}/shot_map.png",
            "heatmap": f"/api/figure/{match_id}/heatmap.png",
        },
        "narrative": narrative,
        "narrative_source": source,
        "elapsed_ms": elapsed_ms,
    }


def _match_meta(match_id: int):
    """从比赛索引只读查询本场信息；索引缺失或查无此场返回 None。"""
    if not Path(INDEX_PATH).is_file():
        return None
    try:
        return load_index().get(str(match_id))
    except Exception:
        return None


# 球队目录缓存：索引有近 4000 场比赛，每次请求都重建太浪费；
# 用索引文件的 mtime + 大小判断是否需要重建。
_catalog_cache = None
_catalog_stamp = None


def _get_catalog():
    """返回与当前索引文件同步的球队目录；索引缺失或读取失败返回 None。"""
    global _catalog_cache, _catalog_stamp

    index_path = Path(INDEX_PATH)
    if not index_path.is_file():
        return None

    try:
        stat = index_path.stat()
        stamp = (stat.st_mtime_ns, stat.st_size)
        if _catalog_cache is None or _catalog_stamp != stamp:
            _catalog_cache = TeamCatalog(load_index())
            _catalog_stamp = stamp
    except Exception as exc:  # noqa: BLE001 - 索引损坏时降级为无候选
        print(f"警告: 构建球队目录失败: {exc}")
        return None

    return _catalog_cache


def _candidate_payload(candidate):
    """候选队名转成接口返回用的 dict。"""
    return {
        "name": candidate.name,
        "matches": candidate.matches,
        "score": candidate.score,
    }


def _read_cache_fallback(match_id, team_name, t0):
    """离线缓存兜底：summary + narrative + 三张图齐备才返回，否则 None。"""
    summary_path = _match_cache_dir(match_id) / "summary.json"
    narrative_path = _match_cache_dir(match_id) / "narrative.json"
    if not (summary_path.is_file() and narrative_path.is_file()):
        return None
    if not all(_figure_path(match_id, name).is_file() for name in FIGURE_NAMES):
        return None
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        narrative_data = json.loads(narrative_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    narrative = (
        narrative_data.get("narrative") if isinstance(narrative_data, dict) else None
    )
    if not isinstance(narrative, str) or not narrative.strip():
        return None
    return JSONResponse(
        content=_analysis_payload(match_id, team_name, summary, narrative, "cache", t0)
    )


def _preloaded_matches(limit=60):
    """列出已预置原始数据的比赛。

    服务器在国内无法访问 raw.githubusercontent.com，也没有可用镜像时，
    只有这里列出的比赛能真正跑出结果；分析失败时用它给出可操作的提示。
    """
    cache_root = Path(settings.ftas_cache_dir)
    if not cache_root.is_dir():
        return []

    items = []
    for entry in cache_root.iterdir():
        if not entry.is_dir():
            continue
        try:
            match_id = int(entry.name)
        except ValueError:
            continue
        if not all(
            (entry / name).is_file()
            for name in ("events.json", "matches.json", "lineups.json")
        ):
            continue
        meta = _match_meta(match_id) or {}
        home = str(meta.get("home", ""))
        away = str(meta.get("away", ""))
        date = str(meta.get("date", ""))
        competition = str(meta.get("competition", ""))
        label = (
            f"{date} | {competition} | "
            f"{home} {meta.get('home_score', '')}-{meta.get('away_score', '')} {away}"
            if home
            else str(match_id)
        )
        items.append({"match_id": match_id, "date": date, "label": label})

    items.sort(key=lambda item: (item["date"], item["match_id"]), reverse=True)
    return items[:limit]


def _data_unavailable_message(preloaded):
    """数据取不到且无缓存时，给前端一段能照着做的中文说明。"""
    if not preloaded:
        return (
            "该场比赛未预置数据，且服务器无法在线下载（演示环境未开通数据源访问）。"
            "请先预置比赛数据后再试。"
        )
    samples = "、".join(item["label"].split("|")[-1].strip() for item in preloaded[:5])
    return (
        "该场比赛未预置数据，且服务器无法在线下载（演示环境未开通数据源访问）。"
        f"当前可分析的比赛共 {len(preloaded)} 场，例如：{samples}。"
        "请从比赛下拉列表中选择这些已预置的比赛。"
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """把请求体/查询参数校验错误统一映射为 400。"""
    messages = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", []))
        msg = error.get("msg", "")
        messages.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(status_code=400, content={"detail": "参数非法: " + "; ".join(messages)})


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """限流命中统一返回 429 JSON。"""
    return JSONResponse(
        status_code=429,
        content={"detail": f"请求过于频繁，请稍后再试（限制 {exc.detail}）"},
    )


@app.get("/api/health")
def health():
    """返回服务健康状态与 LLM 配置状态。"""
    return {"status": "ok", "llm_configured": bool(settings.openai_api_key)}


@app.get("/api/teams")
@limiter.limit(SUGGEST_RATE_LIMIT)
def suggest_teams(
    request: Request,
    q: str = Query("", description="球队名片段，支持简称与拼写错误，可为空"),
    limit: int = Query(8, description="返回条数，默认 8、上限 50"),
):
    """返回候选队名，供输入框做自动补全；q 为空时返回热门球队。"""
    if limit < 1 or limit > 50:
        return JSONResponse(
            status_code=400, content={"detail": "参数非法: limit 必须在 1-50 之间"}
        )

    catalog = _get_catalog()
    if catalog is None:
        return JSONResponse(
            status_code=503, content={"detail": f"索引文件缺失: {INDEX_PATH}"}
        )

    candidates = catalog.search(q, limit=limit)
    return {
        "query": q.strip(),
        "count": len(candidates),
        "teams": [_candidate_payload(item) for item in candidates],
    }


@app.get("/api/matches")
@limiter.limit(f"{settings.rate_limit_per_min}/minute")
def list_matches(
    request: Request,
    team: str = Query(..., description="球队名（必填）"),
    competition: str | None = Query(None, description="赛事名（可选，大小写不敏感子串匹配）"),
    limit: int = Query(50, description="返回条数，默认 50、上限 200"),
):
    """按球队与可选赛事筛选比赛索引，按日期降序返回。

    球队名先经过模糊解析：与索引里的队名一致时直接用，输入简称或拼写有误差
    但能唯一定位某支球队时也直接用，定位不了则返回候选项交给前端提示，不瞎猜。
    """
    team = team.strip()
    if not team:
        return JSONResponse(status_code=400, content={"detail": "参数非法: team 为必填"})
    if limit < 1 or limit > 200:
        return JSONResponse(
            status_code=400, content={"detail": "参数非法: limit 必须在 1-200 之间"}
        )

    if not Path(INDEX_PATH).is_file():
        return JSONResponse(
            status_code=503, content={"detail": f"索引文件缺失: {INDEX_PATH}"}
        )

    try:
        index = load_index()
    except Exception as exc:
        return JSONResponse(status_code=503, content={"detail": f"索引读取失败: {exc}"})

    catalog = _get_catalog()
    if catalog is None:
        return JSONResponse(
            status_code=503, content={"detail": f"索引读取失败: {INDEX_PATH}"}
        )

    resolution = catalog.resolve(team)
    target_names = set(resolution.names)

    comp_lower = (competition or "").strip().lower()
    rows = []
    for mid, info in index.items():
        if not isinstance(info, dict):
            continue
        try:
            mid_int = int(mid)
        except (TypeError, ValueError):
            continue
        home = str(info.get("home", ""))
        away = str(info.get("away", ""))
        if home not in target_names and away not in target_names:
            continue
        comp = str(info.get("competition", ""))
        if comp_lower and comp_lower not in comp.lower():
            continue
        home_score = info.get("home_score", 0)
        away_score = info.get("away_score", 0)
        rows.append(
            {
                "match_id": mid_int,
                "date": str(info.get("date", "")),
                "competition": comp,
                "season": str(info.get("season", "")),
                "home": home,
                "away": away,
                "home_score": int(home_score) if home_score is not None else 0,
                "away_score": int(away_score) if away_score is not None else 0,
                "label": (
                    f"{info.get('date', '')} | {comp} | "
                    f"{home} {home_score}-{away_score} {away}"
                ),
            }
        )
    rows.sort(key=lambda row: (row["date"], row["match_id"]), reverse=True)
    matched = rows[:limit]

    payload = {
        "team": team,
        "resolved_team": resolution.name,
        "matched_by": resolution.matched_by,
        "count": len(rows),
        "matches": matched,
    }
    if not matched:
        # 一场都没找到时给出候选队名，前端提示「你是不是要找」
        payload["suggestions"] = [
            _candidate_payload(item) for item in resolution.candidates
        ]
    return payload


@app.post("/api/analyze")
@limiter.limit(f"{settings.rate_limit_per_min}/minute")
def analyze(request: Request, body: AnalyzeRequest):
    """执行单场战术分析，返回 summary、三张图 URL 与中文战术叙述。"""
    match_id = body.match_id
    team_name = body.team_name.strip()
    prompt = body.prompt.strip()

    # 参数校验 → 400
    if not team_name:
        return JSONResponse(status_code=400, content={"detail": "参数非法: team_name 不能为空"})
    if not prompt:
        return JSONResponse(status_code=400, content={"detail": "参数非法: prompt 不能为空"})
    if len(prompt) > settings.max_prompt_chars:
        return JSONResponse(
            status_code=400,
            content={"detail": f"参数非法: prompt 超过 {settings.max_prompt_chars} 字符"},
        )

    # 索引可用时先做球队存在性校验，不必加载数据即可返回 400
    meta = _match_meta(match_id)
    if meta is not None:
        home = str(meta.get("home", ""))
        away = str(meta.get("away", ""))
        # 允许大小写、重音、标点上的差异，但必须换回索引里的规范队名，
        # 否则后续按队名过滤事件会一条也匹配不到
        if normalize_name(team_name) == normalize_name(home):
            team_name = home
        elif normalize_name(team_name) == normalize_name(away):
            team_name = away
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": f"参数非法: 球队 '{team_name}' 不在本场比赛（{home} vs {away}）"
                },
            )

    t0 = time.time()

    try:
        result = analyze_match(match_id, team_name)
    except DataSourceError as exc:
        cached = _read_cache_fallback(match_id, team_name, t0)
        if cached is not None:
            return cached
        # 数据取不到且没有缓存：给出「哪些比赛能分析」的可操作提示，
        # 原始报错放在 reason 里保留诊断能力，不再直接抛给用户
        preloaded = _preloaded_matches()
        return JSONResponse(
            status_code=502,
            content={
                "detail": _data_unavailable_message(preloaded),
                "preloaded": preloaded,
                "reason": str(exc),
            },
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": f"参数非法: {exc}"})

    # 保存 summary 与三张图（dpi=300）；关闭 Figure 放在 finally，
    # 保证「写 summary 失败」这类异常路径（例如缓存目录属主不对）
    # 也不会把三张图泄漏在内存里
    figures = (
        ("pass_network", result.pass_fig),
        ("shot_map", result.shot_fig),
        ("heatmap", result.heat_fig),
    )
    try:
        _match_cache_dir(match_id).mkdir(parents=True, exist_ok=True)
        summary_path = _match_cache_dir(match_id) / "summary.json"
        summary_path.write_text(
            json.dumps(_jsonable(result.summary), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for name, fig in figures:
            _figure_path(match_id, name).parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(_figure_path(match_id, name), dpi=300)
    except Exception as exc:
        return JSONResponse(
            status_code=502, content={"detail": f"数据获取失败: 缓存产物写入失败: {exc}"}
        )
    finally:
        for _, fig in figures:
            plt.close(fig)

    summary = _jsonable(result.summary)

    # 调用模型生成中文战术叙述；失败或不合格先尝试离线缓存兜底
    try:
        narrative = llm_analyze(summary, prompt)
    except LLMUnavailable as exc:
        cached = _read_cache_fallback(match_id, team_name, t0)
        if cached is not None:
            return cached
        return JSONResponse(status_code=502, content={"detail": f"模型不可用: {exc}"})

    problems = validate_output(narrative, summary)
    if problems:
        # 追加一句纠错提示重新调用一次
        retry_prompt = (
            prompt
            + "\n\n注意：上次输出存在以下问题，请严格按五段结构并使用 JSON 中的数字逐项修正后重新输出：\n"
            + "\n".join(f"- {problem}" for problem in problems)
        )
        try:
            narrative = llm_analyze(summary, retry_prompt)
        except LLMUnavailable as exc:
            cached = _read_cache_fallback(match_id, team_name, t0)
            if cached is not None:
                return cached
            return JSONResponse(status_code=502, content={"detail": f"模型不可用: {exc}"})

        problems = validate_output(narrative, summary)
        if problems:
            cached = _read_cache_fallback(match_id, team_name, t0)
            if cached is not None:
                return cached
            return JSONResponse(
                status_code=502, content={"detail": f"模型输出不合格: {problems}"}
            )

    # 保存 live 叙述（保存失败不影响本次返回）
    narrative_data = {
        "narrative": narrative,
        "source": "live",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        narrative_path = _match_cache_dir(match_id) / "narrative.json"
        narrative_path.write_text(
            json.dumps(narrative_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        print(f"警告: 保存 narrative.json 失败: {exc}")

    return JSONResponse(
        content=_analysis_payload(match_id, team_name, summary, narrative, "live", t0)
    )


@app.get("/api/figure/{match_id}/{name}.png")
def get_figure(match_id: int, name: str):
    """返回已生成的 PNG 图；图名非法或文件不存在返回 404。"""
    if name not in FIGURE_NAMES:
        raise HTTPException(status_code=404, detail="文件不存在")
    path = _figure_path(match_id, name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, media_type="image/png", filename=f"{name}.png")


# 静态页：web/ 存在时挂载到根路径；不存在则跳过（API 不受影响）
_WEB_DIR = _PROJECT_ROOT / "web"
if _WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
else:
    print("警告: web/ 目录不存在，跳过静态页挂载（API 不受影响）")
