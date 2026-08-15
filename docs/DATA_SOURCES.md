# Data sources

Tier: primary = publisher of record; feed = licensed market data feed; aggregator =
delayed / unofficial. Verified = live dry-run succeeded from a real environment.

| Adapter | Publisher | What | Cadence | Tier | Verified |
|---|---|---|---|---|---|
| `rba_f1` | RBA, table F1 CSV | cash rate target, AONIA, BBSW 1/3/6m, OIS 1/3/6m | daily ~16:30 Syd | primary | 15 Aug 2026 |
| `rba_f2` | RBA, table F2 CSV | ACGB 2/3/5/10y, 10y indexed | daily ~16:30 Syd | primary | 15 Aug 2026 |
| `ust_par` | US Treasury, daily par yield CSV | 1m to 30y par curve (13 tenors) | daily ~15:30 NY | primary | 15 Aug 2026 |
| `nyfed_rates` | NY Fed markets API (JSON) | SOFR, EFFR (+ target range in meta) | daily 08:00 NY for T-1 | primary | 15 Aug 2026 |
| `alpaca` + `worker/` | Alpaca Market Data (IEX or delayed SIP) | SPY QQQ DIA IWM TLT IEF GLD USO, NVDA AAPL MSFT AMD TSLA AVGO TSM; 1-min bars | streaming (worker) + polling fallback | feed | pending Sean's keys |
| `yfinance` | Yahoo Finance via yfinance | ASX200, SPX, NDX, DJIA, VIX, AUDUSD, DXY, WTI, Brent, gold, copper, CBOE 5/10/30y | 10-20 min delayed | aggregator | 15 Aug 2026 (from GitHub Actions) |
| `asx_rate_tracker` | ASX, RBA Rate Tracker data files | 30-day interbank futures implied yield strip (18 contracts), front settlement, ASX expected cash rate / change / probability | EOD, T-1 | primary | 15 Aug 2026 |
| `fed_funds_futures` | CME via Yahoo (`ZQ<code><yy>.CBT`) | 30-day fed funds futures strip, 18 rolling contract months, prices | EOD, T-1 | aggregator | 15 Aug 2026 |

## Derived, not fetched

| Series | Computed by | From | Tier |
|---|---|---|---|
| `au.rba.implied.n1..n12` | `tmd derive` -> `calcs/implied_path.py` | ASX IB strip + AONIA + `meetings.yaml` | primary |
| `us.fed.implied.n1..n12` | `tmd derive` -> `calcs/implied_path.py` | ZQ strip + EFFR + `meetings.yaml` | aggregator |

Keyed by meeting *position* (`n1` = after the next meeting), because series ids are
permanent and meetings roll. `meta` carries `meeting_date`, `effective_date`, `step_bp`,
`change_from_current_bp`, `cumulative_moves`, `weight`, `weak` and the whole-fit
`fit_rms_bp`. Tier follows the weakest input, which is why the Fed path is `aggregator`.
Runs as a `derive` step after `ingest` in the `ingest-fixings` workflow, and records into
`ingest_runs` as `derive_rba` / `derive_fed` so `adapter_health` covers it too.

## Reference config, not a source

| File | What | Review |
|---|---|---|
| `catalog/meetings.yaml` | RBA and FOMC decision/effective dates, rest of 2026 + all 2027 | Yearly, when each bank publishes its 2028 schedule |

Both banks publish schedules only as HTML, so per CLAUDE.md these are transcribed into
versioned config rather than scraped. They are not Observations: a scheduled date is not
a measurement, and `validate.py` rejects anything more than two days in the future.

## Planned (see PLAN.md)

| Adapter | Publisher | Notes |
|---|---|---|
| `fred` | St Louis Fed | misc history, needs free key |
| `abs_calendar`, `bls_bea_calendar` | publishers | release dates |

## Blocked, no machine-readable source (checked 15 Aug 2026)

| Adapter | What exists | Why blocked |
|---|---|---|
| `asx_bbsw` | 10-day BBSW history as **PDF**; a daily-volume **xlsx** (volumes, not rates); live rates behind a paid ASX subscription | No free CSV/JSON/API for the rates themselves. BBSW 1/3/6m already arrive via `rba_f1` at primary tier, one day in arrears |
| `rba_calendar` | Meeting dates in an **HTML table** on `rba.gov.au/schedules-events/board-meeting-schedules.html` | No CSV/JSON/iCal. RBA's RSS feeds carry past media releases, not the forward schedule |
| `fomc_calendar` | Meeting dates in **HTML** on `federalreserve.gov/monetarypolicy/fomccalendars.htm` | No CSV/JSON/iCal. The `/feeds/*.xml` feeds are past press releases; the NY Fed markets API has no FOMC endpoint |

Partial cover: `asx_rate_tracker` observations carry `meta.rba_mtng_dt` and
`meta.nxt_rba_mtng_dt`, so the last and next RBA meeting dates *are* available
machine-readably even though the full schedule is not.

## Known quirks

- ASX Rate Tracker: the three data files are named `.csv` and served as `text/csv`, but
  the body is JSON. The adapter reads them as text and `json.loads` them.
- ASX Rate Tracker: the implied strip is stored by contract *position* (`m1` .. `m18`),
  not calendar month, because series ids are permanent and contracts roll. The contract
  each observation refers to is in `meta.expiry_month`.
- `fed_funds_futures` uses the same position keying, and stores only the *latest* close
  per contract: a position means a different contract either side of a month roll, so
  back-dating it would file one contract's price under another's name.
- Yahoo returns ZQ closes as widened float32 (`96.36750030517578` for a `96.3675` tick),
  so the adapter quantises to 4dp. ZQ ticks are 0.0025/0.005, both exact at 4dp.
- Deferred ZQ months are often unquoted on Yahoo (Jan-28 was empty on 15 Aug 2026). The
  adapter logs them and stores nothing rather than inventing a price.
- RBA F1: some columns lag one day (e.g. cash rate row for "today" is empty until tomorrow).
  The adapter simply stores nothing for empty cells.
- Treasury CSV is per calendar year; adapter fetches current and previous year when the
  lookback crosses 1 Jan.
- NY Fed rates are for the *previous* business day; `ts` is set to that day 17:00 NY.
- yfinance: one batched `yf.download(period="1d", interval="5m")`; `ts` is the last bar's
  timestamp. Per-ticker `fast_info` calls returned nothing from GitHub runners; stay batched.
