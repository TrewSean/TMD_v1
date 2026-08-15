"""CME 30-day federal funds futures (ZQ) via Yahoo Finance. Tier: aggregator.

Source: Yahoo Finance contract symbols of the form `ZQ<month code><yy>.CBT`, e.g.
`ZQU26.CBT` for September 2026. Fetched with one batched `yf.download`, the same way
`yfinance_quotes.py` does it, because per-ticker calls return nothing from GitHub
runners. Delayed and unofficial; the publisher of record is CME, and a licensed CME
feed (Phase 4) would replace this at tier `feed`.

What is stored
--------------
The **price**, not the implied rate. Turning a price into a rate (100 - price) is
arithmetic, and arithmetic belongs in `calcs/`, not in an adapter. `tmd derive` reads
these prices and hands them to `calcs.implied_path.contracts_from_prices`.

Contract identity
-----------------
Series ids are permanent but the listed contracts roll forward every month, so the
strip is keyed by POSITION (`m1` = the current calendar month's contract, `m2` the
next, and so on for 18 months) exactly as `asx_rate_tracker` does. Which contract a
number actually refers to travels with it: `meta.contract_ym` ("2026-09") is the
machine-readable form, `meta.expiry_month` ("Sep-26") matches the ASX wording, and
`meta.symbol` is the Yahoo ticker it came from.

Only the LATEST close per contract is stored, never the older bars in the download
window. A position means a different contract either side of a month roll, so
back-dating position m1 with bars from before the roll would file one contract's price
under another contract's name.

Conventions
-----------
`ts` is the session date stamped at 14:00 America/Chicago. That is when CME determines
the ZQ daily settlement, from Globex bid/ask activity between 13:59:00 and 14:00:00 CT
(CME, "30-Day Fed Fund Futures Daily Settlement Procedure",
https://www.cmegroup.com/market-data/settlements/files/30-day-fed-fund-futures-daily-settlement-procedure.pdf).
The *value* is Yahoo's daily close for that session, which approximates the official
settlement but is not guaranteed to equal it; that gap is exactly what tier
`aggregator` is telling you.

The contract settles to the monthly average of the daily effective fed funds rate
(EFFR) over the contract month, which is the model `calcs/implied_path.py` inverts.

source_ref on the catalogue = the position, `m1` .. `m18`.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from tmd.core.adapter import AdapterError, SourceAdapter
from tmd.core.models import Observation

log = logging.getLogger(__name__)

CHICAGO = ZoneInfo("America/Chicago")
STRIP_MONTHS = 18
# Yahoo hands back float32 widened to float64, so a 96.3675 tick arrives as
# 96.36750030517578. Quantising to 4dp recovers the quoted tick exactly: ZQ trades in
# 0.0025 (front month) and 0.005 increments, both exact at 4dp. This removes a
# representation artefact, it does not change the number.
TICK = Decimal("0.0001")
# CME/CBOT delivery month codes, January to December.
MONTH_CODES = "FGHJKMNQUVXZ"
DISPLAY_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def contract_symbol(year: int, month: int) -> str:
    """(2026, 9) -> 'ZQU26.CBT'."""
    if not 1 <= month <= 12:
        raise ValueError(f"month out of range: {month}")
    return f"ZQ{MONTH_CODES[month - 1]}{year % 100:02d}.CBT"


def strip_months(anchor: date, count: int = STRIP_MONTHS) -> list[tuple[int, int]]:
    """The rolling strip: (year, month) for `count` months starting with anchor's month."""
    out: list[tuple[int, int]] = []
    year, month = anchor.year, anchor.month
    for _ in range(count):
        out.append((year, month))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return out


def _settlement_ts(session: date) -> datetime:
    """CME determines the ZQ daily settlement at 14:00 Central. See the module docstring."""
    return datetime(session.year, session.month, session.day, 14, 0, tzinfo=CHICAGO).astimezone(UTC)


def observations_from_closes(
    closes,
    months: list[tuple[int, int]],
    ref_to_id: dict[str, str],
    as_of: datetime | None = None,
) -> list[Observation]:
    """`closes` is a DataFrame indexed by session with one column per contract symbol.

    Returns one Observation per position that has a usable close, in position order.
    Positions with no data are simply absent; we never invent a price.
    """
    fetched = as_of or datetime.now(UTC)
    out: list[Observation] = []
    missing: list[str] = []
    for position, (year, month) in enumerate(months, start=1):
        ref = f"m{position}"
        series_id = ref_to_id.get(ref)
        if series_id is None:
            continue
        symbol = contract_symbol(year, month)
        if symbol not in closes.columns:
            missing.append(symbol)
            continue
        column = closes[symbol].dropna()
        if column.empty:
            missing.append(symbol)
            continue
        session = column.index[-1]
        session = session.date() if hasattr(session, "date") else session
        out.append(
            Observation(
                series_id=series_id,
                ts=_settlement_ts(session),
                value=Decimal(str(float(column.iloc[-1]))).quantize(TICK),
                as_of=fetched,
                source_ref=ref,
                meta={
                    "symbol": symbol,
                    "contract_ym": f"{year:04d}-{month:02d}",
                    "expiry_month": f"{DISPLAY_MONTHS[month - 1]}-{year % 100:02d}",
                },
            )
        )
    if missing:
        # Deferred ZQ months are often illiquid on Yahoo; a gap is expected at the far end.
        log.warning("fed_funds_futures: no close for %s", missing)
    return out


class FedFundsFutures(SourceAdapter):
    name = "fed_funds_futures"

    def fetch(self, since: datetime | None = None) -> list[Observation]:
        import yfinance as yf  # lazy: heavy import, and the parser tests never need it

        ref_to_id = {s.source_ref: s.id for s in self.series}
        months = strip_months(datetime.now(CHICAGO).date())
        symbols = [contract_symbol(y, m) for y, m in months]

        # 5 sessions of daily bars so a holiday or a quiet contract still yields a close;
        # only the last bar per contract is used (see the module docstring).
        df = yf.download(
            symbols,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=False,
            group_by="column",
            threads=False,
        )
        if df is None or df.empty:
            raise AdapterError(
                "fed_funds_futures: yfinance returned an empty frame for the ZQ strip; "
                "Yahoo may be blocking this network (see stderr above)"
            )
        closes = df["Close"] if "Close" in df else df
        out = observations_from_closes(closes, months, ref_to_id)
        if not out:
            raise AdapterError(
                f"fed_funds_futures: no contract in the strip returned a close ({symbols[0]}...)"
            )
        if since is not None:
            out = [o for o in out if o.ts >= since]
        return out
