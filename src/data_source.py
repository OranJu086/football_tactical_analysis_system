"""按 match_id 命名空间缓存的 StatsBomb 数据源。

重构目标：把"全局单场覆盖 + 改写源码"的取数方式，
改为"按 match_id 缓存、进程内无全局可变状态"。

- 缓存目录由环境变量 FTAS_CACHE_DIR 决定，默认 data/cache
- 每个 match_id 一个子目录，互不覆盖
- 回源下载用 requests 直连（显式超时），不调用 statsbombpy 的无超时接口
"""
import json
import os
import tempfile
from dataclasses import dataclass

import pandas as pd
import requests
from statsbombpy.public import OPEN_DATA_PATHS

# StatsBomb 开放数据的默认基址（OPEN_DATA_PATHS 中的模板均以此开头）
DEFAULT_DATA_BASE = 'https://raw.githubusercontent.com/statsbomb/open-data/master/data'

# 备用来源：国内服务器直连 raw.githubusercontent.com 会被重置，
# 因此默认按顺序尝试多个镜像（顺序与 scripts/prefetch.py 一致，均已实测可用）
JSDELIVR_BASE = 'https://fastly.jsdelivr.net/gh/statsbomb/open-data@master/data'
GITHUB_API_BASE = 'https://api.github.com/repos/statsbomb/open-data/contents/data'

# 显式设置 FTAS_STATSBOMB_BASE 时只使用该基址（便于测试超时或自建镜像）；
# 未设置时启用多来源回退
_ENV_DATA_BASE = os.environ.get('FTAS_STATSBOMB_BASE')
DATA_BASE = (_ENV_DATA_BASE or DEFAULT_DATA_BASE).rstrip('/')
USE_MIRRORS = _ENV_DATA_BASE is None

# 各类数据在仓库中的相对路径模板，取自 statsbombpy.public.OPEN_DATA_PATHS，
# 只取其路径部分，不依赖其无超时的请求实现
RELATIVE_TEMPLATES = {
    key: value.replace(f'{DEFAULT_DATA_BASE}/', '')
    for key, value in OPEN_DATA_PATHS.items()
}

# 缓存目录与下载索引路径（均由环境变量决定并带默认值）
CACHE_DIR = os.environ.get('FTAS_CACHE_DIR', 'data/cache')
MATCH_INDEX_PATH = os.environ.get('FTAS_MATCH_INDEX_PATH', 'data/match_index.json')

# 显式超时：连接 5 秒、读取 15 秒
REQUEST_TIMEOUT = (5, 15)


class DataSourceError(Exception):
    """数据源错误（下载失败、索引缺失等），信息包含 match_id 与 URL。"""


@dataclass
class MatchData:
    """一场比赛在内存中的完整数据。"""
    match_id: int
    events_df: pd.DataFrame
    matches: list
    lineups: list


def _match_cache_dir(match_id):
    """返回 match_id 对应的缓存子目录。"""
    return os.path.join(CACHE_DIR, str(match_id))


def _candidate_sources(kind, rel_path):
    """一类数据的候选来源，顺序即尝试顺序。

    lineups 走 jsdelivr 时常被拒（403），所以 GitHub API 优先；
    events / matches 相反，jsdelivr 更快。
    """
    raw_url = f'{DATA_BASE}/{rel_path}'
    if not USE_MIRRORS:
        return [('custom', raw_url)]

    jsdelivr_url = f'{JSDELIVR_BASE}/{rel_path}'
    github_api_url = f'{GITHUB_API_BASE}/{rel_path}'
    if kind == 'lineups':
        return [
            ('github_api', github_api_url),
            ('jsdelivr', jsdelivr_url),
            ('raw', raw_url),
        ]
    return [
        ('jsdelivr', jsdelivr_url),
        ('github_api', github_api_url),
        ('raw', raw_url),
    ]


def _try_get_json(source, url):
    """从单一来源下载并解析 JSON，失败抛 DataSourceError（含来源标签）。"""
    # GitHub contents 接口带该 Accept 头时直接返回文件原始内容
    headers = {'Accept': 'application/vnd.github.raw'} if source == 'github_api' else None
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise DataSourceError(f'[{source}] {type(exc).__name__}: {exc}') from exc
    except ValueError as exc:
        raise DataSourceError(f'[{source}] 响应不是合法 JSON: {exc}') from exc


def _fetch_kind(kind, match_id, meta):
    """下载一类数据：按候选来源依次尝试，全部失败才抛出。"""
    rel_path = RELATIVE_TEMPLATES[kind].format(
        match_id=match_id,
        competition_id=meta.get('competition_id'),
        season_id=meta.get('season_id'),
    )
    failures = []
    for source, url in _candidate_sources(kind, rel_path):
        try:
            return _try_get_json(source, url)
        except DataSourceError as exc:
            failures.append(str(exc))
    raise DataSourceError(
        f"下载失败 match_id={match_id} kind={kind}（已尝试 {len(failures)} 个来源）: "
        + '; '.join(failures)
    )


def _load_match_meta(match_id):
    """从 download_match 维护的索引中读取赛事/赛季信息（只读，不改写索引）。"""
    if not os.path.exists(MATCH_INDEX_PATH):
        raise DataSourceError(
            f"无法定位 match_id={match_id} 的赛事/赛季信息：缺少索引文件 "
            f"{MATCH_INDEX_PATH}，请先运行 download_match.py {match_id} 构建索引"
        )
    with open(MATCH_INDEX_PATH, 'r', encoding='utf-8') as f:
        index = json.load(f)
    meta = index.get(str(match_id))
    if meta is None:
        raise DataSourceError(
            f"无法定位 match_id={match_id} 的赛事/赛季信息：索引 "
            f"{MATCH_INDEX_PATH} 中不存在该比赛，请先运行 download_match.py {match_id}"
        )
    return meta


def _download_match(match_id, meta):
    """回源下载 events / matches / lineups，返回原始 JSON。"""
    events = _fetch_kind('events', match_id, meta)
    lineups = _fetch_kind('lineups', match_id, meta)
    all_matches = _fetch_kind('matches', match_id, meta)

    # matches 接口返回整个赛事赛季的比赛列表，这里只保留本场（与旧版单场覆盖行为一致）
    match = next(
        (m for m in all_matches if str(m.get('match_id')) == str(match_id)),
        None,
    )
    if match is None:
        raise DataSourceError(
            f"下载失败 match_id={match_id}: matches 响应中不存在该比赛"
        )

    return events, [match], lineups


def _atomic_write_json(path, data):
    """先写临时文件再原子替换，避免并发进程写坏同一文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix='.tmp-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _write_cache(match_id, events, matches, lineups):
    """把回源下载的结果写入 ${CACHE_DIR}/{match_id}/ 下三份 JSON。"""
    cache_dir = _match_cache_dir(match_id)
    os.makedirs(cache_dir, exist_ok=True)
    _atomic_write_json(os.path.join(cache_dir, 'events.json'), events)
    _atomic_write_json(os.path.join(cache_dir, 'matches.json'), matches)
    _atomic_write_json(os.path.join(cache_dir, 'lineups.json'), lineups)


def _read_cache(match_id):
    """命中缓存时读取三份 JSON 并还原为内存结构；缓存不全返回 None。"""
    cache_dir = _match_cache_dir(match_id)
    events_path = os.path.join(cache_dir, 'events.json')
    matches_path = os.path.join(cache_dir, 'matches.json')
    lineups_path = os.path.join(cache_dir, 'lineups.json')

    if not all(os.path.exists(p) for p in (events_path, matches_path, lineups_path)):
        return None

    with open(events_path, 'r', encoding='utf-8') as f:
        events = json.load(f)
    with open(matches_path, 'r', encoding='utf-8') as f:
        matches = json.load(f)
    with open(lineups_path, 'r', encoding='utf-8') as f:
        lineups = json.load(f)

    # 与现有 load_events 行为一致：json.load 后 pd.json_normalize 成 DataFrame
    events_df = pd.json_normalize(events)
    return events_df, matches, lineups


def ensure_match_data(match_id, force=False):
    """获取一场比赛的数据：命中缓存直接读，miss 回源下载并写缓存。"""
    match_id = int(match_id)

    if not force:
        cached = _read_cache(match_id)
        if cached is not None:
            events_df, matches, lineups = cached
            return MatchData(
                match_id=match_id,
                events_df=events_df,
                matches=matches,
                lineups=lineups,
            )

    # miss 或 force：回源下载（matches 接口需要索引里的赛事/赛季信息）
    meta = _load_match_meta(match_id)
    events, matches, lineups = _download_match(match_id, meta)
    _write_cache(match_id, events, matches, lineups)

    events_df = pd.json_normalize(events)
    print(f"[data_source] match_id={match_id} 已下载并缓存到 {_match_cache_dir(match_id)}")
    return MatchData(
        match_id=match_id,
        events_df=events_df,
        matches=matches,
        lineups=lineups,
    )
