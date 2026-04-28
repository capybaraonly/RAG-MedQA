# 生产环境后端镜像
# 使用 uv 安装依赖，Python 3.12

FROM python:3.12-slim AS base

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 先复制依赖文件，利用层缓存
COPY pyproject.toml uv.lock ./

# 安装 Python 依赖（不安装项目本身，避免重复）
RUN uv sync --frozen --no-install-project --python 3.12

# 复制项目代码
COPY . .

# 设置环境变量
ENV PYTHONPATH=/app
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 9380 9381

CMD ["python", "api/ragflow_server.py"]
