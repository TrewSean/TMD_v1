"""Alpaca Market Data (US stocks and ETFs). Tier: feed.

Two ways in, one set of series:
  * This adapter (`alpaca`): REST snapshot of the latest 1-minute bar per symbol via
    `alpaca-py`. Runs on the GitHub Actions intraday schedule as a polling fallback.
  * The streaming worker (`worker/`): websocket bars for the same symbols, written as
    they arrive. Uses `bar_to_observation` from this module so both paths agree.

Free plan facts (Aug 2026): feed "iex" is real-time but only IEX-venue volume;
"delayed_sip" is the full consolidated tape delayed 15 minutes; "sip" real-time is a
paid plan. Set ALPACA_FEED accordingly (default iex). No ASX, no rates, no FX here.

Docs: https://docs.alpaca.markets/docs/about-market-data-api
Keys: ALPACA_API_KEY / ALPACA_API_SECRET environment variables (never in code).

source_ref on the catalogue = the Alpaca symbol (e.g. SPY, NVDA).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from tmd.config import settings
from tmd.core.adapter import AdapterError, SourceAdapter
from tmd.core.models import Observation

log = logging.getLogger(__name__)


def bar_to_observation(
    bar: Any, series_id: str, symbol: str, as_of: datetime | None = None
) -> Observation:
    """alpaca-py Bar (or any object with timestamp/open/high/low/close/volume) -> Observation.

    ts = the bar's timestamp (bar START in Alpaca's convention, UTC). value = close.
    """
    ts = bar.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    meta = {
        "open": str(bar.open),
        "high": str(bar.high),
        "low": str(bar.low),
        "volume": str(bar.volume),
    }
    if getattr(bar, "vwap", None) is not None:
        meta["vwap"] = str(bar.vwap)
    return Observation(
        series_id=series_id,
        ts=ts,
        value=Decimal(str(bar.close)),
        as_of=as_of or datetime.now(UTC),
        source_ref=symbol,
        meta=meta,
    )


def _feed(name: str):
    from alpaca.data.enums import DataFeed

    try:
        return DataFeed(name.lower())
    except ValueError as exc:
        raise AdapterError(f"unknown ALPACA_FEED {name!r}; use iex, delayed_sip or sip") from exc


class AlpacaSnapshot(SourceAdapter):
    name = "alpaca"

    def fetch(self, since: datetime | None = None) -> list[Observation]:
        if not settings.alpaca_key or not settings.alpaca_secret:
            raise AdapterError("ALPACA_API_KEY / ALPACA_API_SECRET not set")
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestBarRequest

        client = StockHistoricalDataClient(settings.alpaca_key, settings.alpaca_secret)
        ref_to_id = {s.source_ref: s.id for s in self.series}
        req = StockLatestBarRequest(
            symbol_or_symbols=list(ref_to_id), feed=_feed(settings.alpaca_feed)
        )
        bars = client.get_stock_latest_bar(req)
        fetched = datetime.now(UTC)
        out: list[Observation] = []
        missing: list[str] = []
        for symbol, sid in ref_to_id.items():
            bar = bars.get(symbol) if isinstance(bars, dict) else None
            if bar is None:
                missing.append(symbol)
                continue
            out.append(bar_to_observation(bar, sid, symbol, fetched))
        if missing:
            log.warning("alpaca: no latest bar for %s", missing)
        if not out:
            raise AdapterError(f"alpaca: no bars returned for any symbol ({missing})")
        return out
