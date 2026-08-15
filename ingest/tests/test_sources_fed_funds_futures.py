"""ZQ strip tests. The frame test runs against a real recorded download, including
the far contract that Yahoo had no data for, which is the normal case at the far end."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
import pytest

from tmd.sources.fed_funds_futures import (
    contract_symbol,
    observations_from_closes,
    strip_months,
)

STRIP = {f"m{i}": f"us.cme.zq.m{i}" for i in range(1, 19)}


@pytest.fixture
def closes(fixture_path):
    return pd.read_csv(
        fixture_path("fed_funds_futures_closes_sample.csv"), index_col=0, parse_dates=True
    )


def test_contract_symbol_uses_cbot_month_codes():
    assert contract_symbol(2026, 1) == "ZQF26.CBT"
    assert contract_symbol(2026, 9) == "ZQU26.CBT"
    assert contract_symbol(2026, 12) == "ZQZ26.CBT"
    assert contract_symbol(2028, 1) == "ZQF28.CBT"
    with pytest.raises(ValueError):
        contract_symbol(2026, 13)


def test_strip_months_rolls_across_the_year_boundary():
    months = strip_months(date(2026, 8, 15), count=18)
    assert len(months) == 18
    assert months[0] == (2026, 8)  # m1 is the current month's contract
    assert months[4] == (2026, 12)
    assert months[5] == (2027, 1)
    assert months[-1] == (2028, 1)
    # Strictly increasing, no gaps.
    assert all(
        (b[0] - a[0]) * 12 + (b[1] - a[1]) == 1 for a, b in zip(months, months[1:], strict=False)
    )


def test_observations_from_recorded_strip(closes):
    months = strip_months(date(2026, 8, 15))
    obs = observations_from_closes(closes, months, STRIP)

    # 17 of 18: Jan-28 was not yet trading on Yahoo, so it is simply absent.
    assert len(obs) == 17
    by_ref = {o.source_ref: o for o in obs}
    assert "m18" not in by_ref

    front = by_ref["m1"]
    assert front.series_id == "us.cme.zq.m1"
    assert front.value == Decimal("96.3675")
    assert front.meta["symbol"] == "ZQQ26.CBT"
    assert front.meta["contract_ym"] == "2026-08"
    assert front.meta["expiry_month"] == "Aug-26"

    # 14:00 America/Chicago on the last session (14 Aug 2026, CDT = UTC-5) -> 19:00 UTC.
    assert front.ts == datetime(2026, 8, 14, 19, 0, tzinfo=UTC)
    assert all(o.ts == front.ts for o in obs)
    assert all(o.ts.tzinfo == UTC for o in obs)

    # The strip is stored as prices, not rates; rates are calcs' job.
    assert all(Decimal("90") < o.value < Decimal("101") for o in obs)
    assert by_ref["m5"].meta["contract_ym"] == "2026-12"
    assert by_ref["m6"].meta["contract_ym"] == "2027-01"


def test_only_the_latest_bar_is_stored(closes):
    # A position means a different contract either side of a roll, so older bars must
    # not be filed under today's position.
    obs = observations_from_closes(closes, strip_months(date(2026, 8, 15)), STRIP)
    assert len({o.ts for o in obs}) == 1
    assert len(obs) == len({(o.series_id, o.ts) for o in obs})


def test_positions_not_in_the_catalogue_are_skipped(closes):
    obs = observations_from_closes(
        closes, strip_months(date(2026, 8, 15)), {"m1": "us.cme.zq.m1", "m3": "us.cme.zq.m3"}
    )
    assert [o.source_ref for o in obs] == ["m1", "m3"]


def test_an_all_nan_contract_leaves_a_gap_rather_than_a_zero():
    frame = pd.DataFrame(
        {"ZQQ26.CBT": [96.5, 96.4], "ZQU26.CBT": [None, None]},
        index=pd.to_datetime(["2026-08-13", "2026-08-14"]),
    )
    obs = observations_from_closes(frame, [(2026, 8), (2026, 9)], STRIP)
    assert [o.source_ref for o in obs] == ["m1"]
    assert obs[0].value == Decimal("96.4000")


def test_float32_artefacts_are_quantised_back_to_the_quoted_tick():
    # Yahoo widens float32 to float64, so a 96.3675 tick arrives with a long tail.
    frame = pd.DataFrame({"ZQQ26.CBT": [96.36750030517578]}, index=pd.to_datetime(["2026-08-14"]))
    obs = observations_from_closes(frame, [(2026, 8)], STRIP)
    assert obs[0].value == Decimal("96.3675")
    assert str(obs[0].value) == "96.3675"
