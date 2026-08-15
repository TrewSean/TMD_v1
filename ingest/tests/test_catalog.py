"""The catalogue and the adapter registry must always agree."""

from tmd import catalog
from tmd.core.models import Series
from tmd.sources import REGISTRY


def test_catalog_loads_and_ids_unique():
    series = catalog.load()
    assert len(series) > 20
    ids = [s.id for s in series]
    assert len(ids) == len(set(ids))
    assert all(isinstance(s, Series) for s in series)


def test_every_source_has_an_adapter():
    sources = {s.source for s in catalog.load()}
    missing = sources - set(REGISTRY)
    assert not missing, f"catalogue sources with no adapter: {missing}"


def test_every_adapter_owns_at_least_one_series():
    owned = catalog.by_source(active_only=False)
    orphans = set(REGISTRY) - set(owned)
    assert not orphans, f"adapters with no series in catalogue: {orphans}"


def test_source_refs_unique_within_source():
    for src, series in catalog.by_source(active_only=False).items():
        refs = [s.source_ref for s in series]
        assert len(refs) == len(set(refs)), f"duplicate source_ref in {src}"
