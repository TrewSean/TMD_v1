"""Derived series: implied policy-rate paths from futures strips.

This is the only place that knows about the store, the catalogue, the meeting config
and the calcs at once, which is the same role `runner.py` plays for adapters. The
arithmetic itself lives in `calcs/implied_path.py` and stays pure; nothing here does
maths beyond turning a price into a rate.

Flow per derivation:
  strip observations + current reference rate + meetings.yaml
    -> calcs.implied_path.solve_path
    -> Observations on the `*.implied.n<k>` series
    -> validate -> sink.upsert -> record_run

Node keying
-----------
Series ids are permanent, and meetings roll forward, so a path node is keyed by
POSITION: `n1` is "after the next meeting", `n2` the one after that. This is how the
number is actually read ("two cuts priced by the third meeting"), and it avoids minting
a new series id every eight weeks. Which meeting a node refers to travels with it as
`meta.meeting_date` / `meta.effective_date`.

What ends up in meta
--------------------
Every node carries the whole-fit quality alongside its own reliability, because a level
without them is misleading: `fit_rms_bp` (RMS of model-minus-market across the strip),
`weak` and `weight` (how much contract coverage pins this node; see the weak-node
discussion in `calcs/implied_path.py`), plus the step and cumulative change in bp.

Reference rates
---------------
r_0 is the rate the contract actually settles to, not the headline target:
  * ASX 30-day interbank futures settle to the monthly average of the RBA interbank
    overnight cash rate (AONIA), so r_0 is AONIA and the RBA target is recorded in meta
    for display. In normal conditions the two differ by a basis point or less, well
    inside the calc's stated error bounds, but using the settlement rate keeps the
    arithmetic self-consistent.
  * CME ZQ settles to the monthly average of EFFR, so r_0 is EFFR.
Days already elapsed in the front month are fed in as `realised` from the same series,
which is what stops a part-elapsed month looking like a policy move.
"""

from __future__ import annotations

import logging
import re
import traceback
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from tmd import catalog
from tmd.calcs.implied_path import Contract, PathResult, solve_path
from tmd.catalog import meetings
from tmd.core.models import IngestResult, Observation, Series
from tmd.core.store import Store
from tmd.core.validate import validate_observations

log = logging.getLogger("tmd.derive")

SYDNEY = ZoneInfo("Australia/Sydney")
NEW_YORK = ZoneInfo("America/New_York")
CHICAGO = ZoneInfo("America/Chicago")

_POSITION = re.compile(r"^m(\d+)$")


@dataclass(frozen=True)
class Derivation:
    """One implied path: which strip feeds it, and where the answer is written."""

    name: str  # ingest_runs.adapter, and the catalogue `source` of its nodes
    bank: str  # meetings.yaml bank id
    strip_source: str  # adapter owning the m1..mN strip
    strip_is_price: bool  # True -> implied rate is 100 - value
    reference_series: str  # r_0 and the realised daily rates
    node_prefix: str  # node series ids are prefix + position
    strip_tz: ZoneInfo  # to read a valuation DATE off the strip timestamp
    rate_tz: ZoneInfo  # to read effective DATES off the reference rate timestamps
    target_series: str = ""  # optional headline rate, recorded in meta only


DERIVATIONS: tuple[Derivation, ...] = (
    Derivation(
        name="derive_rba",
        bank="rba",
        strip_source="asx_rate_tracker",
        strip_is_price=False,  # ASX publishes implied yields directly
        reference_series="au.rba.cash_rate_interbank",  # AONIA, what the contract settles to
        node_prefix="au.rba.implied.n",
        strip_tz=SYDNEY,
        rate_tz=SYDNEY,
        target_series="au.rba.cash_rate_target",
    ),
    Derivation(
        name="derive_fed",
        bank="fomc",
        strip_source="fed_funds_futures",
        strip_is_price=True,  # Yahoo gives ZQ prices; 100 - price is the implied rate
        reference_series="us.nyfed.effr",
        node_prefix="us.fed.implied.n",
        strip_tz=CHICAGO,
        rate_tz=NEW_YORK,
    ),
)

# The catalogue consistency tests treat these as legitimate series owners even though
# they are not adapters: nothing fetches them, `tmd derive` computes them.
DERIVED_SOURCES: frozenset[str] = frozenset(d.name for d in DERIVATIONS)


def strip_series(source: str) -> list[Series]:
    """Catalogue entries of a rolling strip, ordered by contract position."""
    numbered: list[tuple[int, Series]] = []
    for s in catalog.by_source().get(source, []):
        m = _POSITION.match(s.source_ref)
        if m:
            numbered.append((int(m.group(1)), s))
    return [s for _, s in sorted(numbered, key=lambda p: p[0])]


def node_series(prefix: str) -> list[Series]:
    """Catalogue entries for a path's nodes, ordered by node position."""
    numbered: list[tuple[int, Series]] = []
    for s in catalog.load():
        if s.active and s.id.startswith(prefix):
            tail = s.id[len(prefix) :]
            if tail.isdigit():
                numbered.append((int(tail), s))
    return [s for _, s in sorted(numbered, key=lambda p: p[0])]


def parse_contract_month(meta: dict[str, str]) -> tuple[int, int] | None:
    """(year, month) from an observation's meta. Handles both strip conventions."""
    ym = meta.get("contract_ym", "")
    if re.fullmatch(r"\d{4}-\d{2}", ym):
        return int(ym[:4]), int(ym[5:])
    display = meta.get("expiry_month", "")  # ASX style, "Aug-26"
    if display:
        try:
            d = datetime.strptime(display, "%b-%y")
        except ValueError:
            return None
        return d.year, d.month
    return None


def collect_contracts(
    store: Store, strip: list[Series], is_price: bool
) -> tuple[list[Contract], datetime | None, list[str]]:
    """Latest observation per strip position -> Contracts. Returns (contracts, ts, notes)."""
    contracts: list[Contract] = []
    notes: list[str] = []
    latest_ts: datetime | None = None
    seen: set[tuple[int, int]] = set()
    for s in strip:
        o = store.latest(s.id)
        if o is None:
            continue
        ym = parse_contract_month(o.meta)
        if ym is None:
            notes.append(f"{s.id}: no usable contract month in meta, skipped")
            continue
        if ym in seen:
            notes.append(f"{s.id}: duplicate contract month {ym}, skipped")
            continue
        seen.add(ym)
        rate = Decimal("100") - o.value if is_price else o.value
        contracts.append(Contract(ym[0], ym[1], float(rate)))
        latest_ts = o.ts if latest_ts is None else max(latest_ts, o.ts)
    return contracts, latest_ts, notes


def realised_rates(
    store: Store, series_id: str, since: datetime, before: date, tz: ZoneInfo
) -> dict[date, float]:
    """Daily reference rates already published for the front month, keyed by their own date.

    Forward-filled across weekends and holidays, because the contracts average over
    CALENDAR days and a non-business day carries the previous business day's rate. Days
    before the first available fixing are left out, so the solver falls back to r_0 for
    them. Filling matters exactly when a policy move lands mid-month: without it, the
    weekend before a move would be back-filled with the post-move rate.
    """
    published: dict[date, float] = {}
    for o in store.history(series_id, since=since):
        d = o.ts.astimezone(tz).date()
        if d < before:
            published[d] = float(o.value)
    if not published:
        return {}
    out: dict[date, float] = {}
    day, carried = min(published), None
    while day < before:
        carried = published.get(day, carried)
        if carried is not None:
            out[day] = carried
        day += timedelta(days=1)
    return out


def path_observations(
    d: Derivation,
    result: PathResult,
    nodes: list[Series],
    ts: datetime,
    extra_meta: dict[str, str],
) -> list[Observation]:
    """One Observation per path node, carrying fit quality and the meeting it refers to."""
    fetched = datetime.now(UTC)
    shared = {
        "fit_rms_bp": str(result.rms_bp),
        "current_rate": str(result.current_rate),
        "valuation_date": result.valuation_date.isoformat(),
        **extra_meta,
    }
    by_position = {int(s.id[len(d.node_prefix) :]): s for s in nodes}
    out: list[Observation] = []
    for position, node in enumerate(result.nodes, start=1):
        series = by_position.get(position)
        series_id = series.id if series else f"{d.node_prefix}{position}"
        out.append(
            Observation(
                series_id=series_id,
                ts=ts,
                value=Decimal(str(node.implied_rate)),
                as_of=fetched,
                source_ref=f"n{position}",
                meta={
                    **shared,
                    "meeting_date": node.meeting_date.isoformat(),
                    "effective_date": node.effective_date.isoformat(),
                    "change_from_current_bp": str(node.change_from_current_bp),
                    "step_bp": str(node.step_bp),
                    "cumulative_moves": str(node.cumulative_moves),
                    "prob_move_at_meeting": str(node.prob_move_at_meeting),
                    "weight": str(node.weight),
                    "weak": "true" if node.weak else "false",
                },
            )
        )
    return out


def run_derivation(d: Derivation, source: Store, sink: Store) -> IngestResult:
    """Compute one implied path and write it. Never raises; records what happened."""
    started = datetime.now(UTC)
    notes: list[str] = []
    try:
        nodes = node_series(d.node_prefix)
        if not nodes:
            raise ValueError(f"no active node series with prefix '{d.node_prefix}' in catalogue")
        strip = strip_series(d.strip_source)
        if not strip:
            raise ValueError(f"no strip series for source '{d.strip_source}' in catalogue")

        contracts, strip_ts, strip_notes = collect_contracts(source, strip, d.strip_is_price)
        notes.extend(strip_notes)
        if not contracts or strip_ts is None:
            raise ValueError(f"no strip observations in the store for '{d.strip_source}'")
        valuation_date = strip_ts.astimezone(d.strip_tz).date()

        reference = source.latest(d.reference_series)
        if reference is None:
            raise ValueError(f"no observation for reference rate '{d.reference_series}'")
        current_rate = float(reference.value)

        bank = meetings.get(d.bank)
        pairs = bank.pairs()
        if not pairs:
            raise ValueError(f"meetings.yaml has no meetings for '{d.bank}'")
        if pairs[-1][1] < valuation_date:
            raise ValueError(
                f"meetings.yaml for '{d.bank}' ends {pairs[-1][1]}, before the valuation "
                f"date {valuation_date}; the calendar needs its yearly review"
            )

        month_start = datetime(valuation_date.year, valuation_date.month, 1, tzinfo=UTC)
        realised = realised_rates(
            source, d.reference_series, month_start, valuation_date, d.rate_tz
        )

        result = solve_path(contracts, pairs, valuation_date, current_rate, realised=realised)
        notes.extend(result.notes)
        if not result.nodes:
            raise ValueError("solver returned no nodes; strip and meeting calendar do not overlap")

        extra_meta = {
            "contracts_used": str(len(contracts)),
            "reference_series": d.reference_series,
            "realised_days": str(len(realised)),
        }
        if d.target_series:
            target = source.latest(d.target_series)
            if target is not None:
                extra_meta["target_rate"] = str(target.value)

        obs = path_observations(d, result, nodes, strip_ts, extra_meta)
        good, problems = validate_observations(obs, {s.id: s for s in nodes})
        notes.extend(problems)
        sink.upsert_series(nodes)
        written = sink.upsert_observations(good)

        status = "ok" if not problems else "partial"
        if not good:
            status = "error"
            notes.append("no valid derived observations")
        result_row = IngestResult(
            adapter=d.name,
            started_at=started,
            finished_at=datetime.now(UTC),
            status=status,
            rows_fetched=len(obs),
            rows_written=written,
            notes=notes,
        )
    except Exception as exc:  # noqa: BLE001 - record any failure, same as the runner
        log.exception("derivation %s failed", d.name)
        result_row = IngestResult(
            adapter=d.name,
            started_at=started,
            finished_at=datetime.now(UTC),
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            notes=[*notes, traceback.format_exc()[-2000:]],
        )
    sink.record_run(result_row)
    log.info(
        "%s: %s fetched=%d written=%d",
        result_row.adapter,
        result_row.status,
        result_row.rows_fetched,
        result_row.rows_written,
    )
    return result_row


def run_all(source: Store, sink: Store) -> list[IngestResult]:
    """Every derivation. One failing never stops the others."""
    return [run_derivation(d, source, sink) for d in DERIVATIONS]
