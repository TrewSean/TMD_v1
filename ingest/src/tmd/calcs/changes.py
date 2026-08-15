"""Period changes for any series: 1d, 1w, 1m, 3m, YTD, 1y.

Pure functions over a list of (ts, value) points. No I/O.

Method
------
Given observations sorted by time and an anchor (usually the latest point), the
"value N ago" is the LAST observation whose ts is <= (anchor_ts - N). This is the
convention a trader expects: "1 week ago" on a Monday means last Monday's close, and
if that was a holiday it means the most recent close before it. We never interpolate.

For YTD the reference is the last observation with ts <= 1 January 00:00 in the
series' local calendar (we approximate with the anchor's own timezone-aware ts;
callers pass a `year_start` if they want a specific local midnight).

Changes are returned both absolute (same unit as the series) and as basis points
when the unit is a percentage rate, plus percent change for prices/indices.
Anything that cannot be computed (no observation old enough) is None, not 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

Point = tuple[datetime, Decimal]

WINDOWS: dict[str, timedelta] = {
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
    "1m": timedelta(days=30),
    "3m": timedelta(days=91),
    "1y": timedelta(days=365),
}

RATE_UNITS = {"pct"}


@dataclass(frozen=True)
class Change:
    label: str
    ref_ts: datetime | None
    ref_value: Decimal | None
    abs_change: Decimal | None  # anchor - ref, in series units
    pct_change: Decimal | None  # (anchor/ref - 1) * 100, None for rate units or ref == 0
    bp_change: Decimal | None  # abs_change * 100 for rate units, else None


def value_at_or_before(points: list[Point], when: datetime) -> Point | None:
    """Last point with ts <= when. points must be sorted ascending by ts."""
    best: Point | None = None
    for ts, v in points:
        if ts <= when:
            best = (ts, v)
        else:
            break
    return best


def _one(points: list[Point], anchor: Point, label: str, ref_when: datetime, unit: str) -> Change:
    ref = value_at_or_before(points, ref_when)
    if ref is None or ref[0] >= anchor[0]:
        return Change(label, None, None, None, None, None)
    ref_ts, ref_v = ref
    a_v = anchor[1]
    abs_c = (a_v - ref_v).normalize()
    if unit in RATE_UNITS:
        return Change(label, ref_ts, ref_v, abs_c, None, (abs_c * 100).quantize(Decimal("0.1")))
    pct = None if ref_v == 0 else ((a_v / ref_v - 1) * 100).quantize(Decimal("0.01"))
    return Change(label, ref_ts, ref_v, abs_c, pct, None)


def changes(
    points: list[Point],
    unit: str,
    anchor: Point | None = None,
    year_start: datetime | None = None,
    windows: dict[str, timedelta] | None = None,
) -> dict[str, Change]:
    """Compute standard period changes.

    points     : sorted ascending by ts (UTC-aware). Empty -> {}.
    unit       : the series unit ("pct" gets bp changes, others get % changes).
    anchor     : the point to measure from; defaults to the last point.
    year_start : datetime for YTD reference; defaults to 1 Jan 00:00 UTC of anchor's year.
    """
    if not points:
        return {}
    pts = sorted(points, key=lambda p: p[0])
    anchor = anchor or pts[-1]
    out: dict[str, Change] = {}
    for label, delta in (windows or WINDOWS).items():
        out[label] = _one(pts, anchor, label, anchor[0] - delta, unit)
    ys = year_start or datetime(anchor[0].year, 1, 1, tzinfo=UTC)
    out["ytd"] = _one(pts, anchor, "ytd", ys, unit)
    return out


def latest_and_changes(points: list[Point], unit: str) -> tuple[Point | None, dict[str, Change]]:
    """Convenience: (latest point, its changes)."""
    if not points:
        return None, {}
    pts = sorted(points, key=lambda p: p[0])
    return pts[-1], changes(pts, unit, anchor=pts[-1])
