"""Sanity checks applied to every observation before it is stored.

These are deliberately simple and loud. A bad number that gets into the DB
ends up on the website; a rejected one just shows up in ingest_runs.notes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from tmd.core.models import Observation, Series

# Plausible bounds per unit. Widen deliberately if a real value trips them.
BOUNDS: dict[str, tuple[Decimal, Decimal]] = {
    "pct": (Decimal("-5"), Decimal("50")),
    "bp": (Decimal("-2000"), Decimal("5000")),
    "index": (Decimal("0"), Decimal("1000000")),
    "price": (Decimal("0"), Decimal("1000000")),
    "usd_per_bbl": (Decimal("-50"), Decimal("1000")),
    "usd_per_oz": (Decimal("0"), Decimal("100000")),
    "usd_per_lb": (Decimal("0"), Decimal("100")),
}

MAX_FUTURE = timedelta(days=2)
MAX_PAST = timedelta(days=365 * 60)


def validate_observations(
    obs: list[Observation], series: dict[str, Series]
) -> tuple[list[Observation], list[str]]:
    good: list[Observation] = []
    problems: list[str] = []
    now = datetime.now(UTC)
    seen: set[tuple[str, datetime]] = set()
    for o in obs:
        s = series.get(o.series_id)
        if s is None:
            problems.append(f"{o.series_id}: not in catalogue for this adapter")
            continue
        if o.value.is_nan():
            problems.append(f"{o.series_id}@{o.ts:%Y-%m-%d}: NaN")
            continue
        lo, hi = BOUNDS.get(s.unit, (Decimal("-1e12"), Decimal("1e12")))
        if not (lo <= o.value <= hi):
            problems.append(
                f"{o.series_id}@{o.ts:%Y-%m-%d}: {o.value} outside [{lo},{hi}] for unit {s.unit}"
            )
            continue
        if o.ts > now + MAX_FUTURE:
            problems.append(f"{o.series_id}: ts {o.ts} is in the future")
            continue
        if o.ts < now - MAX_PAST:
            problems.append(f"{o.series_id}: ts {o.ts} implausibly old")
            continue
        key = (o.series_id, o.ts)
        if key in seen:
            continue  # silently drop exact duplicates
        seen.add(key)
        good.append(o)
    return good, problems
