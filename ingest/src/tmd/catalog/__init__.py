"""Load and validate the series catalogue (series.yaml)."""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import yaml

from tmd.core.models import Series

CATALOG_PATH = Path(__file__).with_name("series.yaml")


class CatalogError(ValueError):
    pass


@lru_cache(maxsize=1)
def load(path: Path = CATALOG_PATH) -> list[Series]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    defaults: dict = raw.get("defaults", {}) or {}
    entries: list[dict] = raw.get("series", []) or []
    out: list[Series] = []
    seen: set[str] = set()
    for e in entries:
        merged = {**defaults, **e}
        s = Series.model_validate(merged)
        if s.id in seen:
            raise CatalogError(f"duplicate series id: {s.id}")
        seen.add(s.id)
        out.append(s)
    return out


def by_source(active_only: bool = True) -> dict[str, list[Series]]:
    groups: dict[str, list[Series]] = defaultdict(list)
    for s in load():
        if active_only and not s.active:
            continue
        groups[s.source].append(s)
    return dict(groups)


def get(series_id: str) -> Series:
    for s in load():
        if s.id == series_id:
            return s
    raise KeyError(series_id)
