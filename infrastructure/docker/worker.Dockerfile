FROM ghcr.io/astral-sh/uv:0.13.8 AS uv
FROM python:3.12-slim AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /srv/proofscan
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim
RUN groupadd --system proofscan && useradd --system --gid proofscan proofscan
WORKDIR /srv/proofscan
COPY --from=dependencies /srv/proofscan/.venv ./.venv
COPY apps/api/proofscan ./apps/api/proofscan
COPY apps/worker ./apps/worker
ENV PATH="/srv/proofscan/.venv/bin:${PATH}" PYTHONPATH="/srv/proofscan/apps/api:/srv/proofscan/apps/worker" PYTHONDONTWRITEBYTECODE=1
USER proofscan
CMD ["celery", "-A", "tasks:celery", "worker", "--loglevel=INFO"]
