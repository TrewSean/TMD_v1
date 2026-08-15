"""The catalogue and the adapter registry must always agree."""

from tmd import catalog
from tmd.core.models import Series
from tmd.jobs.derive import DERIVED_SOURCES
from tmd.sources import REGISTRY

# A series is owned either by an adapter that fetches it or by a derivation that
# computes it. Everything in the catalogue must have exactly one of those owners.
OWNERS = set(REGISTRY) | set(DERIVED_SOURCES)


def test_catalog_loads_and_ids_unique():
    series = catalog.load()
    assert len(series) > 20
    ids = [s.id for s in series]
    assert len(ids) == len(set(ids))
    assert all(isinstance(s, Series) for s in series)


def test_every_source_has_an_adapter_or_derivation():
    sources = {s.source for s in catalog.load()}
    missing = sources - OWNERS
    assert not missing, f"catalogue sources with no adapter or derivation: {missing}"


def test_every_adapter_owns_at_least_one_series():
    owned = catalog.by_source(active_only=False)
    orphans = OWNERS - set(owned)
    assert not orphans, f"adapters/derivations with no series in catalogue: {orphans}"


def test_derived_series_are_tagged_and_never_claim_to_be_fetched():
    for s in catalog.load():
        if s.source in DERIVED_SOURCES:
            assert "derived" in s.tags, f"{s.id} is computed but not tagged derived"
        if "derived" in s.tags:
            assert s.source in DERIVED_SOURCES, f"{s.id} is tagged derived but has an adapter"


def test_source_refs_unique_within_source():
    for src, series in catalog.by_source(active_only=False).items():
        refs = [s.source_ref for s in series]
        assert len(refs) == len(set(refs)), f"duplicate source_ref in {src}"
