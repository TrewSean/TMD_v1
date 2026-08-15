# CLAUDE.md, working rules for this repository

You are working on **TMD Markets**, Sean's markets dashboard. Read this file fully before
touching anything. It exists so you can work for long stretches without supervision and
still produce something Sean can trust.

## What this project is

An always-on markets dashboard (Australian and US rates, equities, FX, commodities).
Three layers, each independently deployable:

1. `ingest/`  Python. Scheduled jobs pull data from sources, validate, write to Postgres.
2. Postgres on Supabase. The single source of truth. Schema in `ingest/migrations/`.
3. `web/`     Next.js on Netlify. Reads the DB (and subscribes to Realtime). Phase 2.

`worker/` (Phase 1b) is a small always-on process for streaming feeds (Alpaca).

**There is no AI at run time.** No LLM calls anywhere in the pipeline or site. You write
code; the code runs on its own. Do not add narrative generation, summarisation, or any
model calls unless PLAN.md explicitly says a phase has been opened for it.

## Non-negotiable design rules

- **Every number is an Observation of a Series.** Series live in
  `ingest/src/tmd/catalog/series.yaml`. If a number is not in the catalogue, it does not
  exist. Add to the catalogue first, then write the adapter.
- **Series ids are permanent.** Never rename. Set `active: false` and add a new id.
- **One source = one adapter** in `ingest/src/tmd/sources/`, subclassing `SourceAdapter`,
  registered in `sources/__init__.py`. Adapters fetch and normalise only. No arithmetic,
  no DB access, no cross-source logic.
- **Calcs are pure functions** in `ingest/src/tmd/calcs/`. Plain inputs, plain outputs,
  no I/O, every function tested with fixed inputs. See `calcs/curves.py` for the pattern.
- **Store history, never overwrite it.** Writes are upserts on `(series_id, ts)`.
- **Timestamps are UTC and timezone-aware.** `ts` = what the value is for; `as_of` = when
  we fetched it. Both always set.
- **Primary source first.** Publisher of record (RBA, Treasury, NY Fed, exchange) beats a
  licensed feed beats an aggregator (yfinance). Record the tier honestly in the catalogue.
- **Never guess a figure.** If a source is missing a value, store nothing. The site shows
  a gap; it never shows an invented number.
- **Secrets only via environment variables.** Never in code, YAML, tests, fixtures, or
  commit messages. `ingest/.env` is git-ignored; CI uses GitHub Actions secrets.
- **Migrations are append-only.** New file `NNNN_name.sql`, never edit an applied one.
- **Config is data.** Tickers, tenors, schedules go in YAML or workflow files, not code.

## How to work (autonomy protocol)

1. Read `PLAN.md`. Pick the first unchecked task in the current phase unless told otherwise.
2. Before coding, write down (in your reply or a scratch note) what "done" looks like for
   that task, including which test will prove it.
3. Implement in small commits. Conventional prefixes: `feat:`, `fix:`, `test:`, `docs:`,
   `chore:`, `refactor:`.
4. **Verify before you declare done.** From `ingest/`:
   ```
   ruff check . && ruff format --check . && pytest
   python -m tmd.jobs.cli run <adapter> --dry-run     # for adapters: prove it fetches live
   ```
   If a live source cannot be reached from your environment, say so explicitly; do not
   claim it works.
5. Update `PLAN.md`: tick the task, add any follow-ups you discovered as new unchecked
   items with a one-line reason.
6. If a task turns out to be impossible or wrong, do not force it. Write what you found
   under "Open questions" in PLAN.md and move to the next task.
7. **Branch and PR, always.** Work on a branch named `feat/<thing>`, `fix/<thing>` or
   `chore/<thing>`. Push it and open a pull request against `main` with a short summary and
   the verification you ran. Merge only when CI is green. Never commit directly to `main`
   except for trivial doc typos. `main` is what the scheduled jobs run, so it must always be
   deployable.
8. Never push a red CI. Never merge a PR into `main` if CI is failing.

## Adding a data source (the most common task)

1. Confirm the source publishes machine-readable data (CSV/JSON/API). Record the URL,
   update cadence, and licence in the adapter docstring.
2. Add series to `catalog/series.yaml` (id, unit, tier, source, source_ref).
3. Save a small real sample as `ingest/tests/fixtures/<source>_sample.<ext>`.
4. Write `sources/<source>.py` with a pure `parse_*()` function and a thin
   `SourceAdapter.fetch()`. Register it in `sources/__init__.py`.
5. Test the parser against the fixture. Then `tmd run <source> --dry-run` live.
6. Add the adapter to a group in `jobs/runner.py` (`fixings`, `intraday`, ...).
7. Note it in `docs/DATA_SOURCES.md`.

## Adding a calc

Pure function in `calcs/`, tests with hand-checked expected values, docstring stating the
method and its known error bounds. If it depends on market conventions (day counts,
settlement, contract specs), cite the spec in the docstring.

## Things that look tempting but are wrong here

- Scraping HTML pages when a CSV/JSON exists. Find the file.
- "Just hard-coding" a ticker list in Python. It goes in `series.yaml`.
- Adding pandas everywhere. Parsers should be plain `csv`/`json`; pandas only where a
  library (yfinance) hands you a frame.
- Catching exceptions silently. The runner records failures in `ingest_runs`; let it.
- Writing to the DB from an adapter or a calc.
- Adding an LLM call.

## Environment

- Python 3.11+, `pip install -e ".[dev]"` inside `ingest/`.
- Local Postgres for tests is optional; unit tests do not need one. CI spins one up.
- `DATABASE_URL` for real runs. Supabase: use the **Session pooler** URI (IPv4, port 5432);
  GitHub Actions runners cannot reach the IPv6-only direct connection.
- Windows: use PowerShell or WSL. Paths in this repo are POSIX; keep them that way.

## Contacts and context

Owner: Sean (GitHub `TrewSean`). Sydney time zone. Building this alongside university,
so favour clear, self-verifying work over speed. When in doubt, leave a note in PLAN.md
rather than interrupting.
