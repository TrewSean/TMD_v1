from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tmd.core.models import Observation


def test_float_value_becomes_clean_decimal():
    o = Observation(series_id="x", ts=datetime(2026, 1, 1, tzinfo=UTC), value=4.35)
    assert o.value == Decimal("4.35")


def test_naive_timestamp_rejected():
    with pytest.raises(ValueError):
        Observation(series_id="x", ts=datetime(2026, 1, 1), value=1)


def test_timestamp_normalised_to_utc():
    from zoneinfo import ZoneInfo

    ts = datetime(2026, 8, 14, 17, 0, tzinfo=ZoneInfo("Australia/Sydney"))
    o = Observation(series_id="x", ts=ts, value=1)
    assert o.ts.tzinfo == UTC
    assert o.ts.hour == 7
