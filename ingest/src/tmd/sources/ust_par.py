"""US Treasury daily par yield curve.

Source of record: https://home.treasury.gov/resource-center/data-chart-center/interest-rates/
CSV endpoint (one file per calendar year, newest first):
  .../daily-treasury-rates.csv/{YEAR}/all?type=daily_treasury_yield_curve&field_tdr_date_value={YEAR}
Columns: Date (MM/DD/YYYY), "1 Mo", "1.5 Month", "2 Mo", "3 Mo", "4 Mo", "6 Mo",
  "1 Yr", ... "30 Yr".
Published each business day after ~3:30pm New York.

source_ref on the catalogue = the column header text.
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

NEW_YORK = ZoneInfo("America/New_York")
BASE = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv"


def url_for_year(year: int) -> str:
    return f"{BASE}/{year}/all?type=daily_treasury_yield_curve&field_tdr_date_value={year}"


def parse_ust_csv(
    text: str, wanted_cols: dict[str, str], since: datetime | None
) -> list[Observation]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if not reader.fieldnames or "Date" not in reader.fieldnames:
        raise AdapterError("UST CSV: 'Date' column missing (format changed?)")
    have = set(reader.fieldnames)
    if not (set(wanted_cols) & have):
        raise AdapterError(f"UST CSV: none of wanted columns present; got {sorted(have)}")
    out: list[Observation] = []
    fetched = datetime.now(UTC)
    for row in reader:
        try:
            d = datetime.strptime(row["Date"].strip(), "%m/%d/%Y")
        except (ValueError, AttributeError):
            continue
        ts = d.replace(hour=16, minute=0, tzinfo=NEW_YORK).astimezone(UTC)
        if since and ts < since:
            continue
        for col, sid in wanted_cols.items():
            raw = (row.get(col) or "").strip()
            if not raw or raw.upper() == "N/A":
                continue
            try:
                v = Decimal(raw)
            except InvalidOperation:
                continue
            out.append(Observation(series_id=sid, ts=ts, value=v, as_of=fetched, source_ref=col))
    return out


class USTPar(SourceAdapter):
    name = "ust_par"

    def fetch(self, since: datetime | None = None) -> list[Observation]:
        now = datetime.now(UTC)
        if since is None:
            since = now - timedelta(days=45)
        wanted = {s.source_ref: s.id for s in self.series}
        years = sorted({since.year, now.year})
        out: list[Observation] = []
        for y in years:
            out.extend(parse_ust_csv(get_text(url_for_year(y)), wanted, since))
        return out
