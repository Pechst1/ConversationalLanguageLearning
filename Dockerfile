FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/
COPY scripts /app/scripts
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

RUN pip install --no-cache-dir . \
    && python -m spacy download fr_core_news_sm \
    && chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENV PORT=8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
