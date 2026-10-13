# FTAS 运行镜像：Python 3.11-slim + 中文字体 + 非 root 用户
FROM python:3.11-slim

# pip 源（默认官方 PyPI；构建时可加 --build-arg PIP_INDEX_URL=... 覆盖）
ARG PIP_INDEX_URL=https://pypi.org/simple

# Debian 源（默认官方；构建时可加 --build-arg APT_MIRROR=... 覆盖，可含 https:// 前缀）
ARG APT_MIRROR=http://deb.debian.org

# 安装中文字体（图表中文显示）与 OpenMP 运行库
RUN sed -i "s|http://deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends fonts-noto-cjk libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户 app
RUN useradd --create-home --uid 1000 app

WORKDIR /app

# 先安装依赖，充分利用镜像层缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -i ${PIP_INDEX_URL}

# 拷贝项目代码；data/cache 由运行时卷挂载覆盖
COPY --chown=app:app . ./

# WORKDIR 由 root 创建，需把 /app 目录本身交给 app 用户（否则无法新建 outputs 等目录）
RUN chown app:app /app

# 运行时配置默认值（可用 .env 或环境变量覆盖）
# OPENAI_API_KEY 不设默认值，避免密钥进入镜像层，运行时通过环境变量注入
ENV APP_PORT=8000 \
    FTAS_CACHE_DIR=/app/data/cache \
    OPENAI_BASE_URL=https://api.deepseek.com/v1 \
    LLM_MODEL=deepseek-chat \
    LLM_TIMEOUT=60 \
    LLM_MAX_RETRIES=3 \
    RATE_LIMIT_PER_MIN=60 \
    MAX_PROMPT_CHARS=8000

# 以非 root 用户运行
USER app

EXPOSE 8000

# 启动 FastAPI 服务（容器内端口固定 8000）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
