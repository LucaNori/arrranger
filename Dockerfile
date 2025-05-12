FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ARG VENDOR
ARG APP_COMMIT_SHA
WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tzdata \
    curl \
    unzip \
    git \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/app/.venv
RUN uv venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy project files
COPY pyproject.toml uv.lock /app/
COPY src/ /app/src/
COPY main.py /app/
COPY arrranger_instances.json.example /app/

# Set commit SHA (if provided) or use a default value
RUN if [ -n "$APP_COMMIT_SHA" ]; then \
      echo "$APP_COMMIT_SHA" > /app/ARRRANGER_COMMIT_SHA.txt; \
    else \
      echo "unknown" > /app/ARRRANGER_COMMIT_SHA.txt; \
    fi

RUN if [ -n "$APP_COMMIT_SHA" ]; then \
      echo "$APP_COMMIT_SHA" > /tmp/commit_sha; \
    else \
      cat /app/ARRRANGER_COMMIT_SHA.txt > /tmp/commit_sha; \
    fi && \
    COMMIT_SHA_VALUE=$(cat /tmp/commit_sha) && \
    echo "ARRRANGER_COMMIT_SHA_ENV=$COMMIT_SHA_VALUE" >> /etc/environment && \
    echo "export ARRRANGER_COMMIT_SHA_ENV=$COMMIT_SHA_VALUE" >> /etc/profile

ENV ARRRANGER_COMMIT_SHA_ENV=unknown

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f "/app/uv.lock" ]; then \
        echo "Using uv.lock file" && \
        uv sync --frozen --no-install-project --no-dev; \
    else \
        echo "No uv.lock file found, running without --frozen" && \
        uv sync --no-install-project --no-dev; \
    fi

RUN mkdir -p /config /data
ENV CONFIG_DIR=/config
ENV DATA_DIR=/data
ENV CONFIG_FILE=/config/arrranger_instances.json
ENV DB_NAME=/data/arrranger.db

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f "/app/uv.lock" ]; then \
        echo "Using uv.lock file" && \
        uv sync --frozen --no-dev; \
    else \
        echo "No uv.lock file found, running without --frozen" && \
        uv sync --no-dev; \
    fi

RUN apt-get purge -y --auto-remove git curl unzip \
    && rm -rf /var/lib/apt/lists/* \
    && chmod -R 755 /app /config /data \
    && chown -R root:root /app \
    && chown -R nobody:nogroup /config /data

USER nobody:nogroup
WORKDIR /config
VOLUME ["/config", "/data"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uv", "run", "main.py"]