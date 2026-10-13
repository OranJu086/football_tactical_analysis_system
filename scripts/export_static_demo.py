"""导出「离线静态演示包」：答辩现场零网络、零后端、零安装的终极兜底。

用法:
    .venv/bin/python scripts/export_static_demo.py [输出目录]

产物（默认 demo_static/）:
    index.html                  自包含页面（内联 CSS/JS，比赛数据内联为 JSON）
    .ftas-demo-static           本工具生成的标记文件（用于安全清理旧产物）
    figures/{match_id}/*.png    三张图，按相对路径引用

特点:
    把 demo_static/ 整个目录拷进 U 盘，在任何有浏览器的电脑上双击 index.html
    即可完整演示：三张图 + 团队统计对比 + 核心球员表 + 中文战术分析。
    数据来自 data/cache 中已预生成的结果，因此不联网、不调用模型、不启动服务。
"""
import json
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = Path(os.environ.get("FTAS_CACHE_DIR", str(PROJECT_ROOT / "data" / "cache")))
DEFAULT_OUT_DIR = PROJECT_ROOT / "demo_static"

# 标记文件：只有本工具生成过的目录才允许被覆盖清理，避免误删用户目录
MARKER_NAME = ".ftas-demo-static"

FIGURE_NAMES = ("pass_network", "shot_map", "heatmap")

CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
     background:#f5f6f8;color:#1f2430;line-height:1.6}
header{background:#12263f;color:#fff;padding:18px 24px}
header h1{margin:0;font-size:20px}
header .sub{margin:4px 0 0;font-size:13px;opacity:.8}
main{max-width:1180px;margin:0 auto;padding:20px 16px 40px}
.picker{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px}
.picker button{padding:8px 12px;border:1px solid #c8d0dc;background:#fff;border-radius:6px;
     cursor:pointer;font-size:13px}
.picker button.active{background:#1a73e8;border-color:#1a73e8;color:#fff}
.head{display:flex;align-items:center;gap:12px;margin-bottom:8px}
.badge{background:#fff3cd;color:#7a5c00;border:1px solid #ffe08a;border-radius:4px;
     padding:3px 8px;font-size:12px}
.meta{font-size:13px;color:#5b6472}
h2{font-size:17px;margin:6px 0 14px}
h3{font-size:15px;margin:0 0 10px}
.figures{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:18px}
.figures figure{margin:0;flex:1 1 300px;background:#fff;border:1px solid #e2e6ee;
     border-radius:8px;padding:8px}
.figures figcaption{font-size:13px;color:#5b6472;margin-bottom:6px}
.figures img{width:100%;height:auto;display:block;border-radius:4px}
.panel{background:#fff;border:1px solid #e2e6ee;border-radius:8px;padding:14px 16px;margin-bottom:16px}
.narrative{white-space:pre-wrap;margin:0;font-size:14px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{border-bottom:1px solid #eef0f4;padding:7px 8px;text-align:left}
th{background:#f8f9fb;color:#3a4353;font-weight:600}
footer{max-width:1180px;margin:0 auto;padding:0 16px 40px;font-size:12px;color:#6b7280}
footer a{color:#1a73e8;text-decoration:none}
.disclaimer{color:#9aa1ad}
.hidden{display:none}
@media (max-width:860px){.figures figure{flex:1 1 100%}}
"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FTAS 离线演示包</title>
<style>@@CSS@@</style>
</head>
<body>
<header>
  <h1>⚽ FTAS 足球战术分析系统</h1>
  <p class="sub">离线静态演示包 · 结果已预生成 · 无需网络、无需后端</p>
</header>
<main>
  <div id="picker" class="picker"></div>
  <section id="result" class="hidden">
    <div class="head">
      <span class="badge">离线静态演示包（预生成结果）</span>
      <span id="meta" class="meta"></span>
    </div>
    <h2 id="title"></h2>
    <div class="figures">
      <figure><figcaption>传球网络</figcaption><img id="f1" alt="传球网络"></figure>
      <figure><figcaption>射门分布</figcaption><img id="f2" alt="射门分布"></figure>
      <figure><figcaption>活动热力图</figcaption><img id="f3" alt="活动热力图"></figure>
    </div>
    <section class="panel">
      <h3>📝 战术分析</h3>
      <p id="narrative" class="narrative"></p>
    </section>
    <section class="panel">
      <h3>📊 团队统计对比</h3>
      <table id="statTable">
        <thead><tr><th>指标</th><th id="thTeam"></th><th id="thOpp"></th></tr></thead>
        <tbody></tbody>
      </table>
    </section>
    <section class="panel">
      <h3>⭐ 核心球员（前 5）</h3>
      <table id="playerTable">
        <thead><tr>
          <th>姓名</th><th>综合分</th><th>传球</th><th>成功率</th>
          <th>关键传球</th><th>射门</th><th>进球</th><th>触球</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </section>
  </section>
</main>
<footer>
  <p>数据来源：StatsBomb ｜ StatsBomb Open Data ｜ CC BY-NC-SA 4.0</p>
  <p>仅供学习与技术演示，非商业用途</p>
  <p class="disclaimer">免责声明：分析结果不代表任何球队或数据提供方的官方观点</p>
</footer>
<script>
const DATA = @@DATA@@;
const STAT_ROWS = [
  ["进球", "goals"], ["射门", "shots"], ["射正", "shots_on_target"],
  ["传球", "passes"], ["传球成功率%", "pass_accuracy_pct"],
  ["控球次数", "possessions"], ["控球份额%", "possession_share_pct"],
  ["进攻三区传球", "final_third_passes"], ["禁区进入", "box_entries"],
  ["传球网络边数", "pass_edges"]
];
function el(id) { return document.getElementById(id); }
function cell(value) { return (value === undefined || value === null) ? "-" : String(value); }
function render(index) {
  const m = DATA.matches[index];
  const s = m.summary;
  const buttons = document.querySelectorAll(".picker button");
  for (let i = 0; i < buttons.length; i++) {
    buttons[i].classList.toggle("active", i === index);
  }
  el("result").classList.remove("hidden");
  el("title").textContent = m.label;
  el("meta").textContent = "分析视角：" + s.focus_team;
  el("f1").src = m.figures.pass_network;
  el("f2").src = m.figures.shot_map;
  el("f3").src = m.figures.heatmap;
  el("narrative").textContent = m.narrative;
  el("thTeam").textContent = s.focus_team;
  el("thOpp").textContent = s.opponent;
  const statBody = el("statTable").querySelector("tbody");
  statBody.innerHTML = "";
  STAT_ROWS.forEach(function (row) {
    const tr = document.createElement("tr");
    tr.innerHTML = "<td>" + row[0] + "</td><td>" + cell(s.team[row[1]]) +
                   "</td><td>" + cell(s.opponent_team[row[1]]) + "</td>";
    statBody.appendChild(tr);
  });
  const playerBody = el("playerTable").querySelector("tbody");
  playerBody.innerHTML = "";
  (s.core_players || []).forEach(function (p) {
    const tr = document.createElement("tr");
    tr.innerHTML = "<td>" + p.name + "</td><td>" + p.score + "</td><td>" + p.passes +
                   "</td><td>" + p.pass_accuracy_pct + "</td><td>" + p.key_passes +
                   "</td><td>" + p.shots + "</td><td>" + p.goals +
                   "</td><td>" + p.touches + "</td>";
    playerBody.appendChild(tr);
  });
}
DATA.matches.forEach(function (m, i) {
  const button = document.createElement("button");
  button.textContent = m.label;
  button.onclick = function () { render(i); };
  el("picker").appendChild(button);
});
if (DATA.matches.length) { render(0); }
</script>
</body>
</html>
"""


def _match_label(summary):
    """由 summary.match 拼出下拉/按钮标签：日期 | 赛事 | 主队 比分 客队。"""
    match = summary["match"]
    return (
        f"{match['date']} | {match['competition']} | "
        f"{match['home_team']} {match['home_score']}-{match['away_score']} "
        f"{match['away_team']}"
    )


def collect_matches():
    """扫描缓存目录，收集七件套齐备的比赛（返回列表）。"""
    if not CACHE_DIR.is_dir():
        return []
    matches = []
    for cache_dir in sorted(CACHE_DIR.iterdir()):
        if not cache_dir.is_dir():
            continue
        summary_path = cache_dir / "summary.json"
        narrative_path = cache_dir / "narrative.json"
        figure_paths = {name: cache_dir / "figures" / f"{name}.png" for name in FIGURE_NAMES}
        if not (summary_path.is_file() and narrative_path.is_file()):
            continue
        if not all(path.is_file() for path in figure_paths.values()):
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            narrative_data = json.loads(narrative_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  [跳过] {cache_dir.name}: 读取失败 {exc}")
            continue
        narrative = narrative_data.get("narrative") if isinstance(narrative_data, dict) else None
        if not isinstance(narrative, str) or not narrative.strip():
            print(f"  [跳过] {cache_dir.name}: narrative 缺失或为空")
            continue
        matches.append(
            {
                "match_id": int(cache_dir.name),
                "label": _match_label(summary),
                "summary": summary,
                "narrative": narrative,
                "figures": {
                    name: f"figures/{cache_dir.name}/{name}.png"
                    for name in FIGURE_NAMES
                },
                "_source_dir": cache_dir,
            }
        )
    return matches


def _prepare_out_dir(out_dir):
    """准备输出目录：仅当目录不存在、为空或是本工具生成的产物时才允许清理。"""
    if out_dir.exists():
        if not out_dir.is_dir():
            print(f"错误: 输出路径已存在且不是目录: {out_dir}")
            sys.exit(1)
        if (out_dir / MARKER_NAME).is_file():
            shutil.rmtree(out_dir)
        elif any(out_dir.iterdir()):
            print(f"错误: 目录已存在且不是本工具生成的产物，拒绝覆盖: {out_dir}")
            print(f"      如确认要覆盖，请先手动删除，或换一个输出目录")
            sys.exit(1)
    out_dir.mkdir(parents=True, exist_ok=True)


def export(out_dir):
    """导出静态演示包，返回导出的比赛数量。"""
    matches = collect_matches()
    if not matches:
        print(f"错误: {CACHE_DIR} 下没有七件套齐备的比赛，请先运行 scripts/prefetch.py")
        sys.exit(1)

    _prepare_out_dir(out_dir)

    for item in matches:
        source_dir = item.pop("_source_dir")
        target_dir = out_dir / "figures" / str(item["match_id"])
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in FIGURE_NAMES:
            shutil.copy2(source_dir / "figures" / f"{name}.png", target_dir / f"{name}.png")
        print(f"  [导出] {item['match_id']} | {item['label']}")

    payload = {"matches": matches, "exported_at": __import__("datetime").datetime.now().isoformat(timespec="seconds")}
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = PAGE_TEMPLATE.replace("@@CSS@@", CSS).replace("@@DATA@@", data_json)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / MARKER_NAME).write_text(
        "本目录由 scripts/export_static_demo.py 生成，可安全删除或重新生成。\n",
        encoding="utf-8",
    )
    return len(matches)


def main():
    out_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUT_DIR
    print(f"扫描缓存目录: {CACHE_DIR}")
    count = export(out_dir)
    files = [p for p in out_dir.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    print("-" * 60)
    print(f"[完成] 已导出 {count} 场比赛到: {out_dir}")
    print(f"[完成] 文件数 {len(files)}，合计 {total / 1024 / 1024:.1f} MB")
    print(f"[使用] 把整个 {out_dir.name}/ 目录拷到 U 盘，双击 index.html 即可离线演示")


if __name__ == "__main__":
    main()
