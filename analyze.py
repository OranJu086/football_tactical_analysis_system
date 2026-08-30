"""
交互式比赛分析入口：每次分析前执行。

流程:
    1. 输入要分析的球队名称
    2. （可选）输入赛事关键词过滤
    3. 显示该球队的比赛并编号，用户选择一场
    4. 自动下载该比赛数据并运行分析

用法:
    .venv/bin/python analyze.py
"""
import sys

from download_match import DEFAULT_TEAM, download_and_prepare
from list_matches import query_matches

PAGE_SIZE = 30


def ask_team():
    team = input(f"① 输入要分析的球队名称（回车默认 {DEFAULT_TEAM}）: ").strip()
    return team or DEFAULT_TEAM


def ask_competition():
    comp = input("② 输入赛事关键词过滤（如 La Liga / Champions League，回车=全部）: ").strip()
    return comp


def show_rows(rows, start, end):
    for i in range(start, end):
        date, mid, comp, season, game = rows[i]
        print(f"{i + 1:>4}. {mid:<10} {date:<12} {comp:<18} {game}")


def choose_match(rows):
    """显示编号列表并让用户选择，返回选中的行。"""
    total = len(rows)
    shown_all = False

    while True:
        if not shown_all:
            end = min(PAGE_SIZE, total)
            print(f"\n共找到 {total} 场比赛，先显示最近 {end} 场：")
            show_rows(rows, 0, end)
            if total > PAGE_SIZE:
                print(f"（输入 0 可查看全部 {total} 场）")
        else:
            print(f"\n全部 {total} 场比赛：")
            show_rows(rows, 0, total)

        choice = input("③ 请输入要分析的比赛编号: ").strip()

        if choice == '0' and not shown_all and total > PAGE_SIZE:
            shown_all = True
            continue

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= total:
                return rows[idx - 1]

        print(f"编号无效，请输入 1-{total} 之间的数字" + ("（或 0 显示全部）" if not shown_all and total > PAGE_SIZE else ""))


def main():
    print("=" * 60)
    print("  足球战术分析 - 比赛选择")
    print("=" * 60)

    team = ask_team()
    comp = ask_competition()

    rows = query_matches(team, comp)
    if not rows:
        print(f"\n没有找到 {team} 的比赛"
              + (f"（关键词 '{comp}'）" if comp else "")
              + "，请检查球队名拼写（如 Real Madrid / Manchester United）")
        sys.exit(1)

    chosen = choose_match(rows)
    date, mid, comp_name, season, game = chosen
    print(f"\n已选择: {game}（{date}，{comp_name} {season}）match_id = {mid}")

    print("\n" + "=" * 60)
    print("  下载比赛数据")
    print("=" * 60)
    download_and_prepare(int(mid), team)

    print("\n" + "=" * 60)
    print("  开始分析")
    print("=" * 60)
    import main as m
    m.main()

    print("\n✅ 分析完成！")
    print("   图表:   outputs/figures/")
    print("   报告:   outputs/reports/match_analysis.txt")
    print("   （用 open 命令或文件管理器打开查看）")


if __name__ == '__main__':
    main()
