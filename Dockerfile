FROM python:3.11-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/
COPY scripts /app/scripts
COPY templates /app/templates
COPY vocabulary_fr_sample.csv /app/vocabulary_fr_sample.csv
COPY docs/serial-episode-tentpole-*.md docs/serial-season-finale.md /app/docs/
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

RUN pip install --no-cache-dir . \
    && python -m spacy download fr_core_news_sm \
    && chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENV PORT=8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
