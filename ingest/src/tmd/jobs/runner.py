"""Runs adapters. This is the only place that knows about both adapters and the store.

Flow per adapter:
  catalogue -> adapter(series it owns) -> fetch() -> validate -> store.upsert -> record_run
One adapter failing never stops the others.
"""

from __future__ import annotations

import logging
import traceback
from datetime import UTC, datetime

from tmd import catalog
from tmd.core.models import IngestResult, Observation
from tmd.core.store import Store
from tmd.core.validate import validate_observations
from tmd.sources import REGISTRY

log = logging.getLogger("tmd.runner")


def run_adapter(name: str, store: Store) -> IngestResult:
    started = datetime.now(UTC)
    notes: list[str] = []
    try:
        series = catalog.by_source().get(name, [])
        if not series:
            raise ValueError(f"no active series in catalogue for source '{name}'")
        cls = REGISTRY[name]
        adapter = cls(series)
        store.upsert_series(series)
        raw: list[Observation] = adapter.fetch()
        good, problems = validate_observations(raw, {s.id: s for s in series})
        notes.extend(problems)
        written = store.upsert_observations(good)
        status = "ok" if not problems else "partial"
        if not good:
            status = "error"
            notes.append("adapter returned no valid observations")
        result = IngestResult(
            adapter=name,
            started_at=started,
            finished_at=datetime.now(UTC),
            status=status,
            rows_fetched=len(raw),
            rows_written=written,
            notes=notes,
        )
    except Exception as exc:  # noqa: BLE001 - we want to record *any* failure
        log.exception("adapter %s failed", name)
        result = IngestResult(
            adapter=name,
            started_at=started,
            finished_at=datetime.now(UTC),
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            notes=[traceback.format_exc()[-2000:]],
        )
    store.record_run(result)
    log.info(
        "%s: %s fetched=%d written=%d",
        name,
        result.status,
        result.rows_fetched,
        result.rows_written,
    )
    return result


def run_many(names: list[str], store: Store) -> list[IngestResult]:
    return [run_adapter(n, store) for n in names]


# Named groups so schedules can say "run the daily fixings" without listing adapters.
GROUPS: dict[str, list[str]] = {
    "fixings": [
        "rba_f1",
        "rba_f2",
        "ust_par",
        "nyfed_rates",
        "asx_rate_tracker",
        "fed_funds_futures",
    ],
    "intraday": ["yfinance"],
    "alpaca": ["alpaca"],  # needs ALPACA_* secrets; polling fallback for the streaming worker
    "all": [
        "rba_f1",
        "rba_f2",
        "ust_par",
        "nyfed_rates",
        "asx_rate_tracker",
        "fed_funds_futures",
        "yfinance",
        "alpaca",
    ],
}
