# Build context is the REPO ROOT (see fly.toml / railway.json), so both packages are visible.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY ingest/ /app/ingest/
COPY worker/ /app/worker/
RUN pip install --no-cache-dir /app/ingest && pip install --no-cache-dir /app/worker
# Runs as a long-lived process; no ports exposed.
CMD ["tmd-worker"]
