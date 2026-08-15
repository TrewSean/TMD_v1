# TMD Markets

Always-on markets dashboard: Australian and US rates, equities, FX, commodities.
No AI at run time. Code pulls data on a schedule, stores it with full history, a
website reads the database.

```
GitHub Actions (cron)  ──►  ingest/  (Python)  ──►  Postgres (Supabase)  ──►  web/ (Next.js on Netlify)
worker/ (Alpaca stream) ───────────────────────────►        ▲
                                                             └── Realtime → browser
```

| Folder | What | Status |
|---|---|---|
| `ingest/` | Python package `tmd`: adapters, catalogue, calcs, CLI, migrations | Phase 0 done |
| `web/` | Next.js site | Phase 2 |
| `worker/` | Always-on streaming worker (Alpaca) | Phase 1d |
| `docs/` | Architecture, data sources, runbook | |
| `.github/workflows/` | CI + scheduled ingest | |

Start with `CLAUDE.md` (rules) and `PLAN.md` (what's next).

## Quick start (ingest)

```bash
cd ingest
pip install -e ".[dev]"
ruff check . && pytest
python -m tmd.jobs.cli catalog
python -m tmd.jobs.cli run fixings --dry-run       # live fetch, prints, no DB
# with a database:
export DATABASE_URL=postgresql://...               # PowerShell: $env:DATABASE_URL="..."
python -m tmd.jobs.cli migrate
python -m tmd.jobs.cli run fixings
python -m tmd.jobs.cli health
```
