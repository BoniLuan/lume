FROM python:3.14.9-slim-bookworm@sha256:945c2676dc2b18e0c1f16879244122c57c0ffede60006bf3df159c507a31bcae AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

RUN addgroup --system --gid 10001 lume \
    && adduser --system --uid 10001 --ingroup lume --home /nonexistent lume

COPY --from=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN uv sync --frozen --no-dev

USER 10001:10001

FROM base AS production
# Dependency/build tools and their caches are not needed to serve requests.
USER root
RUN rm -rf /root/.cache /bin/uv /bin/uvx \
    /usr/local/lib/python3.14/site-packages/pip \
    /usr/local/lib/python3.14/site-packages/pip-*.dist-info \
    /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.14
USER 10001:10001
CMD ["uvicorn", "lume.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM base AS development
USER root
RUN uv sync --frozen --group dev
COPY --chown=10001:10001 tests ./tests
USER 10001:10001
