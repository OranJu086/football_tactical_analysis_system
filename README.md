# FTAS - Football Tactical Analysis System

基于 [StatsBomb 开放数据](https://github.com/statsbomb/open-data) 的足球战术分析系统，可对任意一场公开比赛数据生成传球网络图、射门分布图、活动热力图和文字分析报告。

---

## 一、使用方式

### 1. 环境准备（只需一次）

```bash
# macOS / Linux，要求 Python 3.11+
cd FTAS
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

```bat
:: Windows 10 / 11，要求 Python 3.11+（先安装 python.org 的 3.11 x64）
cd FTAS
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### 2. 日常使用（推荐）

```bash
.venv/bin/python analyze.py
```

按提示依次操作：

```
① 输入要分析的球队名称（回车默认 Barcelona）
② 输入赛事关键词过滤（如 La Liga / Champions League，回车=全部）
③ 从编号列表中选择要分析的比赛（输入 0 可查看全部）
```

选择后程序会自动完成：下载比赛数据 → 更新球队配置 → 运行分析 → 输出结果。

### 3. 手动模式

```bash
# 查询某球队的比赛列表和 match_id
.venv/bin/python list_matches.py "Real Madrid" "La Liga" 30

# 按 match_id 切换比赛（第二个参数为球队名）
.venv/bin/python download_match.py 3773497 "Real Madrid"

# 只运行分析（分析 data/raw/statsbomb/ 下当前已下载的比赛）
.venv/bin/python main.py
```

### 4. 输出结果

| 文件 | 说明 |
|---|---|
| `outputs/figures/pass_network.png` | 传球网络图（节点大小=传球次数，连线粗细=传球频次） |
| `outputs/figures/shot_map.png` | 射门分布图（红色=进球） |
| `outputs/figures/heatmap.png` | 活动热力图（全队触球位置密度） |
| `outputs/reports/match_analysis.txt` | 文字报告（比分、传球统计、射门统计） |

> 每次分析会覆盖上次的输出；如需留档请先复制到其他目录。

---

## 二、实现方式

### 架构

```
根目录脚本（操作层）            src/（分析引擎）
┌──────────────────┐          ┌──────────────────────────┐
│ analyze.py       │          │ data_loader/             │
│ download_match.py│ ───────► │ preprocessing/           │
│ list_matches.py  │          │ analysis/                │
│ main.py          │          │ visualization/           │
└──────────────────┘          │ utils/config.py          │
                              └──────────────────────────┘
```

### 数据流

```
StatsBomb 开放数据 (statsbombpy)
        │ 下载 events.json / matches.json / lineups.json
        ▼
data/raw/statsbomb/  ← match_index.json 缓存比赛索引（离线秒查）
        │
        ▼
main.py:
  1. load_events()          json_normalize → pandas DataFrame
  2. clean_pass_events()    过滤传球事件，提取起终点坐标
  3. build_pass_network()   球员平均站位 + 传球关系边
  4. extract_shots()        射门事件 + 是否进球
  5. extract_positions()    全部触球坐标
  6. create_pitch() + 三个 draw_*()   用 mplsoccer 画图 → PNG
  7. write_report()         文字报告 → match_analysis.txt
```

### 关键设计

- **交互式流程**（`analyze.py`）：输入球队名 → 编号列出比赛 → 用户选择 → 自动下载并分析，每次分析前执行；
- **比赛索引缓存**（`match_index.json`）：首次扫描 StatsBomb 全部赛事目录后本地缓存，之后切换比赛无需联网扫描；
- **单场数据隔离**：`matches.json` 只保留被选中的比赛，保证报告信息准确；
- **无界面渲染**：`main.py` 内置 `matplotlib.use('Agg')`，可在无 GUI 的服务器环境运行；
- **可配置**：数据路径、输出路径、分析球队均集中在 `src/utils/config.py`。

### 依赖

`pandas` · `matplotlib` · `mplsoccer` · `statsbombpy`

---

## 三、数据来源

- **数据提供方**：[StatsBomb](https://statsbomb.com/)（足球数据分析公司）
- **开放数据仓库**：[github.com/statsbomb/open-data](https://github.com/statsbomb/open-data)
- **获取方式**：程序通过 `statsbombpy` 库自动下载原始 JSON（比赛事件、阵容、赛程）
- **覆盖内容**：国际大赛（世界杯、欧洲杯、美洲杯等）与欧洲主要联赛（西甲、英超、德甲、欧冠等）的历史比赛
- **许可协议**：StatsBomb 开放数据采用 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) 协议，**仅限非商业用途**，使用时须注明数据来源。

---

---

## 四、平台兼容性

本项目是纯 Python 代码，**跨平台**（macOS / Linux / Windows），不依赖 macOS 专属功能。

| 平台 | 支持情况 |
|---|---|
| macOS 10.15+ | ✅ 正常使用（开发环境） |
| Linux | ✅ 正常使用（需 Python 3.11+） |
| Windows 10 / 11 | ✅ 正常使用（需 Python 3.11+，见上文安装命令） |
| Windows 7 | ⚠️ 需降级，见下文 |

### Windows 7 兼容说明

- **瓶颈不是本项目代码**（代码兼容 Python 3.8），而是 **Python 官方自 3.9 起不再支持 Windows 7**——Win7 最高只能安装 Python 3.8，而当前依赖链（pandas 3.x、mplsoccer 1.8 等）需要 Python 3.10+；
- 若必须在 Win7 使用，请安装 **Python 3.8.10**，并改用旧版依赖（已提供 [requirements-win7.txt](requirements-win7.txt)）：
  ```bat
  py -3.8 -m venv .venv
  .venv\Scripts\pip install -r requirements-win7.txt
  .venv\Scripts\python analyze.py
  ```
- 注意：requirements-win7.txt 为"尽力而为"的保守版本上限，**需在真实 Win7 环境实测**；个别库（如旧版 statsbombpy）API 可能与本项目不同，必要时改用 `requests` 直连 StatsBomb 开放数据下载；
- 由于 Windows 7 已于 2020 年停止官方支持，**不推荐**在新项目中兼容 Win7，建议使用 Windows 10/11。

---

## 免责声明

本项目的分析结果仅用于学习与技术演示，不代表任何球队或数据提供方的官方观点。
