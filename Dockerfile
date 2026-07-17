# ═══════════════════════════════════════════════════════════
# GracyBot — Docker 构建（Ubuntu 26.04 Resolute Raccoon + Python 3.14）
# ═══════════════════════════════════════════════════════════

# ─── Stage 1: build ──────────────────────────────────────
FROM ubuntu:26.04 AS builder

LABEL stage="builder"

# 阿里源
RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null; \
    sed -i 's/ports.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null; \
    true

# Python 3.14 + 构建工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 验证 Python 版本 >= 3.11
RUN python3 --version

# 创建虚拟环境
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

# pip 换阿里源
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

WORKDIR /build

# 先拷依赖定义，利用 Docker 缓存
COPY pyproject.toml MANIFEST.in ./
COPY gracybot/ gracybot/
COPY res/ res/
COPY graci.py bot.py ./

# 安装 GracyBot + 全部依赖
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir ".[all]"

# Playwright 浏览器（search 功能，无则降级）
RUN python -m playwright install chromium 2>/dev/null || true


# ─── Stage 2: runtime ────────────────────────────────────
FROM ubuntu:26.04 AS runtime

LABEL org.opencontainers.image.title="GracyBot"
LABEL org.opencontainers.image.description="个性化定制化 QQ 机器人框架"
LABEL org.opencontainers.image.url="https://github.com/MiniYv/GracyBot"
LABEL org.opencontainers.image.source="https://github.com/MiniYv/GracyBot"

# 阿里源 + 运行时最小系统
RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null; \
    sed -i 's/ports.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null; \
    apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    tini \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 拷 venv
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"

# 项目文件（只读）
WORKDIR /gracybot
COPY --from=builder /build/gracybot/ ./gracybot/
COPY --from=builder /build/res/ ./res/
COPY --from=builder /build/graci.py ./graci.py
COPY --from=builder /build/bot.py ./bot.py
COPY --from=builder /build/pyproject.toml ./

# 入口脚本
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# 持久化目录
VOLUME ["/gracybot/storage", "/gracybot/plugins_custom"]

# GracyUI 面板端口
EXPOSE 5090

ENTRYPOINT ["tini", "--", "docker-entrypoint.sh"]
CMD ["gracy", "run"]
