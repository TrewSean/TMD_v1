"""Load and validate the policy meeting calendar (meetings.yaml).

Meeting dates are versioned config, not a data source and not Observations. See the
header of meetings.yaml for why, and CLAUDE.md's exception for slow-moving HTML-only
reference data.

The point of this module is that a transcription slip should fail loudly here rather
than silently move an implied path. `load()` raises `MeetingsError` on anything
inconsistent: dates out of order, an effective date not after its decision, duplicates,
or a decision falling on the wrong weekday for that bank.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

MEETINGS_PATH = Path(__file__).with_name("meetings.yaml")


class MeetingsError(ValueError):
    pass


class Meeting(BaseModel):
    decision: date
    effective: date
    projections: bool = False
    note: str = ""


class Bank(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    country: str = Field(min_length=2, max_length=2)
    rate_series: str
    source_url: str
    reviewed: date
    decision_weekday: int = Field(ge=0, le=6)
    meetings: list[Meeting]

    def pairs(self, since: date | None = None) -> list[tuple[date, date]]:
        """(decision, effective) pairs, ascending. Shape `implied_path.solve_path` wants."""
        return [
            (m.decision, m.effective)
            for m in self.meetings
            if since is None or m.effective >= since
        ]

    def upcoming(self, on: date) -> list[Meeting]:
        """Meetings whose rate is not yet in force on `on`."""
        return [m for m in self.meetings if m.effective >= on]

    def next_after(self, on: date) -> Meeting | None:
        later = self.upcoming(on)
        return later[0] if later else None


def _check(bank: Bank) -> None:
    if not bank.meetings:
        raise MeetingsError(f"{bank.id}: no meetings listed")
    seen: set[date] = set()
    previous: date | None = None
    for m in bank.meetings:
        if m.effective <= m.decision:
            raise MeetingsError(
                f"{bank.id} {m.decision}: effective {m.effective} must be after the decision"
            )
        if previous is not None and m.decision <= previous:
            raise MeetingsError(
                f"{bank.id} {m.decision}: decision dates must ascend (previous {previous})"
            )
        if m.decision in seen:
            raise MeetingsError(f"{bank.id}: duplicate decision date {m.decision}")
        if m.decision.weekday() != bank.decision_weekday:
            raise MeetingsError(
                f"{bank.id} {m.decision}: decision falls on "
                f"{m.decision.strftime('%A')}, expected weekday {bank.decision_weekday}"
            )
        seen.add(m.decision)
        previous = m.decision


@lru_cache(maxsize=1)
def load(path: Path = MEETINGS_PATH) -> dict[str, Bank]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = (raw or {}).get("banks") or []
    if not entries:
        raise MeetingsError("meetings.yaml has no banks")
    out: dict[str, Bank] = {}
    for entry in entries:
        try:
            bank = Bank.model_validate(entry)
        except ValidationError as exc:
            raise MeetingsError(f"invalid bank entry: {exc}") from exc
        if bank.id in out:
            raise MeetingsError(f"duplicate bank id: {bank.id}")
        _check(bank)
        out[bank.id] = bank
    return out


def get(bank_id: str) -> Bank:
    try:
        return load()[bank_id]
    except KeyError as exc:
        raise MeetingsError(f"unknown bank '{bank_id}'; have {sorted(load())}") from exc
