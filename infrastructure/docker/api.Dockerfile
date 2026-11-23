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
COPY apps/api ./apps/api
COPY alembic.ini ./
ENV PATH="/srv/proofscan/.venv/bin:${PATH}" PYTHONPATH="/srv/proofscan/apps/api" PYTHONDONTWRITEBYTECODE=1
USER proofscan
EXPOSE 8000
CMD ["uvicorn", "proofscan.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
