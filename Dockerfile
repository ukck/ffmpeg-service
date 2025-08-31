# 1. 构建阶段
FROM python:3.12-alpine AS builder

# 改用中科大镜像
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.ustc.edu.cn/g' /etc/apk/repositories

# 安装构建工具和 ffmpeg
RUN apk add --no-cache ffmpeg build-base curl

WORKDIR /app
COPY pyproject.toml ./

# 改 pip 源为中科大镜像，安装 uv + 依赖
RUN pip install --no-cache-dir -i https://mirrors.ustc.edu.cn/pypi/simple uv \
    && uv pip install --system --no-cache --index-url https://mirrors.ustc.edu.cn/pypi/simple .

COPY app.py .

# 2. 运行阶段
FROM python:3.12-alpine

RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.ustc.edu.cn/g' /etc/apk/repositories \
    && apk add --no-cache ffmpeg

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY app.py .

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
