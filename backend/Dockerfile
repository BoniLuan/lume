FROM python:3.14.7-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

RUN addgroup --system --gid 10001 lume \
    && adduser --system --uid 10001 --ingroup lume --home /nonexistent lume

COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN uv sync --frozen --no-dev

USER 10001:10001

FROM base AS production
CMD ["uvicorn", "lume.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM base AS development
USER root
RUN uv sync --frozen --group dev
COPY --chown=10001:10001 tests ./tests
USER 10001:10001
