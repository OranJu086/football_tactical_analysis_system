"""
列出某球队可用的 StatsBomb 比赛，直接拿到 match_id。

用法:
    .venv/bin/python list_matches.py [球队名] [赛事关键词] [数量限制]

示例:
    .venv/bin/python list_matches.py                  # 巴萨全部比赛
    .venv/bin/python list_matches.py Barcelona "La Liga" 30
    .venv/bin/python list_matches.py "Real Madrid"
"""
import sys

from download_match import build_index, load_index

DEFAULT_TEAM = 'Barcelona'


def query_matches(team, comp_kw='', limit=0):
    """
    查询某球队的比赛。
    返回列表，每个元素: (date, match_id, competition, season, "主队 x-y 客队")
    按日期从新到旧排序。
    """
    index = load_index()
    if not index:
        print("比赛索引为空，先构建（需要联网，首次较慢）...")
        index = build_index(index)

    rows = []
    for mid, m in index.items():
        if team.lower() not in (m['home'].lower(), m['away'].lower()):
            continue
        if comp_kw and comp_kw.lower() not in m['competition'].lower():
            continue
        score = f"{m['home_score']}-{m['away_score']}"
        rows.append((m['date'], mid, m['competition'], m['season'],
                     f"{m['home']} {score} {m['away']}"))

    rows.sort(reverse=True)  # 按日期从新到旧
    if limit > 0:
        rows = rows[:limit]
    return rows


def main():
    team = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEAM
    comp_kw = sys.argv[2] if len(sys.argv) > 2 else ''
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    rows = query_matches(team, comp_kw, limit)

    print(f"\n{team} 的比赛（{len(rows)} 场"
          + (f"，关键词 '{comp_kw}'" if comp_kw else "")
          + "）:")
    print(f"{'match_id':<10} {'日期':<12} {'赛事':<18} {'比赛'}")
    print("-" * 80)
    for date, mid, comp, season, game in rows:
        print(f"{mid:<10} {date:<12} {comp:<18} {game}")
    print("\n用法: .venv/bin/python download_match.py <match_id> [球队名]")


if __name__ == '__main__':
    main()
