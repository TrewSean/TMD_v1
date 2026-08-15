# Architecture

## The one idea

Every number on the site is an **Observation** (value at a time) of a **Series** (a
catalogued thing with a unit, a source and a trust tier). Sources are pluggable
**adapters** that produce observations. **Calcs** are pure functions over observations.
The **store** is Postgres. The **site** reads the store. Nothing else talks to anything.

```
                 ┌──────────────── ingest (Python, scheduled) ────────────────┐
 RBA / Treasury  │  SourceAdapter.fetch() → validate → Store.upsert            │
 NY Fed / Yahoo ─┤  one adapter per source, registered in sources/__init__.py │
 Alpaca (worker) │  runner isolates failures, logs to ingest_runs              │
                 └───────────────────────────┬────────────────────────────────┘
                                             ▼
                          Postgres (Supabase): series, observations, ingest_runs
                          views: latest_observations, adapter_health
                          Realtime publication on observations
                                             ▼
                          web (Next.js on Netlify) reads with anon key (RLS read-only)
```

## Why these choices

- **Catalogue in YAML, not code.** Adding a ticker is a data change, reviewable in a diff,
  impossible to get "half wired": tests assert catalogue and registry agree.
- **Upsert on (series_id, ts).** Re-running a job corrects rather than duplicates.
  History is never lost; a revised fixing overwrites the same key with a new `as_of`.
- **`as_of` on every row.** The site can show staleness truthfully and the DB can be
  audited ("what did we think the 10yr was at 9am?").
- **Runner isolates adapters.** One broken source never blocks the others, and every run
  leaves a row in `ingest_runs` for the health page.
- **Postgres over anything fancier.** History, joins, views, Realtime, RLS, free tier.
- **GitHub Actions for cron.** Free, versioned next to the code, no server to babysit.
  Only the streaming worker needs an always-on host.
- **No AI at run time.** Deterministic, cheap, testable. Claude Code writes the code.

## Extending

- New source: `docs/DATA_SOURCES.md` + `CLAUDE.md` "Adding a data source".
- New calc: pure function + tests. If the site needs it precomputed, add a scheduled job
  that writes derived Series (tier `primary` if from primary inputs, tag `derived`).
- New table: new migration file. Update the RLS block in a follow-up migration.
- New site page: reads views/tables only; never computes what the pipeline should have.
