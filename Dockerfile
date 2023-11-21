ARG PYTHON_VERSION=3.11.6
FROM python:${PYTHON_VERSION}-alpine as base

RUN apk add --no-cache \
    bash \
    curl \
    jq \
    git \
    openssh \
    tzdata \
    && rm -rf /var/cache/apk/*

WORKDIR /app

FROM base as builder

RUN pip install --upgrade pip \
    && pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock /app/

RUN mkdir src && touch README.md src/git_auto_merge.py

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache/

RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --only main \
    && rm -rf $POETRY_CACHE_DIR/*

FROM base as final

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
