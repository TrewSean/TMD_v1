"""RBA statistical tables F1 (money market) and F2 (government bond yields).

Source of record: https://www.rba.gov.au/statistics/tables/
CSV layout: ~11 header rows (Title, Description, Frequency, Type, Units, ..., Series ID)
then one row per date, "DD-Mon-YYYY". Published daily, usually by ~4:30pm Sydney
for the same day (some columns lag a day). Empty cells are simply empty.

source_ref on the catalogue = the RBA "Series ID" (e.g. FIRMMCRTD).
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from tmd.core.adapter import AdapterError, SourceAdapter
from tmd.core.http import get_text
from tmd.core.models import Observation

SYDNEY = ZoneInfo("Australia/Sydney")
DEFAULT_LOOKBACK_DAYS = 45


def parse_rba_csv(
    text: str, wanted_ids: dict[str, str], since: datetime | None
) -> list[Observation]:
    """wanted_ids maps RBA Series ID -> our series id."""
    text = text.lstrip("﻿")
    rows = list(csv.reader(io.StringIO(text)))
    header_idx = next((i for i, r in enumerate(rows) if r and r[0].strip() == "Series ID"), None)
    if header_idx is None:
        raise AdapterError("RBA CSV: no 'Series ID' header row found (format changed?)")
    ids = [c.strip() for c in rows[header_idx]]
    col_for: dict[int, str] = {}
    for i, rba_id in enumerate(ids):
        if rba_id in wanted_ids:
            col_for[i] = wanted_ids[rba_id]
    missing = set(wanted_ids) - set(ids)
    if missing:
        # Not fatal: report through notes by raising only if *nothing* matched.
        if not col_for:
            raise AdapterError(f"RBA CSV: none of the wanted series ids present: {sorted(missing)}")
    out: list[Observation] = []
    fetched = datetime.now(UTC)
    for r in rows[header_idx + 1 :]:
        if not r or not r[0].strip():
            continue
        try:
            d = datetime.strptime(r[0].strip(), "%d-%b-%Y")
        except ValueError:
            continue
        # A daily fixing is "for" that Sydney business day; store as that day's close, UTC.
        ts = d.replace(hour=17, minute=0, tzinfo=SYDNEY).astimezone(UTC)
        if since and ts < since:
            continue
        for i, sid in col_for.items():
            if i >= len(r) or not r[i].strip():
                continue
            try:
                v = Decimal(r[i].strip())
            except InvalidOperation:
                continue
            out.append(Observation(series_id=sid, ts=ts, value=v, as_of=fetched, source_ref=ids[i]))
    return out


class _RBATable(SourceAdapter):
    url: str

    def fetch(self, since: datetime | None = None) -> list[Observation]:
        if since is None:
            since = datetime.now(UTC) - timedelta(days=DEFAULT_LOOKBACK_DAYS)
        text = get_text(self.url)
        wanted = {s.source_ref: s.id for s in self.series}
        return parse_rba_csv(text, wanted, since)


class RBAF1(_RBATable):
    name = "rba_f1"
    url = "https://www.rba.gov.au/statistics/tables/csv/f1-data.csv"


class RBAF2(_RBATable):
    name = "rba_f2"
    url = "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv"
