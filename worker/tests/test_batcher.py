from datetime import UTC, datetime, timedelta
from decimal import Decimal

from tmd import catalog
from tmd.core.models import Observation
from tmd.core.store import MemoryStore

from tmd_worker.stream import Batcher


def _obs(sid, minute, value):
    return Observation(
        series_id=sid, ts=datetime(2026, 8, 14, 19, minute, tzinfo=UTC), value=Decimal(value)
    )


def test_batcher_flushes_validates_and_heartbeats():
    series = {s.id: s for s in catalog.by_source()["alpaca"]}
    store = MemoryStore()
    b = Batcher(store, series)
    b.add(_obs("us.etf.spy", 1, "645.5"))
    b.add(_obs("us.etf.spy", 2, "645.7"))
    b.add(_obs("us.etf.spy", 3, "-5"))  # out of bounds for unit price
    assert b.due() is False  # not enough rows and not old enough
    b.last_flush -= timedelta(seconds=10)
    assert b.due() is True
    assert b.flush() == 2
    assert store.latest("us.etf.spy").value == Decimal("645.7")
    b.heartbeat()
    run = store.runs[-1]
    assert run.adapter == "alpaca_stream" and run.status == "ok"
    assert run.rows_written == 2 and run.rows_fetched == 3
    assert any("outside" in n for n in run.notes)
    # counters reset
    b.heartbeat()
    assert store.runs[-1].rows_written == 0
