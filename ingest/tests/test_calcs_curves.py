from decimal import Decimal

from tmd.calcs.curves import (
    cross_curve_spreads,
    slope_bp,
    sort_curve,
    spread_bp,
    tenor_from_series_id,
)


def test_tenor_from_series_id():
    assert tenor_from_series_id("us.ust.par.10y") == "10y"
    assert tenor_from_series_id("au.acgb.3y") == "3y"
    assert tenor_from_series_id("au.rba.cash_rate_target") is None


def test_sort_and_slope():
    pts = {"10y": Decimal("4.97"), "2y": Decimal("4.52"), "3m": Decimal("4.40")}
    assert [t for t, _ in sort_curve(pts)] == ["3m", "2y", "10y"]
    assert slope_bp(pts) == Decimal("45.0")
    assert slope_bp({"2y": Decimal("1")}) is None


def test_cross_curve():
    au = {"2y": Decimal("4.59"), "10y": Decimal("4.97")}
    us = {"2y": Decimal("4.25"), "10y": Decimal("4.70"), "30y": Decimal("5.23")}
    assert cross_curve_spreads(au, us) == {"2y": Decimal("34.0"), "10y": Decimal("27.0")}
    assert spread_bp(Decimal("4.70"), Decimal("4.25")) == Decimal("45.0")


def test_interpolate_missing_flags_and_no_extrapolation():
    from tmd.calcs.curves import interpolate_missing

    au = {"10y": Decimal("5.00"), "20y": Decimal("5.40")}
    got = interpolate_missing(au, ["10y", "15y", "20y", "30y"])
    assert got["10y"] == (Decimal("5.00"), False)
    assert got["15y"] == (Decimal("5.200"), True)
    assert got["20y"] == (Decimal("5.40"), False)
    assert "30y" not in got  # beyond observed range, not extrapolated
    assert interpolate_missing({}, ["2y"]) == {}
