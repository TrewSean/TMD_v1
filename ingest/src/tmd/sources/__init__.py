"""Adapter registry. To add a source: write the adapter, import it here, add to REGISTRY.

The test suite asserts every catalogue `source` has a registry entry and vice versa,
so forgetting one fails CI rather than failing silently at 3am.
"""

from __future__ import annotations

from tmd.core.adapter import SourceAdapter
from tmd.sources.asx_rate_tracker import ASXRateTracker
from tmd.sources.nyfed_rates import NYFedRates
from tmd.sources.rba_tables import RBAF1, RBAF2
from tmd.sources.ust_par import USTPar
from tmd.sources.yfinance_quotes import YFinanceQuotes

REGISTRY: dict[str, type[SourceAdapter]] = {
    RBAF1.name: RBAF1,
    RBAF2.name: RBAF2,
    USTPar.name: USTPar,
    NYFedRates.name: NYFedRates,
    YFinanceQuotes.name: YFinanceQuotes,
    ASXRateTracker.name: ASXRateTracker,
}
