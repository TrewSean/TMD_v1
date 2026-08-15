"""End-to-end through the runner with a stubbed adapter and the in-memory store."""

from datetime import UTC, datetime
from decimal import Decimal

from tmd.core.adapter import SourceAdapter
from tmd.core.models import Observation
from tmd.core.store import MemoryStore
from tmd.jobs import runner
from tmd.sources import REGISTRY


class _Fake(SourceAdapter):
    name = "rba_f1"  # borrow a real name so the catalogue lookup works

    def fetch(self, since=None):
        ts = datetime(2026, 8, 13, 7, tzinfo=UTC)
        return [
            Observation(series_id="au.rba.cash_rate_target", ts=ts, value=Decimal("4.35")),
            Observation(series_id="au.rba.cash_rate_target", ts=ts, value=Decimal("4.35")),  # dup
            Observation(series_id="au.bbsw.3m", ts=ts, value=Decimal("999")),  # out of bounds
            Observation(series_id="not.in.catalogue", ts=ts, value=Decimal("1")),
        ]


def test_runner_validates_and_records(monkeypatch):
    monkeypatch.setitem(REGISTRY, "rba_f1", _Fake)
    store = MemoryStore()
    res = runner.run_adapter("rba_f1", store)
    assert res.status == "partial"
    assert res.rows_fetched == 4
    assert res.rows_written == 1
    assert store.latest("au.rba.cash_rate_target").value == Decimal("4.35")
    assert store.latest("au.bbsw.3m") is None
    assert len(store.runs) == 1


def test_runner_records_error_and_continues(monkeypatch):
    class _Boom(_Fake):
        def fetch(self, since=None):
            raise RuntimeError("site down")

    monkeypatch.setitem(REGISTRY, "rba_f1", _Boom)
    store = MemoryStore()
    results = runner.run_many(["rba_f1"], store)
    assert results[0].status == "error"
    assert "site down" in results[0].error
    assert store.runs[0].status == "error"
