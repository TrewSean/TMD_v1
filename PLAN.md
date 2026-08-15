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
- [x] `asx_rate_tracker`: ASX 30-day interbank cash rate futures implied RBA path
      (15 Aug 2026). Three published files under `/content/dam/asx/data/`
      (`yield_curve`, `dynamic_text`, `market_exp`), named `.csv` and served as
      `text/csv` but with JSON bodies. 22 series: the 18-contract implied yield strip
      stored by contract position, plus front settlement, ASX expected cash rate,
      expected change, and probability of a move. Live dry-run: 36 obs, status ok.
- [!] `asx_bbsw`: BLOCKED, no machine-readable rate file. ASX publishes the 10-day BBSW
      history only as a PDF (`/data/benchmarks/bbsw-10-day-rolling-history.pdf`); the
      only xlsx (`asx-interbank-bbsw-daily-volume-report.xlsx`) is *volumes*, not rates;
      live rates sit behind a paid ASX benchmark subscription. Not scraping the PDF.
      BBSW 1/3/6m already arrive via `rba_f1` at primary tier, one business day late,
      so the gap is latency only. Revisit if ASX ever publishes a rates CSV/JSON.
- [ ] `fred`: FRED API for series without a cleaner primary (e.g. DXY history, breakevens).
      Needs a free API key -> `FRED_API_KEY` secret.
- [ ] `fed_funds_futures`: CME ZQ strip via yfinance contract symbols (`ZQU26.CBT` ...)
      with a rolling contract generator; tier aggregator, delayed
- [ ] `au_bond_futures`: ASX 3yr/10yr bond futures (YT/XT) if any free delayed source is
      machine-readable; otherwise `[!]` blocked pending IBKR (Phase 4)
- [ ] `abs_calendar`, `bls_bea_calendar`: release calendars into a `calendar_events`
      table (new migration `0003_calendar.sql`)
- [x] `rba_calendar`, `fomc_calendar`: meeting dates as versioned config
      `catalog/meetings.yaml` + `catalog/meetings.py` loader (15 Aug 2026). RBA and FOMC
      decision/effective dates for the rest of 2026 and all of 2027, transcribed from the
      two published schedules (URLs in the file header). The loader raises `MeetingsError`
      on out-of-order dates, effective <= decision, duplicates, or a decision on the wrong
      weekday, so a transcription slip fails CI instead of shifting an implied path.
      REVIEW YEARLY: extend when the RBA publishes 2028 (mid-2027) and the Fed publishes
      its 2028 tentative calendar (usually with the June FOMC).
- [ ] Optional cross-check later: FRED `fred/release/dates` API can confirm FOMC dates once
      the `fred` adapter exists.

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
- (resolved 15 Aug) ASX Rate Tracker: yes, there is a machine-readable endpoint. The page
  is a widget fed by `https://www.asx.com.au/content/dam/asx/data/{yield_curve,dynamic_text,
  market_exp}.csv`. They are JSON despite the `.csv` name and the `text/csv` header, so the
  adapter reads text and `json.loads`. If ASX ever makes the extension honest, the adapter
  raises at the parse rather than storing nonsense.
- `asx_rate_tracker` catalogues 18 strip contracts because that is what ASX lists today. If
  ASX ever lists a 19th, position `m19` is not in the catalogue, so the runner records a
  "not in catalogue" note and marks the run `partial` rather than dropping it silently.
  Watch `ingest_runs.notes` for that; the fix is one more catalogue line.
- ASX's `Ftre_Cash_Rate_Change` (-0.25) and `Prob_Change` (0 for all 15 days) disagree with
  each other in the 13 Aug file. We store both verbatim, as published, and do no arithmetic
  in the adapter. Worth understanding what ASX means by each before either is put on a tile.
- Both meeting calendars are blocked on format, not on effort. If a licensed calendar feed
  ever gets added, the `calendar_events` table is the prerequisite (see 1b).
