"""Yield curve helpers. Pure functions on plain numbers.

This module is the template for every calc in the project:
  * inputs are plain Python (dicts, Decimals, floats), never DB rows or HTTP;
  * outputs are plain Python;
  * every function has a test with fixed inputs in tests/test_calcs_curves.py.
"""

from __future__ import annotations

from decimal import Decimal

# Tenor labels -> years. Shared by AU and US curves so spreads line up.
TENOR_YEARS: dict[str, float] = {
    "1m": 1 / 12,
    "2m": 2 / 12,
    "3m": 0.25,
    "4m": 4 / 12,
    "6m": 0.5,
    "1y": 1,
    "2y": 2,
    "3y": 3,
    "5y": 5,
    "7y": 7,
    "10y": 10,
    "15y": 15,
    "20y": 20,
    "30y": 30,
}


def tenor_from_series_id(series_id: str) -> str | None:
    """'us.ust.par.10y' -> '10y'; 'au.acgb.3y' -> '3y'; else None."""
    tail = series_id.rsplit(".", 1)[-1]
    return tail if tail in TENOR_YEARS else None


def sort_curve(points: dict[str, Decimal]) -> list[tuple[str, Decimal]]:
    """Order {tenor: yield} by maturity."""
    return sorted(points.items(), key=lambda kv: TENOR_YEARS[kv[0]])


def spread_bp(a: Decimal, b: Decimal) -> Decimal:
    """(a - b) in basis points, both in percent."""
    return ((a - b) * 100).quantize(Decimal("0.1"))


def slope_bp(points: dict[str, Decimal], short: str = "2y", long: str = "10y") -> Decimal | None:
    """Classic 2s10s style slope. None if either tenor missing."""
    if short not in points or long not in points:
        return None
    return spread_bp(points[long], points[short])


def cross_curve_spreads(au: dict[str, Decimal], us: dict[str, Decimal]) -> dict[str, Decimal]:
    """AU minus US at every tenor both curves have, in bp."""
    return {t: spread_bp(au[t], us[t]) for t in au if t in us}
