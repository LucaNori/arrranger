FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/app/.venv
RUN uv venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY arrranger_sync.py .
COPY arrranger_scheduler.py .
COPY arrranger_instances.json.example .
COPY arrranger_logging.py .
COPY . /app
RUN mkdir -p /config /data
ENV CONFIG_DIR=/config
ENV DATA_DIR=/data
ENV CONFIG_FILE=/config/arrranger_instances.json
ENV DB_NAME=/data/arrranger.db
RUN chmod -R 755 /app /config /data
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uv", "run", "arrranger_sync.py"]