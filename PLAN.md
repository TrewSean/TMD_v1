# PLAN.md, the living task list

Rules: work top to bottom within the current phase. Tick items only when verified
(tests green, live dry-run shown). Add discovered work as new unchecked items with a
reason. Move questions to "Open questions" rather than guessing.

Legend: `[ ]` todo, `[x]` done, `[~]` in progress, `[!]` blocked (say why).

## Phase 0, scaffolding (DONE 15 Aug 2026)

- [x] Repo layout: `ingest/`, `web/`, `worker/`, `docs/`, `.github/workflows/`
- [x] Core model: `Series`, `Observation`, `IngestResult`
- [x] `SourceAdapter` interface and registry
- [x] Series catalogue (`series.yaml`) with loader and consistency tests
- [x] `Store` interface: `MemoryStore` (tests) and `PostgresStore` (psycopg3, upserts)
- [x] Migrations `0001_init` (series, observations, ingest_runs, views) and
      `0002_realtime_and_rls` (Supabase read-only anon policies + Realtime publication)
- [x] Runner with validation, per-adapter error isolation, `ingest_runs` logging
- [x] CLI: `tmd run|migrate|catalog|health`
- [x] Adapters live-verified: `rba_f1`, `rba_f2`, `ust_par`, `nyfed_rates`
- [x] Adapter live-verified from GitHub Actions (15 Aug): `yfinance`
- [x] `calcs/curves.py` as the calc template, with tests
- [x] CI workflow (ruff, pytest, migration smoke on Postgres service)
- [x] Scheduled workflows: `ingest-fixings`, `ingest-intraday`, `migrate`
- [x] CLAUDE.md, PLAN.md, README, docs

## Phase 1, data layer complete on free sources

### 1a. Wire production
- [x] Sean adds `DATABASE_URL` (Supabase session pooler URI) to GitHub Actions secrets (15 Aug)
- [x] Run `migrate` workflow by hand; confirm tables exist in Supabase Table Editor (15 Aug)
- [x] Run `ingest-fixings` by hand; confirm rows in `latest_observations` (15 Aug, 776 rows)
- [x] Run `ingest-intraday` by hand; `yfinance` works from Actions after switching to a
      single batched download (per-ticker `fast_info` calls returned nothing). 14/14 tickers.
- [ ] Decide: make repo public (unlimited Actions minutes) or keep private and reduce
      intraday cadence. Reason: private repos get 2,000 min/month; current schedule ~1,500.

### 1b. Remaining primary sources
- [ ] `asx_rate_tracker`: ASX 30-day interbank cash rate futures implied RBA path
      (EOD, from ASX's published data; check for a JSON/CSV endpoint before scraping)
- [ ] `asx_bbsw`: ASX BBSW daily file (cross-check vs RBA F1 which lags a day)
- [ ] `fred`: FRED API for series without a cleaner primary (e.g. DXY history, breakevens).
      Needs a free API key -> `FRED_API_KEY` secret.
- [ ] `fed_funds_futures`: CME ZQ strip via yfinance contract symbols (`ZQU26.CBT` ...)
      with a rolling contract generator; tier aggregator, delayed
- [ ] `au_bond_futures`: ASX 3yr/10yr bond futures (YT/XT) if any free delayed source is
      machine-readable; otherwise `[!]` blocked pending IBKR (Phase 4)
- [ ] `abs_calendar`, `bls_bea_calendar`: release calendars into a `calendar_events`
      table (new migration `0003_calendar.sql`)
- [ ] `rba_calendar`, `fomc_calendar`: meeting dates (needed by implied path calc)

### 1c. Calcs
- [x] `calcs/implied_path.py`: meeting-by-meeting implied policy rate from a futures
      strip (monthly-average contracts, ridge least-squares across meeting boundaries,
      weak-node flag, realised front-month days). Exact on synthetic strips. (15 Aug)
- [x] `calcs/changes.py`: 1d / 1w / 1m / 3m / 1y / YTD changes, bp for rates, % otherwise (15 Aug)
- [x] `calcs/curves.py`: `interpolate_missing` linear-in-years, flagged, no extrapolation (15 Aug)
- [ ] Wire calcs into a scheduled job that writes derived series (e.g. `au.rba.implied.<meeting>`,
      `us.fed.implied.<meeting>`, `*.chg_1d`) once `asx_rate_tracker`, `fed_funds_futures`,
      `rba_calendar` and `fomc_calendar` adapters exist (depends on 1b).

### 1d. Streaming worker (Alpaca)
- [ ] `worker/`: Python process using `alpaca-py` websocket (IEX feed) for a configured
      list of US ETFs/stocks -> writes bars/quotes into `observations` (new series with
      tier `feed`, frequency `tick`); throttle writes to 1/min per symbol
- [ ] Dockerfile + deploy to Fly.io or Railway free tier; `ALPACA_API_KEY/SECRET`,
      `DATABASE_URL` as env vars there
- [ ] Health row in `ingest_runs` every 5 min so the site can show "stream alive"

## Phase 2, web app
- [ ] `web/`: Next.js (App Router, TypeScript), Supabase JS client, Tailwind
- [ ] Pages: Overview (headline tiles), Rates desk (AU/US, curves, implied paths),
      Equities and commodities, Calendar, Sources and health
- [ ] Every tile shows value, change, `as_of`, tier badge
- [ ] Realtime subscription for tick/intraday series
- [ ] Deploy to Netlify (site: tmd-markets); env `NEXT_PUBLIC_SUPABASE_URL`, `..._ANON_KEY`
- [ ] Charts: history per series with 1m/3m/1y/max ranges

## Phase 3, hardening
- [ ] Alerting: failed adapter 2x in a row -> GitHub issue opened automatically
- [ ] Data retention policy for tick data (downsample to 1-min after 30 days)
- [ ] Backfill job: `tmd backfill <adapter> --since 2015-01-01`

## Phase 4, live rates (paid) and personal layer
- [ ] IBKR gateway on a VPS (ASX24 A$21.50/mo, CME L1 US$1.55/mo) or Databento CME
- [ ] Personal layer as a private route (calendar, inbox) if still wanted

## Open questions
- (resolved 15 Aug) Yahoo works from GitHub runners with batched `yf.download`; per-ticker
  `fast_info` returned nothing. Keep the adapter batched.
- ASX Rate Tracker: is there a stable machine-readable endpoint, or only the HTML page?
