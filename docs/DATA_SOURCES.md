# Data sources

Tier: primary = publisher of record; feed = licensed market data feed; aggregator =
delayed / unofficial. Verified = live dry-run succeeded from a real environment.

| Adapter | Publisher | What | Cadence | Tier | Verified |
|---|---|---|---|---|---|
| `rba_f1` | RBA, table F1 CSV | cash rate target, AONIA, BBSW 1/3/6m, OIS 1/3/6m | daily ~16:30 Syd | primary | 15 Aug 2026 |
| `rba_f2` | RBA, table F2 CSV | ACGB 2/3/5/10y, 10y indexed | daily ~16:30 Syd | primary | 15 Aug 2026 |
| `ust_par` | US Treasury, daily par yield CSV | 1m to 30y par curve (13 tenors) | daily ~15:30 NY | primary | 15 Aug 2026 |
| `nyfed_rates` | NY Fed markets API (JSON) | SOFR, EFFR (+ target range in meta) | daily 08:00 NY for T-1 | primary | 15 Aug 2026 |
| `yfinance` | Yahoo Finance via yfinance | ASX200, SPX, NDX, DJIA, VIX, AUDUSD, DXY, WTI, Brent, gold, copper, CBOE 5/10/30y | 10-20 min delayed | aggregator | 15 Aug 2026 (from GitHub Actions) |
| `asx_rate_tracker` | ASX, RBA Rate Tracker data files | 30-day interbank futures implied yield strip (18 contracts), front settlement, ASX expected cash rate / change / probability | EOD, T-1 | primary | 15 Aug 2026 |

## Planned (see PLAN.md)

| Adapter | Publisher | Notes |
|---|---|---|
| `fed_funds_futures` | CME via yfinance | ZQ strip contracts, delayed |
| `fred` | St Louis Fed | misc history, needs free key |
| `abs_calendar`, `bls_bea_calendar` | publishers | release dates |
| `alpaca` (worker) | Alpaca IEX feed | US equities/ETFs streaming, tier feed |

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
- RBA F1: some columns lag one day (e.g. cash rate row for "today" is empty until tomorrow).
  The adapter simply stores nothing for empty cells.
- Treasury CSV is per calendar year; adapter fetches current and previous year when the
  lookback crosses 1 Jan.
- NY Fed rates are for the *previous* business day; `ts` is set to that day 17:00 NY.
- yfinance: one batched `yf.download(period="1d", interval="5m")`; `ts` is the last bar's
  timestamp. Per-ticker `fast_info` calls returned nothing from GitHub runners; stay batched.
