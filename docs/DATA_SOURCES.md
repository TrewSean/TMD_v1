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

## Planned (see PLAN.md)

| Adapter | Publisher | Notes |
|---|---|---|
| `asx_rate_tracker` | ASX | 30-day interbank cash rate futures implied path, EOD |
| `asx_bbsw` | ASX | BBSW daily file, same-day |
| `fed_funds_futures` | CME via yfinance | ZQ strip contracts, delayed |
| `fred` | St Louis Fed | misc history, needs free key |
| `abs_calendar`, `bls_bea_calendar`, `rba_calendar`, `fomc_calendar` | publishers | release / meeting dates |
| `alpaca` (worker) | Alpaca IEX feed | US equities/ETFs streaming, tier feed |

## Known quirks

- RBA F1: some columns lag one day (e.g. cash rate row for "today" is empty until tomorrow).
  The adapter simply stores nothing for empty cells.
- Treasury CSV is per calendar year; adapter fetches current and previous year when the
  lookback crosses 1 Jan.
- NY Fed rates are for the *previous* business day; `ts` is set to that day 17:00 NY.
- yfinance: one batched `yf.download(period="1d", interval="5m")`; `ts` is the last bar's
  timestamp. Per-ticker `fast_info` calls returned nothing from GitHub runners; stay batched.
