# Runbook

## Secrets (GitHub → repo → Settings → Secrets and variables → Actions)

| Secret | Used by | Where to get it |
|---|---|---|
| `DATABASE_URL` | all ingest workflows | Supabase → Project → Connect → "Session pooler" URI (port 5432). Replace `[YOUR-PASSWORD]`. |
| `ALPACA_API_KEY`, `ALPACA_API_SECRET` | worker (Phase 1d) | Alpaca dashboard → API keys |
| `FRED_API_KEY` | `fred` adapter (Phase 1b) | fred.stlouisfed.org → My Account → API keys |

Never paste these into chat, code, or issues.

## First-time production wiring

1. Add `DATABASE_URL` secret.
2. Actions → `migrate` → Run workflow. Check Supabase Table Editor shows `series`,
   `observations`, `ingest_runs`.
3. Actions → `ingest-fixings` → Run workflow. Check `latest_observations` view has rows.
4. Actions → `ingest-intraday` → Run workflow. If yfinance fails from GitHub runners,
   note it in PLAN.md Open questions.

## Daily health

`python -m tmd.jobs.cli health` (needs `DATABASE_URL`), or query `adapter_health` in
Supabase. Any adapter with status `error` twice in a row deserves a look at the
workflow log (Actions tab → the run → "ingest" step).

## Common failures

- **Adapter error "format changed?"**: the publisher changed a CSV header. Save a fresh
  sample to `tests/fixtures/`, fix the parser, add a test for the new shape.
- **`prepared statement` errors**: you are on the transaction pooler (port 6543). Either
  switch `DATABASE_URL` to the session pooler (5432) or keep `prepare_threshold=None`
  (already set in `store.py`).
- **Actions minutes exhausted**: repo is private and intraday cadence is too high. Make
  the repo public, or reduce `ingest-intraday` cron, or move polling to the worker.
- **Cron did not fire on time**: GitHub delays scheduled runs at busy times. The `as_of`
  on rows tells the truth. Not a bug.

## Local development

```
cd ingest
pip install -e ".[dev]"
cp .env.example .env         # fill DATABASE_URL if you want real writes
ruff check . && pytest
python -m tmd.jobs.cli run fixings --dry-run
```
