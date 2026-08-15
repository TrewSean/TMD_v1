"""The one interface every data source must implement.

Adding a new source = one new file in tmd/sources/ that subclasses SourceAdapter,
plus its series in catalog/series.yaml. Nothing else in the system changes.

Contract:
  * `name`     : unique snake_case id, must equal the `source` field on its series.
  * `fetch()`  : go to the source, return Observations for the series it owns.
                 May raise; the runner catches, records an error row, and moves on.
  * Never write to the database directly. Return data; the runner stores it.
  * Never do arithmetic on the data beyond unit normalisation. Calcs live in tmd/calcs.
  * Must be safe to run repeatedly (idempotent). Duplicates are handled by upsert.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from tmd.core.models import Observation, Series


class SourceAdapter(ABC):
    name: str

    def __init__(self, series: list[Series]):
        # The runner hands the adapter only the catalogue entries it owns.
        self.series = series
        self.by_ref: dict[str, Series] = {s.source_ref: s for s in series}
        self.by_id: dict[str, Series] = {s.id: s for s in series}

    @abstractmethod
    def fetch(self, since: datetime | None = None) -> list[Observation]:
        """Return observations. `since` is a hint to limit history; may be ignored."""

    # Optional hook: adapters that can cheaply report their own health.
    def healthcheck(self) -> bool:
        return True


class AdapterError(RuntimeError):
    """Raise for expected, non-bug failures (site down, format changed)."""
