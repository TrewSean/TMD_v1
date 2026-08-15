# worker: Alpaca streaming -> Postgres

An always-on Python process. Subscribes to Alpaca 1-minute bars for the `alpaca` series in
the shared catalogue and writes them to the same `observations` table the scheduled jobs
use. Heartbeats to `ingest_runs` as adapter `alpaca_stream` every 5 minutes.

Same symbols, same `bar_to_observation`, as the `alpaca` REST adapter in `ingest/`, which
GitHub Actions can run as a polling fallback if this process is down.

## Run locally

```
cd worker
pip install -e ../ingest -e ".[dev]"
# .env in ingest/ or exported: DATABASE_URL, ALPACA_API_KEY, ALPACA_API_SECRET, ALPACA_FEED
tmd-worker
```

Off US market hours nothing arrives; that is normal. Ctrl+C flushes and exits.

## Deploy (Fly.io, free tier is enough)

From the repo root:

```
fly auth signup            # or fly auth login
fly launch --no-deploy --copy-config --config worker/fly.toml --name tmd-worker --region syd
fly secrets set --config worker/fly.toml DATABASE_URL="..." ALPACA_API_KEY="..." ALPACA_API_SECRET="..." ALPACA_FEED=iex
fly deploy --config worker/fly.toml
fly logs --config worker/fly.toml
```

Railway alternative: new project from the GitHub repo, set the root to the repo, it picks
up `worker/railway.json`; add the same four variables in the service settings.

## Feed choice

`iex` (default): real-time, IEX-venue-only volume. `delayed_sip`: full consolidated tape,
15 minutes late. Both are on the free plan. `sip` real-time is paid.
