# saleor test runner. Build context: a saleor clone (only pyproject.toml and uv.lock are copied).
# Run inside a Postgres container's network namespace so the DB is on 127.0.0.1 (saleor's pytest-socket allow-list).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev libmagic1 git shared-mime-info \
    && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir uv
WORKDIR /deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --all-groups
ENV PATH=/deps/.venv/bin:$PATH VIRTUAL_ENV=/deps/.venv PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=postgres://saleor:saleor@127.0.0.1/saleor SECRET_KEY=test
WORKDIR /repo
ENTRYPOINT ["pytest", "-p", "no:cacheprovider", "-n", "0", "-q"]
