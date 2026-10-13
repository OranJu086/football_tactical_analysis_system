# FTAS · Football Tactical Analysis System

基于 [StatsBomb 开放数据](https://github.com/statsbomb/open-data) 的足球战术分析系统：
**选一场比赛 → 输入一句分析提示 → 自动产出三张战术图 + 结构化统计摘要 + 中文战术解读。**

> 🟢 在线演示（毕设答辩期间）：<http://47.100.102.198:8000>
> 页面底部标注了数据来源与许可；服务为一次性部署，答辩结束后关停。

---

## 目录

1. [功能一览](#一功能一览)
2. [快速开始](#二快速开始)
3. [项目结构](#三项目结构)
4. [系统架构与数据流](#四系统架构与数据流)
5. [统计摘要（Schema v2）](#五统计摘要schema-v2)
6. [HTTP API](#六http-api)
7. [数据来源与离线兜底](#七数据来源与离线兜底)
8. [部署到服务器](#八部署到服务器)
9. [开发与测试](#九开发与测试)
10. [数据来源与许可](#十数据来源与许可)
11. [常见问题](#十一常见问题)

---

## 一、功能一览

| 能力 | 说明 |
|---|---|
| **传球网络图** | 节点大小 = 传球次数，连线粗细 = 传球频次，位置 = 球员平均站位 |
| **射门分布图** | 每脚射门的落点，红点 = 进球 |
| **活动热力图** | 全队触球位置密度（KDE） |
| **统计摘要** | 战术风格 / 进攻偏好 / 核心球员 三组指标（见第五节） |
| **AI 战术解读** | 大模型基于摘要生成中文分析，固定五段：结论 / 战术风格 / 进攻偏好 / 核心球员表现 / 建议 |
| **球队名模糊匹配** | 支持简称（`barca`、`psg`）、拼写错误、重音差异；歧义时给出候选而不是乱猜 |
| **离线兜底** | 模型或网络不可用时自动回退到预置结果，页面标注「离线缓存结果」 |

---

## 二、快速开始

### 1. 在线访问

直接用浏览器打开 <http://47.100.102.198:8000>：输入球队名 → 选择比赛 → 输入提示词 → 点「分析」。

### 2. 本机用 Docker 运行（推荐）

```bash
cd FTAS
cp .env.example .env          # 打开 .env，把 OPENAI_API_KEY 填上（不填则走离线缓存模式）
docker compose build
docker compose up -d
# 浏览器打开 http://localhost:8000
```

### 3. 不用 Docker 直接跑

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. 命令行版（原有用法，仍然可用）

```bash
# 交互式：输入球队 → 过滤赛事 → 选比赛 → 自动下载并分析
.venv/bin/python analyze.py

# 查询某球队的比赛列表与 match_id
.venv/bin/python list_matches.py "Real Madrid" "La Liga" 30

# 按 match_id 切换比赛（第二个参数为球队名）
.venv/bin/python download_match.py 3773497 "Real Madrid"

# 只跑分析：python main.py [match_id] [team_name]
.venv/bin/python main.py
```

命令行产物：

| 文件 | 说明 |
|---|---|
| `outputs/figures/pass_network.png` | 传球网络图 |
| `outputs/figures/shot_map.png` | 射门分布图 |
| `outputs/figures/heatmap.png` | 活动热力图 |
| `outputs/reports/match_analysis.txt` | 文字报告 |

---

## 三、项目结构

```
FTAS/
├── app/                         # FastAPI 服务层
│   ├── main.py                  #   路由：health / teams / matches / analyze / figure
│   ├── schemas.py               #   请求体校验（pydantic）
│   ├── limiter.py               #   按 IP 限流（slowapi）
│   └── team_matcher.py          #   球队名归一化与模糊匹配
├── web/                         # 前端单页（纯静态，无构建步骤）
│   ├── index.html · app.js · style.css
├── src/                         # 分析引擎（与命令行共用）
│   ├── data_source.py           #   按 match_id 缓存取数 + 多源回退下载
│   ├── pipeline.py              #   串起全流程，返回内存态结果
│   ├── analysis/summary.py      #   统计摘要（Schema v2）
│   ├── analysis/                #   传球网络 / 射门 / 热力图 的数据构建
│   ├── preprocessing/           #   事件清洗
│   ├── visualization/           #   mplsoccer 绘图
│   ├── llm/                     #   模型接入（client + prompts）
│   └── utils/config.py          #   路径配置（全部由环境变量决定）
├── scripts/
│   ├── prefetch.py              #   预置演示比赛数据（幂等）
│   ├── smoke_test.py            #   离线自检（不联网、不调用模型）
│   └── export_static_demo.py    #   导出 U 盘离线演示包
├── tests/                       # 单元测试（模型匹配 / 摘要 / 提示词）
├── deploy/README.md             # 服务器部署手册
├── docs/答辩演示脚本.md          # 3 分钟演示流程 + 应急手册
├── data/
│   ├── match_index.json         #   3961 场比赛索引（随仓库提供）
│   └── cache/{match_id}/        #   运行时缓存（不入库，见第七节）
├── Dockerfile · docker-compose.yml · .env.example
└── main.py / analyze.py / list_matches.py / download_match.py   # 命令行入口
```

---

## 四、系统架构与数据流

```
浏览器（web/，原生 HTML + JS，同源 fetch）
   │  POST /api/analyze {match_id, team_name, prompt}
   ▼
FastAPI（app/main.py，容器内 uvicorn）
   ├── src/data_source.py        按 match_id 取数：命中缓存直读，miss 时多源回退下载
   ├── src/pipeline.py           事件 → 传球网络 / 射门 / 热力图
   ├── src/analysis/summary.py   压缩成结构化摘要 JSON（Schema v2）
   ├── src/llm/                  摘要 + 用户提示词 → 中文战术解读（含防幻觉校验）
   └── data/cache/{match_id}/    原始数据 + summary.json + 三张图 + narrative.json
   ▼
StatsBomb 开放数据（raw / jsdelivr / GitHub API 三源回退）
   ▼
DeepSeek（OpenAI 兼容协议，base_url 可配置）
```

**一次分析的完整流程**

1. 校验参数（match_id、球队名、提示词长度）→ 不合法返回 400
2. `ensure_match_data()`：缓存命中直接读，miss 时按「jsdelivr → GitHub API → raw」下载 events / matches / lineups
3. `analyze_match()`：清洗事件 → 构建传球网络、射门、触球坐标 → 绘制三张图
4. `build_match_summary()`：产出 Schema v2 摘要 JSON
5. 保存摘要与三张图到 `data/cache/{match_id}/`
6. 调用模型生成五段式中文解读；**输出校验不通过会自动纠错重试一次**
7. 模型不可用 → 回退到预置的 `narrative.json`（`narrative_source = "cache"`）；再不行返回 502 + 可操作提示

---

## 五、统计摘要（Schema v2）

摘要 JSON 是**模型的唯一事实来源**——系统提示词强制模型只能引用其中的数字，不得引入外部知识。

| 分组 | 字段 |
|---|---|
| `match` | 日期、赛事、赛季、主客队、比分 |
| `team` / `opponent_team` | 进球、射门、射正、传球数、传球成功数、传球成功率、控球次数、控球份额、进攻三区传球、禁区进入、传球网络边数 |
| `style`（战术风格） | 阵型、平均传球长度、长传占比、每控球传球数、前场压迫次数 |
| `attack_preference`（进攻偏好） | 左/中/右路占比、传中、直塞、平均射门距离、禁区内/外射门 |
| `core_players`（核心球员前 5） | 综合分 = `进球×5 + 关键传球×3 + 射门×1 + 网络度数×0.5 + 传球数×0.05` |
| `players` / `shot_list` | 全队传球表与逐脚射门明细 |

**关键口径**（详细注释见 `src/analysis/summary.py`）

- 传球成功 = `pass.outcome.name` 为空
- 射正 = `shot.outcome.name ∈ {Goal, Saved, Post}`
- 禁区 = `x ≥ 102 且 18 ≤ y ≤ 62`；进攻三区 = `x ≥ 80`
- 射门距离 = 射门点到球门中心 `(120, 40)` 的欧氏距离
- 左右中三分区按起点 `y` 划分，`right_pct = 100 − left − center`，保证三者之和恒为 100.0

---

## 六、HTTP API

服务同时托管前端静态页（根路径 `/`），所有接口同源、无需跨域配置。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | `{"status":"ok","llm_configured":true}` |
| GET | `/api/teams?q=&limit=8` | 球队名候选（自动补全），`q` 为空返回热门球队 |
| GET | `/api/matches?team=&competition=&limit=50` | 按球队筛选比赛，含 `resolved_team` / `matched_by` / `suggestions` |
| POST | `/api/analyze` | 执行分析并返回摘要、图片 URL 与战术解读 |
| GET | `/api/figure/{match_id}/{name}.png` | 三张图之一（`pass_network` / `shot_map` / `heatmap`） |

**POST /api/analyze**

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"match_id":3749552,"team_name":"Manchester United","prompt":"分析这场比赛的战术风格"}'
```

```jsonc
{
  "match_id": 3749552,
  "team_name": "Manchester United",
  "summary": { /* Schema v2 */ },
  "figures": {
    "pass_network": "/api/figure/3749552/pass_network.png",
    "shot_map":     "/api/figure/3749552/shot_map.png",
    "heatmap":      "/api/figure/3749552/heatmap.png"
  },
  "narrative": "……中文战术分析……",
  "narrative_source": "live",     // live = 本次调用模型；cache = 回退预置结果
  "elapsed_ms": 8437
}
```

**状态码**

| 码 | 含义 |
|---|---|
| 400 | 参数非法（match_id 非正整数、球队名不在本场、提示词为空或超长） |
| 429 | 触发按 IP 限流 |
| 502 | 数据取不到且无缓存 / 模型不可用且无缓存（响应含 `preloaded` 列表，可直接展示） |
| 503 | 比赛索引文件缺失 |

**限流额度**：`/api/analyze` 与 `/api/matches` 走 `RATE_LIMIT_PER_MIN`（默认 60/分钟）；
`/api/teams` 因配合输入框自动补全，单独放宽到 300/分钟。

**可配置环境变量**（见 `.env.example`）

`APP_PORT` · `FTAS_CACHE_DIR` · `OPENAI_BASE_URL` · `OPENAI_API_KEY` · `LLM_MODEL` · `LLM_TIMEOUT` ·
`LLM_MAX_RETRIES` · `RATE_LIMIT_PER_MIN` · `MAX_PROMPT_CHARS`

可选：`FTAS_STATSBOMB_BASE`（自定义数据基址，设置后只用该基址）· `FTAS_TEAM_NAME`（命令行默认球队）

---

## 七、数据源与离线兜底

### 多源回退

`raw.githubusercontent.com` 在国内网络下常被重置，因此 `src/data_source.py` 默认按顺序尝试三个来源：

```
events / matches :  jsdelivr  →  GitHub API  →  raw
lineups          :  GitHub API →  jsdelivr   →  raw   （jsdelivr 对 lineups 常返回 403）
```

只要有一个来源可达，就能分析**索引中的任意一场比赛**（3961 场）。设置 `FTAS_STATSBOMB_BASE`
可强制只用一个自建镜像（也用于测试超时行为）。

### 缓存与预置

- 运行时数据存在 `data/cache/{match_id}/`，每场一个子目录，互不覆盖；
- **`data/cache/` 与 `.env` 都不入 Git**，全新克隆后缓存为空；
- 想开箱即用，先跑一次预置脚本（幂等，已存在则跳过）：

```bash
.venv/bin/python scripts/prefetch.py        # 下载演示比赛数据
.venv/bin/python scripts/smoke_test.py      # 离线自检，退出码非 0 表示有缺失
```

### 离线兜底

| 情况 | 行为 |
|---|---|
| 模型可用 | 正常返回，`narrative_source = "live"` |
| 模型不可用 / 输出不合格 | 回退到预置 `narrative.json`，`narrative_source = "cache"`，前端显示黄色徽标 |
| 数据取不到且无预置结果 | 502，并返回 `preloaded` 列表，前端提示「当前可分析的比赛共 N 场」 |

> **首次分析一场未预置的比赛需要 30–70 秒**（现场下载 3–4 MB 数据），之后同一场比赛约 8 秒。
> 演示前建议把要展示的比赛各点一次「预热」。

### U 盘离线演示包

完全脱离网络与服务器的演示方式，适合答辩现场网络不可控的情况：

```bash
.venv/bin/python scripts/export_static_demo.py    # 生成 demo_static/
```

把整个 `demo_static/` 目录拷进 U 盘，在任何有浏览器的电脑上双击 `index.html` 即可演示
（含三张图、统计对比表与战术解读，比赛之间可切换）。注意必须**整个目录一起拷贝**。

---

## 八、部署到服务器

完整步骤见 **[deploy/README.md](deploy/README.md)**（服务器装 Docker → 传代码 → 配置 `.env` →
构建镜像 → 启动 → 放行端口 → 健康检查），其中包含两个容易踩的坑：

1. **Docker Hub 不可达**：需要在 `/etc/docker/daemon.json` 配置国内镜像加速器；
2. **缓存目录属主**：`tar` 解压出来属主是 `root`，而容器里以 uid 1000 运行，必须
   `chown -R 1000:1000 data/cache`，否则分析会返回 502。

---

## 九、开发与测试

```bash
# 单元测试（球队匹配 / 统计摘要 / 提示词，全部离线）
.venv/bin/python -m pytest tests/ -q

# 本地起服务
.venv/bin/uvicorn app.main:app --reload --port 8000

# 预置数据 / 离线自检 / 导出离线包
.venv/bin/python scripts/prefetch.py
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/export_static_demo.py
```

技术栈：`FastAPI` · `uvicorn` · `pydantic` · `slowapi` · `pandas` · `matplotlib` · `mplsoccer` ·
`statsbombpy` · `openai`（兼容 OpenAI 协议）· `streamlit`（早期网页版 `web_app.py`，保留可用）

---

## 十、数据来源与许可

- **数据提供方**：[StatsBomb](https://statsbomb.com/)（足球数据分析公司）
- **开放数据仓库**：[github.com/statsbomb/open-data](https://github.com/statsbomb/open-data)
- **获取方式**：程序按需下载原始 JSON（比赛事件、阵容、赛程），并在本地按 `match_id` 缓存
- **覆盖内容**：国际大赛（世界杯、欧洲杯、美洲杯等）与欧洲主要联赛（西甲、英超、德甲、意甲、法甲、欧冠等）的历史比赛
- **许可协议**：StatsBomb 开放数据采用 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)，
  **仅限非商业用途**，使用时须注明数据来源（网页页脚已标注）

---

## 十一、常见问题

**Q：点了某场比赛，提示「该场比赛未预置数据，且服务器无法在线下载」？**
说明三个数据源都不可达，且本地没有该场的预置结果。响应里带 `preloaded` 列表，从里面挑一场即可；
或先在本机跑 `scripts/prefetch.py` 补齐数据。

**Q：图表里的中文显示成方块？**
镜像里已安装 `fonts-noto-cjk`。自建环境需自行安装中文字体。

**Q：为什么第一次分析某场比赛特别慢？**
需要现场下载该场的 events / matches / lineups（3–4 MB）。第二次起走缓存，约 8 秒。

**Q：模型会不会编造数据？**
有三道防线：系统提示词禁止引用摘要之外的数字；输出校验会检查五段结构与「出现了摘要中不存在的小数」；
校验不通过自动纠错重试一次。实测询问摘要中不存在的 xG 时，模型会回答「数据不足」。

**Q：Windows 7 能用吗？**
项目本身跨平台，但 Docker 部署需 Windows 10/11；纯 Python 方式下 Win7 最高只支持 Python 3.8，
需要降级依赖（参考仓库中的 `requirements-win7.txt`），且未在真实 Win7 环境实测，**不推荐**。

---

## 免责声明

本项目的分析结果仅用于学习与技术演示，不代表任何球队或数据提供方的官方观点。
