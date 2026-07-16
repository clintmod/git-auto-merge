ARG PYTHON_VERSION=3.11.6
FROM python:${PYTHON_VERSION}-alpine AS base

# upgrade first so distro security fixes land even when the base image lags
RUN apk upgrade --no-cache \
    && apk add --no-cache \
    bash \
    curl \
    jq \
    git \
    openssh \
    tzdata \
    && rm -rf /var/cache/apk/*

WORKDIR /app

FROM base AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_CACHE_DIR=/tmp/uv_cache \
    UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock /app/

# dummy sources so the project itself resolves; the editable install points
# at /app/src, which the final stage populates with the real code
RUN mkdir src && touch README.md src/git_auto_merge.py src/utils.py

RUN --mount=type=cache,target=/tmp/uv_cache uv sync --frozen --no-dev

FROM base AS final

RUN adduser -D app \
    && chown -R app:app /app

USER app

RUN mkdir -p ~/.ssh && \
    ssh-keyscan github.com >> ~/.ssh/known_hosts \
    && ssh-keyscan gitlab.com >> ~/.ssh/known_hosts \
    && ssh-keyscan bitbucket.org >> ~/.ssh/known_hosts

ENV VIRTUAL_ENV=/app/.venv/ \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY src /app/src

ENTRYPOINT ["git-auto-merge"]
