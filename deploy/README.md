# FTAS 部署手册（毕设答辩用）

本手册面向没有运维经验的毕设学生，按顺序操作即可把「足球战术分析系统」部署到一台 Linux 服务器上，并附答辩远程演示方案（含离线兜底）与常见故障排查。

---

## 目录

1. [整体架构](#1-整体架构)
2. [服务器安装 Docker](#2-服务器安装-docker)
3. [上传代码到服务器](#3-上传代码到服务器)
4. [配置 .env（填 API Key）](#4-配置-env填-api-key)
5. [构建镜像（含国内镜像源 workaround）](#5-构建镜像含国内镜像源-workaround)
6. [启动服务](#6-启动服务)
7. [开放非标准端口（安全组）](#7-开放非标准端口安全组)
8. [健康检查与浏览器访问](#8-健康检查与浏览器访问)
9. [开机自启](#9-开机自启)
10. [远程演示与离线兜底方案](#10-远程演示与离线兜底方案)
11. [常见故障排查](#11-常见故障排查)
12. [常用运维命令速查](#12-常用运维命令速查)

---

## 1. 整体架构

```
浏览器 ──> 服务器:8000 ──> FastAPI (uvicorn, Docker 容器)
                              │
                              ├── data/cache/{match_id}/  预置比赛缓存（events/matches/lineups/summary/narrative/figures）
                              ├── data/match_index.json   3961 场比赛索引
                              └── LLM 接口（DeepSeek，通过 OPENAI_API_KEY 调用）
```

- 容器内服务端口固定为 **8000**，宿主机映射端口由 `.env` 的 `APP_PORT` 决定（默认 8000）。
- `data/cache/` 通过 Docker 卷挂载进容器，宿主机上直接修改缓存即可被服务读取。
- `.env` 不会进入镜像（`.dockerignore` 已排除），Key 只通过环境变量注入运行中的容器。

---

## 2. 服务器安装 Docker

> 以 Ubuntu 22.04 / Debian 12 为例。CentOS/Rocky 见下方备注。

```bash
# 1) 更新软件源并安装依赖
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# 2) 添加 Docker 官方 GPG Key 与软件源
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://mirrors.ustc.edu.cn/docker-ce/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://mirrors.ustc.edu.cn/docker-ce/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 3) 安装 Docker Engine 与 Compose 插件
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4) 把当前用户加入 docker 组（免 sudo），然后重新登录或执行 newgrp docker
sudo usermod -aG docker "$USER"
newgrp docker

# 5) 验证
docker --version
docker compose version
```

> **CentOS/Rocky Linux 备注**：把上面的 `https://mirrors.ustc.edu.cn/docker-ce/linux/ubuntu` 换成
> `https://mirrors.ustc.edu.cn/docker-ce/linux/centos`，`lsb_release -cs` 换成 `9`（Rocky 9 用 centos 源即可）。

> **校园网下载慢**：`apt-get update` 过慢时，可先把系统源换成 USTC/TUNA 镜像：
> `sudo sed -i 's@//.*archive.ubuntu.com@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list`（Debian 需按实际源文件调整）。

---

## 3. 上传代码到服务器

任选一种方式，把整个项目目录（含 `data/cache/` 预置比赛、`web/`、`scripts/`）传到服务器。

### 方式 A：git（推荐）

```bash
# 本地（如果项目还没推送到仓库，先推一次）
git remote add origin <你的仓库地址>
git add -A && git commit -m "deploy" && git push -u origin main

# 服务器
git clone <你的仓库地址> FTAS
cd FTAS
```

> 注意：`data/cache/` 与 `.env` 在 `.gitignore` 中，不会随 git 上传。仓库克隆后需另行上传这两部分：
> 缓存可直接 `scp -r data/cache 服务器:FTAS/data/`，`.env` 在服务器上按第 4 节创建。

### 方式 B：scp 打包上传（无 git 仓库时）

```bash
# 本地打包（排除 .venv、.git 等大目录）
cd /path/to/FTAS
tar --exclude='.venv' --exclude='.git' --exclude='__pycache__' \
    --exclude='.docker-tmp' -czf /tmp/ftas.tar.gz .

# 上传并解压
scp /tmp/ftas.tar.gz 用户名@服务器IP:/home/用户名/
ssh 用户名@服务器IP
mkdir -p FTAS && tar -xzf ftas.tar.gz -C FTAS && cd FTAS
```

---

### 上传后必做：修正缓存目录属主

容器内的服务以 **uid 1000（app 用户）** 运行，而 `tar` 解压出来的文件属主是 `root`，
服务会**能读缓存、不能写**——点击「分析」时返回：

```
502 数据获取失败: 缓存产物写入失败: [Errno 13] Permission denied: 'data/cache/xxx/summary.json'
```

解决（在服务器上、项目根目录执行一次即可）：

```bash
chown -R 1000:1000 data/cache
ls -ld data/cache          # 确认属主已变成 1000
```

> 为什么 macOS 上不会遇到：Docker Desktop 会自动处理宿主与容器之间的属主映射，
> 而 Linux 上是真实 uid 映射，所以这个问题只在服务器上暴露。

## 4. 配置 .env（填 API Key）

在项目根目录（与 `docker-compose.yml` 同级）：

```bash
cd FTAS
cp .env.example .env
nano .env        # 或 vim .env
```

关键配置：

```dotenv
# 宿主机访问端口（云服务器安全组要放行这个端口）
APP_PORT=8000

# LLM 接口（默认 DeepSeek，可换成任意 OpenAI 兼容接口）
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=sk-在这里填你的真实Key
LLM_MODEL=deepseek-chat
```

- **只需要改 `OPENAI_API_KEY`**，其余保持默认即可。
- 不填 Key 也能启动和浏览缓存比赛，但 `POST /api/analyze` 只会走离线缓存兜底（`narrative_source=cache`），不会调用模型。
- `.env` 已被 `.dockerignore` 排除，**不会进入镜像**；它只通过 `docker compose` 注入运行中的容器。

---

## 5. 构建镜像（含国内镜像源 workaround）

国内服务器直连 Docker Hub / Debian / PyPI 容易超时，本项目镜像构建已支持镜像源参数。

```bash
cd FTAS

# 0) 准备 Docker 配置目录（部分服务器上 Docker 需要本机 auth/config，这里做一次本地副本避免权限问题）
rm -rf .docker-tmp && cp -R ~/.docker ./.docker-tmp && export DOCKER_CONFIG="$PWD/.docker-tmp"

# 1) 构建镜像：APT 走中科大源，pip 走清华源
docker compose build \
  --build-arg APT_MIRROR=https://mirrors.ustc.edu.cn \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 2) 构建完成后删除临时配置目录
rm -rf .docker-tmp
```

> **如果 pip 安装依赖仍然失败**，可以多试 1 次（网络抖动），或把 `PIP_INDEX_URL` 换成
> `https://mirrors.aliyun.com/pypi/simple/` 后重新构建。

> **Docker Hub 拉取基础镜像失败**时，在 `/etc/docker/daemon.json` 配置 registry mirror 后重启 Docker：
>
> ```json
> {
>   "registry-mirrors": [
>     "https://docker.m.daocloud.io",
>     "https://dockerproxy.com"
>   ]
> }
> ```
>
> ```bash
> sudo systemctl daemon-reload && sudo systemctl restart docker
> ```

---

## 6. 启动服务

```bash
cd FTAS
docker compose up -d
```

- `-d` 表示后台运行。
- 首次启动会创建 `ftas-ftas-1` 容器并挂载 `./data/cache` 到容器内 `/app/data/cache`。
- 查看状态：

```bash
docker compose ps
# 期望看到 STATUS 为 Up，PORTS 为 0.0.0.0:8000->8000/tcp
```

---

## 7. 开放非标准端口（安全组）

如果 `APP_PORT` 不是 80/443（本项目默认 **8000**），云服务器需要在**安全组**里放行该端口，否则外网访问不了。

以阿里云/腾讯云控制台为例：

1. 进入「云服务器 ECS/CVM → 安全组 → 配置规则 → 入方向 → 手动添加」。
2. 填写规则：
   - 协议类型：TCP
   - 端口范围：`8000/8000`（或你 `APP_PORT` 填的端口）
   - 授权对象：`0.0.0.0/0`（答辩演示可先全放行，演示完建议收紧）
3. 保存后一般立即生效。

同时检查服务器本机防火墙（如果开了 firewalld/ufw）：

```bash
# ufw（Ubuntu 常见）
sudo ufw allow 8000/tcp

# firewalld（CentOS 常见）
sudo firewall-cmd --permanent --add-port=8000/tcp && sudo firewall-cmd --reload
```

---

## 8. 健康检查与浏览器访问

```bash
# 1) 健康检查（看到 llm_configured:true 表示 Key 已注入）
curl localhost:8000/api/health
# 期望: {"status":"ok","llm_configured":true}

# 2) 前端首页应返回 HTML（标题 FTAS）
curl -s localhost:8000/ | head -20

# 3) 比赛查询接口应返回 200
curl -s "localhost:8000/api/matches?team=Manchester%20United&limit=3"
```

浏览器访问：

```
http://服务器IP:8000/
```

前端页会加载比赛列表、发起分析请求并展示 summary/图表/战术叙述。

---

## 9. 开机自启

`docker-compose.yml` 已配置 `restart: unless-stopped`，容器会在以下情况自动重启：

- 服务器重启后 Docker 启动时；
- 容器异常退出时（除非手动 `docker stop`）。

同时确保 Docker 服务本身开机自启：

```bash
sudo systemctl enable docker
sudo systemctl enable containerd
```

验证：

```bash
sudo reboot          # 重启服务器
docker compose ps    # 重启后应自动 Up
curl localhost:8000/api/health
```

> 手动停止后不再自启：`docker compose stop`；恢复自启：`docker compose start` 或 `docker compose up -d`。

---

## 10. 远程演示与离线兜底方案

> 面向「演示机不便携带」的场景（例如项目开发在台式机上）：
> **答辩现场不需要你的电脑**，只需要一台能上网的设备（教室电脑 / 同学笔记本 / 你自己的手机）。

### 10.1 主方案：教室电脑浏览器访问服务器

前提：云服务器已按第 1–9 节部署完成。

1. 答辩当天确认服务在跑：`curl http://<服务器IP>:<端口>/api/health`
2. 用教室电脑或同学笔记本打开浏览器，访问 `http://<服务器IP>:<端口>`
3. 正常演示。单次分析传输量约 1.3 MB（三张图）+ 12 KB 文本，手机热点也够用。

> ⚠️ 关键：**必须提前到答辩场地实测一次**（校园网 + 手机热点各访问一次）。
> 会场网络能否访问到你的服务器，是本方案唯一的命门。若完全不通公网，直接用 10.2。

### 10.2 终极兜底：离线静态演示包（U 盘，零网络零服务器）

不依赖服务器、不依赖网络、不依赖安装——只依赖一个浏览器。

```bash
cd FTAS
.venv/bin/python scripts/export_static_demo.py     # 生成 demo_static/
```

把整个 `demo_static/` 目录（约 4–5 MB）拷进 U 盘，到现场**双击 `index.html`** 即可：
三张图 + 团队统计对比 + 核心球员表 + 中文战术分析，顶部按钮可切换比赛。

注意事项：
- **必须整个目录一起拷贝**：页面用相对路径引用 `figures/` 下的图片。
- 数据来自 `data/cache/` 中已生成的结果，是**预生成快照**，不调用模型、不联网。
- 想增加可选比赛：先运行 `scripts/prefetch.py` 补齐缓存，再重新导出。
- 重复运行导出脚本是安全的（目录内 `.ftas-demo-static` 标记文件用于识别并清理旧产物）。

### 10.3 备用：手机热点 + 手机浏览器

前端已做响应式（断点 860px），手机浏览器可直接打开服务器地址演示。
适合服务器可达、但教室电脑不便使用的情况。

### 10.4 录屏备份（强烈建议）

提前录一段 3–5 分钟的完整演示视频，存 **U 盘 + 云盘 + 手机** 三份。
任何环节彻底失效时，播放录屏配合架构讲解，仍可完成答辩。

### 10.5 现场检查清单

| 时间 | 动作 |
|---|---|
| 答辩前 1–2 天 | 到答辩场地实测服务器可达性（校园网 + 手机热点）；生成离线包；导出录屏 |
| 答辩前 1 小时 | 确认服务器在跑、离线包已拷入 U 盘、录屏可播放 |
| 答辩前 10 分钟 | 用教室电脑打开一次页面，确认能出图 |
| 现场故障 | 打不开服务器 → 换手机热点；服务器不通 → 切 10.2 离线包；全挂 → 播 10.4 录屏 |

> 若你有可携带的电脑，也可本机 `docker compose up -d`（或用空 Key 走缓存模式）
> 后访问 `localhost:8000`，效果与服务器一致。

---

## 11. 常见故障排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| `curl localhost:8000/api/health` 无响应 | 容器没起来 / 端口被占 | `docker compose ps` 看状态；`docker compose logs ftas` 看日志；`lsof -i:8000` 查占用 |
| 页面能开，但 `/api/analyze` 返回 502 | 网络被断 / Key 失效 / 该场缓存缺失 | 断网时用空 Key 走缓存；`docker compose logs ftas` 看具体错误 |
| `llm_configured:false` | `.env` 没复制或 Key 为空 | `cp .env.example .env` 并填 `OPENAI_API_KEY`，然后 `docker compose up -d --force-recreate` |
| 构建时 `apt-get update` 超时 | Debian 官方源慢 | 按第 5 节传入 `--build-arg APT_MIRROR=https://mirrors.ustc.edu.cn` |
| 构建时 pip 安装失败 | PyPI 官方源慢 | 传入 `--build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple` |
| 外网访问不了 8000 | 安全组/防火墙没放行 | 见第 7 节 |
| 服务器重启后容器没自启 | Docker 服务未 enable | `sudo systemctl enable docker` |
| 图表中文显示方块 | 镜像内缺中文字体 | 确认用本项目 Dockerfile 构建（已装 fonts-noto-cjk），不要用旧镜像 |
| 8000 端口被旧容器占用 | 旧版镜像容器在跑 | `docker compose up -d --force-recreate` 重建替换 |
| `smoke_test.py` 报 FAIL | 缓存文件缺失/损坏 | 重新运行 `.venv/bin/python scripts/prefetch.py` 补齐 |

---

## 12. 常用运维命令速查

```bash
docker compose ps                      # 查看容器状态
docker compose logs -f ftas            # 持续查看日志
docker compose restart ftas            # 重启
docker compose up -d --force-recreate  # 重建容器（改 .env 后必须用这个）
docker compose down                    # 停止并删除容器（数据卷不受影响）
docker compose build --no-cache        # 强制重新构建镜像
curl localhost:8000/api/health         # 健康检查
```

> 答辩结束后如需彻底清理：`docker compose down && docker rmi $(docker images -q 'ftas*')`
