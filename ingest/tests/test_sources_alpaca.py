from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from tmd.sources.alpaca import bar_to_observation


def test_bar_to_observation_maps_fields():
    bar = SimpleNamespace(
        symbol="SPY",
        timestamp=datetime(2026, 8, 14, 19, 59, tzinfo=UTC),
        open=645.1,
        high=645.9,
        low=644.8,
        close=645.5,
        volume=123456,
        trade_count=900,
        vwap=645.4,
    )
    o = bar_to_observation(bar, "us.etf.spy", "SPY")
    assert o.series_id == "us.etf.spy"
    assert o.value == Decimal("645.5")
    assert o.ts == bar.timestamp
    assert o.meta["volume"] == "123456" and o.meta["vwap"] == "645.4"
    assert o.source_ref == "SPY"


def test_naive_bar_timestamp_assumed_utc():
    bar = SimpleNamespace(
        timestamp=datetime(2026, 8, 14, 19, 59), open=1, high=1, low=1, close=1, volume=0
    )
    o = bar_to_observation(bar, "x", "X")
    assert o.ts.tzinfo is not None and o.ts.hour == 19
