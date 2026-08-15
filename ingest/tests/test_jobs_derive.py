"""`tmd derive` end to end against a MemoryStore.

The strips are built by averaging a KNOWN piecewise-constant path over each contract
month, so the test asserts the whole chain, real catalogue and real meetings.yaml
included, recovers the path it was given. That is what makes it a wiring test rather
than a restatement of the solver's own unit tests.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from tmd.catalog import meetings
from tmd.core.models import Observation
from tmd.core.store import MemoryStore
from tmd.jobs import derive

SYDNEY = ZoneInfo("Australia/Sydney")
NEW_YORK = ZoneInfo("America/New_York")
CHICAGO = ZoneInfo("America/Chicago")

VALUATION = date(2026, 8, 14)
ASX_TS = datetime(2026, 8, 14, 16, 30, tzinfo=SYDNEY).astimezone(UTC)
ZQ_TS = datetime(2026, 8, 14, 14, 0, tzinfo=CHICAGO).astimezone(UTC)

RBA_CURRENT = 4.35
FED_CURRENT = 3.63
MONTHS = [(2026, m) for m in range(8, 13)] + [(2027, m) for m in range(1, 13)] + [(2028, 1)]
DISPLAY = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _month_average(year: int, month: int, current: float, path: list[tuple[date, float]]) -> float:
    """Average a piecewise-constant path over one calendar month, as the contracts do."""
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    d, total, days = date(year, month, 1), 0.0, 0
    while d < end:
        rate = current
        for effective, r in path:
            if d >= effective:
                rate = r
        total += rate
        days += 1
        d += timedelta(days=1)
    return total / days


def _truth_path(bank_id: str, moves: dict[int, float], current: float) -> list[tuple[date, float]]:
    """Assign a cumulative rate to each meeting of a real bank calendar."""
    out: list[tuple[date, float]] = []
    rate = current
    for i, (_, effective) in enumerate(meetings.get(bank_id).pairs(), start=1):
        rate += moves.get(i, 0.0)
        out.append((effective, rate))
    return out


def _seed_reference(store: MemoryStore, series_id: str, rate: float, tz: ZoneInfo) -> None:
    """Daily fixings for the elapsed part of the front month, plus r_0 as the latest."""
    for day in range(1, VALUATION.day):
        ts = datetime(2026, 8, day, 17, 0, tzinfo=tz).astimezone(UTC)
        store.upsert_observations(
            [Observation(series_id=series_id, ts=ts, value=Decimal(str(rate)))]
        )


def _seed_strip(
    store: MemoryStore,
    prefix: str,
    path: list[tuple[date, float]],
    current: float,
    ts: datetime,
    as_price: bool,
    machine_meta: bool,
) -> None:
    for position, (year, month) in enumerate(MONTHS, start=1):
        avg = _month_average(year, month, current, path)
        value = Decimal(str(round(100 - avg, 6))) if as_price else Decimal(str(round(avg, 6)))
        meta = (
            {"contract_ym": f"{year:04d}-{month:02d}"}
            if machine_meta
            else {"expiry_month": f"{DISPLAY[month - 1]}-{year % 100:02d}"}
        )
        store.upsert_observations(
            [
                Observation(
                    series_id=f"{prefix}{position}",
                    ts=ts,
                    value=value,
                    source_ref=f"m{position}",
                    meta=meta,
                )
            ]
        )


@pytest.fixture
def seeded():
    """A store holding both strips and both reference rates, from known paths."""
    store = MemoryStore()
    # RBA: hold, then 25bp of cuts at meetings 3 and 5.
    rba_path = _truth_path("rba", {3: -0.25, 5: -0.25}, RBA_CURRENT)
    _seed_strip(store, "au.asx.ib.implied.m", rba_path, RBA_CURRENT, ASX_TS, False, False)
    _seed_reference(store, "au.rba.cash_rate_interbank", RBA_CURRENT, SYDNEY)
    store.upsert_observations(
        [
            Observation(
                series_id="au.rba.cash_rate_target", ts=ASX_TS, value=Decimal(str(RBA_CURRENT))
            )
        ]
    )
    # Fed: one cut at the second meeting, another at the fourth.
    fed_path = _truth_path("fomc", {2: -0.25, 4: -0.25}, FED_CURRENT)
    _seed_strip(store, "us.cme.zq.m", fed_path, FED_CURRENT, ZQ_TS, True, True)
    _seed_reference(store, "us.nyfed.effr", FED_CURRENT, NEW_YORK)
    return store, rba_path, fed_path


def test_both_derivations_run_and_write(seeded):
    source, _, _ = seeded
    sink = MemoryStore()
    results = derive.run_all(source, sink)

    assert [r.adapter for r in results] == ["derive_rba", "derive_fed"]
    assert all(r.status == "ok" for r in results), [(r.adapter, r.error, r.notes) for r in results]
    assert all(r.rows_written == r.rows_fetched > 0 for r in results)
    # Every run is recorded for the health view, and the node series are registered
    # before their observations so the foreign key holds in Postgres.
    assert len(sink.runs) == 2
    assert "au.rba.implied.n1" in sink.series
    assert "us.fed.implied.n1" in sink.series


def test_rba_path_recovers_the_known_curve(seeded):
    source, rba_path, _ = seeded
    sink = MemoryStore()
    derive.run_derivation(derive.DERIVATIONS[0], source, sink)

    nodes = sorted(
        (o for (sid, _), o in sink.obs.items() if sid.startswith("au.rba.implied.n")),
        key=lambda o: int(o.source_ref[1:]),
    )
    assert len(nodes) == len(meetings.get("rba").pairs()) == 11
    for node, (_, truth) in zip(nodes, rba_path, strict=True):
        assert float(node.value) == pytest.approx(truth, abs=3e-3)

    # The cuts land on the meetings they were put on, not smeared across neighbours.
    assert float(nodes[2].meta["step_bp"]) == pytest.approx(-25.0, abs=0.5)
    assert float(nodes[4].meta["step_bp"]) == pytest.approx(-25.0, abs=0.5)
    assert float(nodes[1].meta["step_bp"]) == pytest.approx(0.0, abs=0.5)
    assert float(nodes[-1].meta["change_from_current_bp"]) == pytest.approx(-50.0, abs=1.0)


def test_fed_path_inverts_prices_and_recovers_the_curve(seeded):
    source, _, fed_path = seeded
    sink = MemoryStore()
    derive.run_derivation(derive.DERIVATIONS[1], source, sink)

    nodes = sorted(
        (o for (sid, _), o in sink.obs.items() if sid.startswith("us.fed.implied.n")),
        key=lambda o: int(o.source_ref[1:]),
    )
    assert len(nodes) == 11
    for node, (_, truth) in zip(nodes, fed_path, strict=True):
        assert float(node.value) == pytest.approx(truth, abs=3e-3)
    # ZQ is stored as a price; a failure to do 100 - price would land near 96, not 3.6.
    assert all(Decimal("2") < o.value < Decimal("5") for o in nodes)


def test_meta_carries_fit_quality_and_the_meeting_it_refers_to(seeded):
    source, _, _ = seeded
    sink = MemoryStore()
    derive.run_derivation(derive.DERIVATIONS[0], source, sink)
    node = sink.obs[("au.rba.implied.n1", ASX_TS)]

    assert node.ts == ASX_TS  # the path is stamped with the market date it was struck on
    assert node.meta["meeting_date"] == "2026-09-29"
    assert node.meta["effective_date"] == "2026-09-30"
    assert node.meta["valuation_date"] == VALUATION.isoformat()
    assert node.meta["weak"] in {"true", "false"}
    assert float(node.meta["fit_rms_bp"]) < 1.0  # synthetic strip, so the fit is near exact
    assert float(node.meta["weight"]) > 0
    assert node.meta["contracts_used"] == str(len(MONTHS))
    assert node.meta["reference_series"] == "au.rba.cash_rate_interbank"
    assert node.meta["target_rate"] == str(RBA_CURRENT)
    # Elapsed days of the front month were fed in rather than assumed.
    assert int(node.meta["realised_days"]) == VALUATION.day - 1


def test_missing_inputs_are_recorded_as_an_error_not_raised():
    empty, sink = MemoryStore(), MemoryStore()
    results = derive.run_all(empty, sink)

    assert all(r.status == "error" for r in results)
    assert all("no strip observations" in (r.error or "") for r in results)
    assert len(sink.runs) == 2  # still recorded, so adapter_health shows the failure
    assert not sink.obs  # and nothing was invented


def test_missing_reference_rate_is_an_error(seeded):
    source, _, _ = seeded
    # Drop the reference rate but keep the strip.
    source.obs = {k: v for k, v in source.obs.items() if k[0] != "au.rba.cash_rate_interbank"}
    sink = MemoryStore()
    result = derive.run_derivation(derive.DERIVATIONS[0], source, sink)
    assert result.status == "error"
    assert "reference rate" in (result.error or "")


def test_realised_rates_forward_fill_across_non_business_days():
    # Contracts average over CALENDAR days, so a weekend carries Friday's rate.
    store = MemoryStore()
    for day, rate in ((6, 4.35), (7, 4.35), (10, 4.10)):  # Thu, Fri, then Mon after a cut
        store.upsert_observations(
            [
                Observation(
                    series_id="au.rba.cash_rate_interbank",
                    ts=datetime(2026, 8, day, 17, 0, tzinfo=SYDNEY).astimezone(UTC),
                    value=Decimal(str(rate)),
                )
            ]
        )
    got = derive.realised_rates(
        store,
        "au.rba.cash_rate_interbank",
        datetime(2026, 8, 1, tzinfo=UTC),
        date(2026, 8, 12),
        SYDNEY,
    )
    assert got[date(2026, 8, 8)] == 4.35  # Saturday carries Friday
    assert got[date(2026, 8, 9)] == 4.35  # Sunday too
    assert got[date(2026, 8, 10)] == 4.10  # Monday's own fixing, post-cut
    assert got[date(2026, 8, 11)] == 4.10  # Tuesday not yet published, carries Monday
    # Nothing invented before the first fixing; the solver falls back to r_0 there.
    assert date(2026, 8, 5) not in got
    assert max(got) == date(2026, 8, 11)


def test_contract_month_parsing_handles_both_strip_conventions():
    assert derive.parse_contract_month({"contract_ym": "2027-01"}) == (2027, 1)
    assert derive.parse_contract_month({"expiry_month": "Aug-26"}) == (2026, 8)
    assert derive.parse_contract_month({"expiry_month": "Jan-28"}) == (2028, 1)
    # contract_ym wins when both are present.
    assert derive.parse_contract_month({"contract_ym": "2027-05", "expiry_month": "Aug-26"}) == (
        2027,
        5,
    )
    assert derive.parse_contract_month({}) is None
    assert derive.parse_contract_month({"expiry_month": "nonsense"}) is None


def test_catalogue_wiring_matches_the_derivations():
    for d in derive.DERIVATIONS:
        strip = derive.strip_series(d.strip_source)
        nodes = derive.node_series(d.node_prefix)
        assert len(strip) == 18, d.name
        assert [s.source_ref for s in strip][:3] == ["m1", "m2", "m3"]
        assert len(nodes) == 12, d.name
        assert all(s.source == d.name for s in nodes)
        assert all("derived" in s.tags for s in nodes)
