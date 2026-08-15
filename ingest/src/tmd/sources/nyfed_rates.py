"""New York Fed reference rates (SOFR, EFFR, and friends).

Source of record: https://markets.newyorkfed.org/  (public JSON API, no key)
  secured  : /api/rates/secured/{sofr|bgcr|tgcr}/last/{n}.json
  unsecured: /api/rates/unsecured/{effr|obfr}/last/{n}.json
Published ~8:00am New York for the *previous* business day.

source_ref on the catalogue = the rate code (sofr, effr, ...).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from tmd.core.adapter import AdapterError, SourceAdapter
from tmd.core.http import get_json
from tmd.core.models import Observation

NEW_YORK = ZoneInfo("America/New_York")
BASE = "https://markets.newyorkfed.org/api/rates"
KIND = {
    "sofr": "secured",
    "bgcr": "secured",
    "tgcr": "secured",
    "effr": "unsecured",
    "obfr": "unsecured",
}


def parse_ref_rates(payload: object, series_id: str, code: str) -> list[Observation]:
    if not isinstance(payload, dict) or "refRates" not in payload:
        raise AdapterError(f"NY Fed {code}: unexpected payload shape")
    fetched = datetime.now(UTC)
    out: list[Observation] = []
    for r in payload["refRates"]:
        if str(r.get("type", "")).lower() != code:
            continue
        d = datetime.strptime(r["effectiveDate"], "%Y-%m-%d")
        ts = d.replace(hour=17, tzinfo=NEW_YORK).astimezone(UTC)
        meta = {}
        for k in ("targetRateFrom", "targetRateTo", "volumeInBillions"):
            if k in r and r[k] is not None:
                meta[k] = str(r[k])
        out.append(
            Observation(
                series_id=series_id,
                ts=ts,
                value=Decimal(str(r["percentRate"])),
                as_of=fetched,
                source_ref=code,
                meta=meta,
            )
        )
    return out


class NYFedRates(SourceAdapter):
    name = "nyfed_rates"

    def fetch(self, since: datetime | None = None) -> list[Observation]:
        n = 30
        if since is not None:
            n = max(1, min(400, (datetime.now(UTC) - since).days + 5))
        out: list[Observation] = []
        for s in self.series:
            code = s.source_ref.lower()
            kind = KIND.get(code)
            if kind is None:
                raise AdapterError(f"NY Fed: unknown rate code {code}")
            payload = get_json(f"{BASE}/{kind}/{code}/last/{n}.json")
            out.extend(parse_ref_rates(payload, s.id, code))
        if since is not None:
            out = [o for o in out if o.ts >= since - timedelta(days=1)]
        return out
