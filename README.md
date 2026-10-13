# FTAS — Football Tactical Analysis System

基于 [StatsBomb 开放数据](https://github.com/statsbomb/open-data) 的足球战术分析系统。
选定一场比赛并给出一句分析提示，系统会自动生成传球网络图、射门分布图、活动热力图与结构化统计摘要，
再由大语言模型输出中文战术解读。

提供两种使用方式：**Web 服务**（FastAPI + 静态前端，Docker 一键部署）与**命令行工具**。

## Features

- **三张战术图**：传球网络（节点大小 = 传球次数，连线粗细 = 传球频次）、射门分布（红点 = 进球）、活动热力图（触球密度 KDE）
- **结构化统计摘要**：把一场比赛压缩成固定 Schema 的 JSON，涵盖球队对比、战术风格、进攻偏好与核心球员
- **AI 战术解读**：模型只依据摘要中的数字生成五段式中文分析（结论 / 战术风格 / 进攻偏好 / 核心球员表现 / 建议），并受输出校验约束
- **球队名模糊匹配**：支持简称（`barca`、`psg`）、拼写错误与重音差异；存在歧义时返回候选项而非猜测
- **多源数据下载**：内置三个数据源回退，在网络受限环境下仍可获取任意比赛
- **离线回退**：模型或网络不可用时，自动改用预置结果，并在响应中标注来源

## Architecture

```
浏览器（web/，原生 HTML + JavaScript）
   │  POST /api/analyze
   ▼
FastAPI（app/）
   ├── src/data_source.py          按 match_id 取数：命中缓存直读，miss 时多源回退下载
   ├── src/pipeline.py             事件 → 传球网络 / 射门 / 热力图
   ├── src/analysis/summary.py     压缩为结构化摘要 JSON
   ├── src/llm/                    摘要 + 用户提示词 → 中文战术解读
   └── data/cache/{match_id}/      原始数据 + summary.json + 三张图 + narrative.json
   ▼
StatsBomb 开放数据（jsdelivr / GitHub API / raw 三源回退）
   ▼
兼容 OpenAI 协议的大模型服务
```

一次请求的完整流程：

1. 校验 `match_id`、球队名与提示词长度
2. `ensure_match_data()`：缓存命中直读，miss 时下载 events / matches / lineups
3. `analyze_match()`：清洗事件 → 构建传球网络、射门与触球坐标 → 绘制三张图
4. `build_match_summary()`：生成固定 Schema 的摘要 JSON
5. 保存摘要与图片到 `data/cache/{match_id}/`
6. 调用模型生成战术解读；输出校验不通过会自动纠错重试一次
7. 模型不可用时回退到预置结果；再不可用则返回 502 与可操作提示

## Quick Start

### Docker（推荐）

```bash
git clone <repository-url>
cd FTAS
cp .env.example .env          # 填入 OPENAI_API_KEY；留空则只使用离线回退结果
docker compose build
docker compose up -d
```

浏览器打开 <http://localhost:8000>。

### 本地 Python

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 命令行工具

命令行与 Web 服务共用同一套分析引擎，适合批量处理或脚本化调用。

```bash
# 交互式：输入球队 → 过滤赛事 → 选择比赛 → 自动下载并分析
.venv/bin/python analyze.py

# 查询球队的比赛列表与 match_id
.venv/bin/python list_matches.py "Real Madrid" "La Liga" 30

# 按 match_id 切换比赛（第二个参数为分析球队）
.venv/bin/python download_match.py 3773497 "Real Madrid"

# 只运行分析
.venv/bin/python main.py [match_id] [team_name]
```

产物写入 `outputs/`：`figures/` 下三张 PNG，`reports/match_analysis.txt` 为文字报告。

## Project Structure

```
FTAS/
├── app/                      # FastAPI 服务层
│   ├── main.py               #   路由与请求编排
│   ├── schemas.py            #   请求体校验
│   ├── limiter.py            #   按 IP 限流
│   └── team_matcher.py       #   球队名归一化与模糊匹配
├── web/                      # 前端单页（纯静态，无构建步骤）
├── src/                      # 分析引擎
│   ├── data_source.py        #   取数与缓存
│   ├── pipeline.py           #   分析流程编排
│   ├── analysis/             #   传球网络 / 射门 / 热力图 / 统计摘要
│   ├── preprocessing/        #   事件清洗
│   ├── visualization/        #   mplsoccer 绘图
│   ├── llm/                  #   模型客户端与提示词
│   └── utils/config.py       #   路径配置
├── scripts/
│   ├── prefetch.py           #   预置比赛数据（幂等）
│   ├── smoke_test.py         #   离线自检
│   └── export_static_demo.py #   导出静态离线包
├── tests/                    # 单元测试
├── data/
│   ├── match_index.json      #   比赛索引（随仓库提供）
│   └── cache/{match_id}/     #   运行时缓存（不入库）
├── deploy/                   # 部署手册
└── Dockerfile · docker-compose.yml · .env.example
```

## HTTP API

服务同时托管前端静态页（根路径 `/`），接口同源，无需跨域配置。

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | 健康检查，返回是否已配置模型 Key |
| GET | `/api/teams?q=&limit=8` | 球队名候选，用于输入框自动补全 |
| GET | `/api/matches?team=&competition=&limit=50` | 按球队筛选比赛 |
| POST | `/api/analyze` | 执行分析，返回摘要、图片地址与战术解读 |
| GET | `/api/figure/{match_id}/{name}.png` | 三张图之一 |

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"match_id":3749552,"team_name":"Manchester United","prompt":"分析这场比赛的战术风格"}'
```

```jsonc
{
  "match_id": 3749552,
  "team_name": "Manchester United",
  "summary": { /* 见下节 */ },
  "figures": {
    "pass_network": "/api/figure/3749552/pass_network.png",
    "shot_map":     "/api/figure/3749552/shot_map.png",
    "heatmap":      "/api/figure/3749552/heatmap.png"
  },
  "narrative": "……",
  "narrative_source": "live",   // live = 本次调用模型；cache = 回退预置结果
  "elapsed_ms": 8437
}
```

错误码：`400` 参数非法 · `429` 触发限流 · `502` 数据与模型均不可用（响应携带 `preloaded` 列表）· `503` 索引缺失。

## Statistical Summary

摘要 JSON 是模型的唯一事实来源：系统提示词强制模型只能引用其中的数字。

| 分组 | 字段 |
|---|---|
| `match` | 日期、赛事、赛季、主客队、比分 |
| `team` / `opponent_team` | 进球、射门、射正、传球数、传球成功数、传球成功率、控球次数、控球份额、进攻三区传球、禁区进入、传球网络边数 |
| `style` | 阵型、平均传球长度、长传占比、每控球传球数、前场压迫次数 |
| `attack_preference` | 左/中/右路占比、传中、直塞、平均射门距离、禁区内/外射门 |
| `core_players` | 综合分前 5：`进球×5 + 关键传球×3 + 射门×1 + 网络度数×0.5 + 传球数×0.05` |
| `players` / `shot_list` | 全队传球表与逐脚射门明细 |

> [!NOTE]
> 主要口径：传球成功 = `pass.outcome.name` 为空；射正 = `outcome ∈ {Goal, Saved, Post}`；
> 禁区 = `x ≥ 102 且 18 ≤ y ≤ 62`；进攻三区 = `x ≥ 80`；射门距离 = 射门点到球门中心 `(120, 40)` 的欧氏距离。
> 完整注释见 `src/analysis/summary.py`。

## Configuration

所有配置通过环境变量注入，模板见 `.env.example`。

| Variable | Default | Description |
|---|---|---|
| `APP_PORT` | `8000` | 宿主映射端口（容器内固定 8000） |
| `FTAS_CACHE_DIR` | `data/cache` | 比赛数据与产物缓存目录 |
| `OPENAI_BASE_URL` | `https://api.deepseek.com/v1` | 兼容 OpenAI 协议的模型服务地址 |
| `OPENAI_API_KEY` | — | 模型服务 Key；留空则只返回离线回退结果 |
| `LLM_MODEL` | `deepseek-chat` | 模型名 |
| `LLM_TIMEOUT` | `60` | 单次模型调用总超时（秒） |
| `LLM_MAX_RETRIES` | `3` | 模型调用重试次数 |
| `RATE_LIMIT_PER_MIN` | `60` | `/api/analyze` 与 `/api/matches` 的每分钟限额（`/api/teams` 固定 300） |
| `MAX_PROMPT_CHARS` | `8000` | 提示词长度上限 |
| `FTAS_STATSBOMB_BASE` | — | 自定义数据基址；设置后只使用该地址，不再多源回退 |

## Data Source & Caching

`raw.githubusercontent.com` 在部分网络环境下不可达，因此数据层默认按顺序尝试三个来源：

```
events / matches :  jsdelivr  →  GitHub API  →  raw
lineups          :  GitHub API →  jsdelivr   →  raw   （jsdelivr 对 lineups 常返回 403）
```

只要有一个来源可达，就能分析索引中的任意一场比赛。

> [!WARNING]
> `data/cache/` 与 `.env` 都不纳入版本控制，**全新克隆后缓存为空**。
> 首次分析某场比赛需要下载 3–4 MB 数据（约 30–70 秒），之后同一场比赛走缓存（约 8 秒）。

建议提前预置数据：

```bash
.venv/bin/python scripts/prefetch.py     # 下载比赛数据
.venv/bin/python scripts/smoke_test.py   # 离线自检，退出码非 0 表示有缺失
```

## Deployment

部署到 Linux 服务器的完整步骤见 [deploy/README.md](deploy/README.md)，其中两个常见问题值得先看：

> [!WARNING]
> 1. **镜像拉取失败**：国内服务器通常无法直连 Docker Hub，需要在 `/etc/docker/daemon.json` 配置镜像加速器。
> 2. **缓存目录属主**：`tar` 解压出的文件属主是 `root`，而容器内以 uid 1000 运行，必须执行 `chown -R 1000:1000 data/cache`，否则分析接口会返回 502。

## Development & Testing

```bash
.venv/bin/python -m pytest tests/ -q              # 单元测试（全部离线）
.venv/bin/uvicorn app.main:app --reload --port 8000
```

技术栈：FastAPI · uvicorn · pydantic · slowapi · pandas · matplotlib · mplsoccer · statsbombpy · openai

## Data Attribution

- 数据提供方：[StatsBomb](https://statsbomb.com/)
- 开放数据仓库：[github.com/statsbomb/open-data](https://github.com/statsbomb/open-data)
- 覆盖范围：国际大赛（世界杯、欧洲杯、美洲杯等）与欧洲主要联赛（英超、西甲、德甲、意甲、法甲、欧冠等）的历史比赛
- 许可协议：[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)，**仅限非商业用途**，使用时须注明数据来源

> [!NOTE]
> 本项目的分析结果仅用于学习与技术演示，不代表任何球队或数据提供方的官方观点。

## FAQ

**图表中的中文显示为方块？**
镜像内已安装 `fonts-noto-cjk`；自行搭建环境时需额外安装中文字体。

**模型会编造数据吗？**
有三层约束：系统提示词禁止引用摘要之外的数字；输出校验检查五段结构与"出现了摘要中不存在的小数"；
校验失败会自动纠错重试一次。实测询问摘要中不存在的 xG 时，模型会回答"数据不足"。

**为什么某些比赛的首页分析特别慢？**
该场数据尚未缓存，需现场下载。第二次请求起约 8 秒。

**提示"该场比赛未预置数据"？**
三个数据源均不可达，且本地没有该场缓存。响应中的 `preloaded` 字段列出了当前可分析的比赛。

**支持 Windows 吗？**
代码跨平台，推荐通过 Docker 部署（需 Windows 10/11）。纯 Python 方式下 Windows 7 需降级到 Python 3.8
并调整依赖（参考仓库中的 `requirements-win7.txt`），未在真实环境验证，不推荐。
