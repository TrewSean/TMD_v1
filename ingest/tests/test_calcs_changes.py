from datetime import UTC, datetime, timedelta
from decimal import Decimal

from tmd.calcs.changes import changes, latest_and_changes, value_at_or_before


def _d(y, m, d, v):
    return (datetime(y, m, d, 7, tzinfo=UTC), Decimal(v))


def test_value_at_or_before_picks_last_not_after():
    pts = [_d(2026, 8, 10, "1"), _d(2026, 8, 12, "2"), _d(2026, 8, 14, "3")]
    assert value_at_or_before(pts, datetime(2026, 8, 13, tzinfo=UTC)) == pts[1]
    assert value_at_or_before(pts, datetime(2026, 8, 9, tzinfo=UTC)) is None
    assert value_at_or_before(pts, pts[2][0]) == pts[2]


def test_rate_changes_in_bp_and_none_when_too_short():
    # Daily 10yr yields Mon 10 Aug .. Fri 14 Aug (weekend gap before)
    pts = [
        _d(2026, 8, 7, "4.60"),
        _d(2026, 8, 10, "4.62"),
        _d(2026, 8, 11, "4.65"),
        _d(2026, 8, 12, "4.63"),
        _d(2026, 8, 13, "4.63"),
        _d(2026, 8, 14, "4.68"),
    ]
    c = changes(pts, unit="pct")
    assert c["1d"].bp_change == Decimal("5.0")
    assert c["1d"].ref_ts.date() == datetime(2026, 8, 13).date()
    # 1w back from Fri 14 = Fri 7 -> exists exactly
    assert c["1w"].bp_change == Decimal("8.0")
    assert c["1w"].pct_change is None  # rates never get % change
    # nothing 30 days old
    assert c["1m"].abs_change is None
    assert c["ytd"].abs_change is None


def test_price_changes_in_percent():
    pts = [_d(2026, 1, 2, "100"), _d(2026, 8, 13, "150"), _d(2026, 8, 14, "153")]
    c = changes(pts, unit="index")
    assert c["1d"].pct_change == Decimal("2.00")
    assert c["1d"].bp_change is None
    # YTD ref = last point on/before 1 Jan 2026 -> none (first point is 2 Jan)
    assert c["ytd"].abs_change is None
    # explicit year_start after 2 Jan picks it up
    c2 = changes(pts, unit="index", year_start=datetime(2026, 1, 3, tzinfo=UTC))
    assert c2["ytd"].pct_change == Decimal("53.00")


def test_weekend_lookback_uses_previous_close():
    # anchor Monday; "1d ago" is Sunday -> falls back to Friday
    pts = [_d(2026, 8, 14, "10"), _d(2026, 8, 17, "11")]
    c = changes(pts, unit="price")
    assert c["1d"].ref_ts.date() == datetime(2026, 8, 14).date()
    assert c["1d"].pct_change == Decimal("10.00")


def test_custom_windows_and_empty():
    assert changes([], unit="pct") == {}
    pts = [_d(2026, 8, 1, "1.0"), _d(2026, 8, 3, "1.5")]
    c = changes(pts, unit="pct", windows={"2d": timedelta(days=2)})
    assert set(c) == {"2d", "ytd"}
    assert c["2d"].bp_change == Decimal("50.0")


def test_latest_and_changes():
    pts = [_d(2026, 8, 13, "4.63"), _d(2026, 8, 14, "4.68")]
    latest, c = latest_and_changes(list(reversed(pts)), unit="pct")
    assert latest == pts[1]
    assert c["1d"].bp_change == Decimal("5.0")
