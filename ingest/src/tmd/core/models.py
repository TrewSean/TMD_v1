"""Core data model. Everything the pipeline produces is one of these.

Design rule: the website and the calcs never know where a number came from.
They only ever see a Series (what it is) and Observations (its values over time).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class AssetClass(StrEnum):
    RATES = "rates"
    EQUITY = "equity"
    FX = "fx"
    COMMODITY = "commodity"
    CREDIT = "credit"
    MACRO = "macro"


class Frequency(StrEnum):
    """How often a series is *expected* to produce a new observation."""

    TICK = "tick"  # streaming
    INTRADAY = "intraday"  # polled during market hours
    DAILY = "daily"  # one fixing per business day
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    IRREGULAR = "irregular"  # e.g. central bank decisions


class Tier(StrEnum):
    """How much to trust the source. Drives display badges and fallback order."""

    PRIMARY = "primary"  # the publisher of record (RBA, Treasury, NY Fed, exchange)
    FEED = "feed"  # licensed market data feed (Alpaca, IBKR)
    AGGREGATOR = "aggregator"  # delayed / unofficial (yfinance)


class Series(BaseModel):
    """A single time series in the catalogue. Immutable identity for a number."""

    id: str = Field(
        pattern=r"^[a-z0-9_.]+$", description="stable snake_case id, e.g. au.rba.cash_rate_target"
    )
    name: str
    unit: str  # "pct", "bp", "index", "price", "usd", "aud", "usd_per_bbl" ...
    asset_class: AssetClass
    country: str = Field(
        min_length=2, max_length=2, description="ISO 3166-1 alpha-2, or 'XX' for global"
    )
    frequency: Frequency
    tier: Tier
    source: str  # adapter name that owns this series
    source_ref: str = ""  # ticker / column / API key within the source
    description: str = ""
    active: bool = True
    tags: list[str] = Field(default_factory=list)


class Observation(BaseModel):
    """One value of one series at one point in time.

    ts     : the time the value is *for* (fixing date, quote timestamp). Always UTC.
    as_of  : the time we *fetched* it. Always UTC. Lets us audit staleness.
    """

    series_id: str
    ts: datetime
    value: Decimal
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_ref: str = ""
    meta: dict[str, str] = Field(default_factory=dict)

    @field_validator("ts", "as_of")
    @classmethod
    def _must_be_aware_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware (UTC)")
        return v.astimezone(UTC)

    @field_validator("value", mode="before")
    @classmethod
    def _to_decimal(cls, v: object) -> Decimal:
        if isinstance(v, Decimal):
            return v
        if isinstance(v, float):
            # Go through str to avoid binary float artefacts like 4.3500000000001
            return Decimal(str(v))
        if isinstance(v, int | str):
            return Decimal(v)
        raise TypeError(f"cannot convert {type(v).__name__} to Decimal")


class IngestResult(BaseModel):
    """What an adapter run reports back. Written to ingest_runs for monitoring."""

    adapter: str
    started_at: datetime
    finished_at: datetime
    status: str  # "ok" | "partial" | "error"
    rows_fetched: int = 0
    rows_written: int = 0
    error: str | None = None
    notes: list[str] = Field(default_factory=list)
