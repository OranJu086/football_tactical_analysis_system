"""
一键下载指定 StatsBomb 比赛数据并切换到该场比赛。

用法:
    .venv/bin/python download_match.py <match_id> [球队名]

示例:
    .venv/bin/python download_match.py 3773497              # 默认球队 Barcelona
    .venv/bin/python download_match.py 3773497 "Real Madrid"

首次运行会扫描一次赛事目录并缓存到 match_index.json；
之后切换比赛基本秒开，无需再扫描。

下载完成后运行: .venv/bin/python main.py
"""
import json
import os
import sys
import time

from statsbombpy import public

from src.data_source import ensure_match_data

DEFAULT_TEAM = 'Barcelona'
INDEX_PATH = 'data/match_index.json'
MAX_RETRIES = 5


def _fetch(func, *args, **kwargs):
    """带重试的请求，跳过网络抖动导致的失败。"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == MAX_RETRIES:
                print(f"  (跳过: {args} 重试失败: {type(e).__name__})")
                return None
            time.sleep(min(2 ** attempt, 8))


def load_index():
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_index(index):
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=1)


def build_index(existing=None):
    """扫描所有赛事/赛季，建立 match_id -> 比赛信息 索引。"""
    index = existing or {}
    competitions = _fetch(public.competitions)
    if competitions is None:
        print("错误: 无法获取赛事列表，请检查网络后重试")
        sys.exit(1)

    n = 0
    for comp in competitions.values():
        comp_id = comp['competition_id']
        season_id = comp['season_id']
        matches = _fetch(public.matches, comp_id, season_id)
        if not matches:
            continue
        for mid, m in matches.items():
            mid = str(mid)
            if mid in index:
                continue
            index[mid] = {
                'competition_id': comp_id,
                'season_id': season_id,
                'competition': m.get('competition', {}).get('competition_name', ''),
                'season': m.get('season', {}).get('season_name', ''),
                'home': m['home_team']['home_team_name'],
                'away': m['away_team']['away_team_name'],
                'home_score': m['home_score'],
                'away_score': m['away_score'],
                'date': m['match_date'],
            }
            n += 1
    save_index(index)
    print(f"[索引] 已缓存 {len(index)} 场比赛（本次新增 {n} 场）")
    return index


def find_match(match_id):
    index = load_index()
    mid = str(match_id)
    if mid not in index:
        print("扫描赛事目录（首次较慢，之后会缓存）...")
        index = build_index(index)
    if mid not in index:
        return None
    return index[mid]


def download_and_prepare(match_id, team_name=None):
    """下载指定比赛数据到按 match_id 命名的缓存目录（不再改写任何源码）。"""
    team_name = team_name or DEFAULT_TEAM
    info = find_match(match_id)
    if info is None:
        print(f"错误: 比赛 {match_id} 不在 StatsBomb 开放数据中")
        sys.exit(1)

    print(f"找到: {info['home']} {info['home_score']} - "
          f"{info['away_score']} {info['away']} ({info['date']}, {info['competition']})")

    data = ensure_match_data(match_id, force=True)
    print(f"完成: {len(data.events_df)} 个事件已就绪")
    print(f"[提示] 分析球队: {team_name}（仅用于打印，不再写入配置文件）")
    return info


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    match_id = int(sys.argv[1])
    team_name = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_TEAM
    download_and_prepare(match_id, team_name)
    print("现在运行: .venv/bin/python main.py")


if __name__ == '__main__':
    main()
