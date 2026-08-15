"""ASX 30-day interbank cash rate futures, the "RBA Rate Tracker".

Source of record: ASX, which lists, prices and cash-settles the IB contract, so this
is a primary source for its own settlement prices and implied yields.
Page: https://www.asx.com.au/markets/trade-our-derivatives-market/futures-market/rba-rate-tracker

The page is a widget fed by three published data files:

    https://www.asx.com.au/content/dam/asx/data/yield_curve.csv
    https://www.asx.com.au/content/dam/asx/data/dynamic_text.csv
    https://www.asx.com.au/content/dam/asx/data/market_exp.csv

Quirk worth knowing: they carry a `.csv` extension and are served as `text/csv`, but
the body is JSON. That mismatch is the publisher's, not ours. We fetch as text and
`json.loads` it; if ASX ever makes the extension honest this adapter fails loudly at
the parse rather than storing nonsense.

Shapes (trimmed):

    yield_curve   {"Crnt_Stlmnt_Dt": "2026-08-13", "RBA_Trgt_Cash_Rate": 4.35,
                   "months": [{"Expiry_Month": "Aug-26", "Implied_Yield": 4.345}, ...]}
    dynamic_text  {"Crnt_Stlmnt_Dt": ..., "Crnt_Dy_Stlmnt_Price": 95.65,
                   "Ftre_Cash_Rate": 4.1, "Ftre_Cash_Rate_Change": -0.25,
                   "RBA_Mtng_Dt": "2026-08-11", "Nxt_RBA_Mtng_Dt": "2026-09-29", ...}
    market_exp    {"days": [{"Stlmnt_Dt": "2026-08-13",
                             "Prob_No_Change": 100, "Prob_Change": 0}, ...]}

Cadence: end of day, one business day in arrears (`Crnt_Stlmnt_Dt` is the settlement
date the file is for, typically T-1). `market_exp` carries ~15 business days of history.

Licence: published openly on asx.com.au, no key and no terms gate. Attribution to ASX.

source_ref on the catalogue:
  * `m1` .. `mN`  the Nth listed contract month in `yield_curve.months`, m1 being the
    front month. Positions are used rather than calendar months because series ids are
    permanent and the contract set rolls forward every month; the actual contract is
    recorded on every observation as `meta.expiry_month`.
  * everything else is named after the published field it carries.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from tmd.core.adapter import AdapterError, SourceAdapter
from tmd.core.http import get_text
from tmd.core.models import Observation

SYDNEY = ZoneInfo("Australia/Sydney")
BASE = "https://www.asx.com.au/content/dam/asx/data"

# Fields of dynamic_text.csv we publish as series, in a stable order.
DYNAMIC_FIELDS = ("Crnt_Dy_Stlmnt_Price", "Ftre_Cash_Rate", "Ftre_Cash_Rate_Change")
# Fields of dynamic_text.csv we keep as context on every observation from that file.
DYNAMIC_META = (
    "RBA_Mtng_Dt",
    "Nxt_RBA_Mtng_Dt",
    "RBA_Trgt_Cash_Rate",
    "Expiry_Month",
    "Expiry_Year",
)


def _as_dict(payload: object, what: str) -> dict:
    if not isinstance(payload, dict):
        raise AdapterError(f"ASX {what}: expected a JSON object, got {type(payload).__name__}")
    return payload


def _settlement_ts(date_str: str, what: str) -> datetime:
    """ASX strikes the daily settlement price for IB futures at 16:30 Sydney."""
    try:
        d = datetime.strptime(str(date_str), "%Y-%m-%d")
    except ValueError as exc:
        raise AdapterError(f"ASX {what}: unparseable date {date_str!r}") from exc
    return d.replace(hour=16, minute=30, tzinfo=SYDNEY).astimezone(UTC)


def _decimal(value: object) -> Decimal | None:
    """Published number -> Decimal. Returns None for a missing value; never guesses one."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def parse_yield_curve(payload: object, wanted: dict[str, str]) -> list[Observation]:
    """The implied yield strip. `wanted` maps source_ref ("m1", ...) -> our series id."""
    doc = _as_dict(payload, "yield_curve")
    months = doc.get("months")
    if not isinstance(months, list) or not months:
        raise AdapterError("ASX yield_curve: no 'months' array (format changed?)")
    ts = _settlement_ts(doc.get("Crnt_Stlmnt_Dt"), "yield_curve")
    fetched = datetime.now(UTC)
    target = _decimal(doc.get("RBA_Trgt_Cash_Rate"))

    out: list[Observation] = []
    for position, month in enumerate(months, start=1):
        ref = f"m{position}"
        series_id = wanted.get(ref)
        if series_id is None or not isinstance(month, dict):
            continue
        value = _decimal(month.get("Implied_Yield"))
        if value is None:
            continue  # a gap in the strip stays a gap
        meta = {"expiry_month": str(month.get("Expiry_Month", ""))}
        if target is not None:
            meta["rba_target_cash_rate"] = str(target)
        out.append(
            Observation(
                series_id=series_id,
                ts=ts,
                value=value,
                as_of=fetched,
                source_ref=ref,
                meta=meta,
            )
        )
    return out


def parse_dynamic_text(payload: object, wanted: dict[str, str]) -> list[Observation]:
    """Front-contract settlement and ASX's own headline expectation for the next meeting."""
    doc = _as_dict(payload, "dynamic_text")
    ts = _settlement_ts(doc.get("Crnt_Stlmnt_Dt"), "dynamic_text")
    fetched = datetime.now(UTC)
    meta = {k.lower(): str(doc[k]) for k in DYNAMIC_META if doc.get(k) is not None}

    out: list[Observation] = []
    for ref in DYNAMIC_FIELDS:
        series_id = wanted.get(ref)
        if series_id is None:
            continue
        value = _decimal(doc.get(ref))
        if value is None:
            continue
        out.append(
            Observation(
                series_id=series_id,
                ts=ts,
                value=value,
                as_of=fetched,
                source_ref=ref,
                meta=meta,
            )
        )
    return out


def parse_market_exp(payload: object, wanted: dict[str, str]) -> list[Observation]:
    """Implied probability of a move at the next meeting, with ~15 days of history."""
    doc = _as_dict(payload, "market_exp")
    days = doc.get("days")
    if not isinstance(days, list) or not days:
        raise AdapterError("ASX market_exp: no 'days' array (format changed?)")
    series_id = wanted.get("Prob_Change")
    if series_id is None:
        return []
    fetched = datetime.now(UTC)

    out: list[Observation] = []
    for day in days:
        if not isinstance(day, dict):
            continue
        value = _decimal(day.get("Prob_Change"))
        if value is None or day.get("Stlmnt_Dt") is None:
            continue
        meta = {}
        no_change = _decimal(day.get("Prob_No_Change"))
        if no_change is not None:
            meta["prob_no_change"] = str(no_change)
        out.append(
            Observation(
                series_id=series_id,
                ts=_settlement_ts(day["Stlmnt_Dt"], "market_exp"),
                value=value,
                as_of=fetched,
                source_ref="Prob_Change",
                meta=meta,
            )
        )
    return out


class ASXRateTracker(SourceAdapter):
    name = "asx_rate_tracker"

    def fetch(self, since: datetime | None = None) -> list[Observation]:
        wanted = {s.source_ref: s.id for s in self.series}
        out: list[Observation] = []
        out.extend(parse_yield_curve(self._get("yield_curve"), wanted))
        out.extend(parse_dynamic_text(self._get("dynamic_text"), wanted))
        out.extend(parse_market_exp(self._get("market_exp"), wanted))
        if since is not None:
            out = [o for o in out if o.ts >= since]
        return out

    @staticmethod
    def _get(name: str) -> object:
        # .csv extension, text/csv content type, JSON body. See the module docstring.
        text = get_text(f"{BASE}/{name}.csv")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AdapterError(f"ASX {name}.csv: body is not JSON ({exc})") from exc
