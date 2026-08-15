"""Parser tests run against recorded fixtures. No network in CI."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tmd.core.adapter import AdapterError
from tmd.sources.asx_rate_tracker import (
    parse_dynamic_text,
    parse_market_exp,
    parse_yield_curve,
)
from tmd.sources.nyfed_rates import parse_ref_rates
from tmd.sources.rba_tables import parse_rba_csv
from tmd.sources.ust_par import parse_ust_csv


def test_rba_f1_parses_cash_rate_and_bbsw(fixture_text):
    obs = parse_rba_csv(
        fixture_text("rba_f1_sample.csv"),
        {"FIRMMCRTD": "au.rba.cash_rate_target", "FIRMMBAB90D": "au.bbsw.3m"},
        since=None,
    )
    by = {(o.series_id, o.ts.date()): o.value for o in obs}
    assert ("au.rba.cash_rate_target", datetime(2026, 8, 13).date()) in by
    assert by[("au.rba.cash_rate_target", datetime(2026, 8, 13).date())] == Decimal("4.35")
    assert by[("au.bbsw.3m", datetime(2026, 8, 13).date())] == Decimal("4.51")
    # 14 Aug row has empty cash rate cell -> no observation for it
    assert ("au.rba.cash_rate_target", datetime(2026, 8, 14).date()) not in by
    assert all(o.ts.tzinfo == UTC for o in obs)


def test_rba_f2_parses_acgb(fixture_text):
    obs = parse_rba_csv(
        fixture_text("rba_f2_sample.csv"),
        {"FCMYGBAG10D": "au.acgb.10y", "FCMYGBAG2D": "au.acgb.2y"},
        since=None,
    )
    assert {o.series_id for o in obs} == {"au.acgb.10y", "au.acgb.2y"}
    assert all(Decimal("0") < o.value < Decimal("20") for o in obs)


def test_ust_par_parses(fixture_text):
    obs = parse_ust_csv(
        fixture_text("ust_par_sample.csv"),
        {"2 Yr": "us.ust.par.2y", "10 Yr": "us.ust.par.10y", "30 Yr": "us.ust.par.30y"},
        since=None,
    )
    latest = max(obs, key=lambda o: o.ts)
    assert latest.ts.date() == datetime(2026, 8, 14).date()
    vals = {o.series_id: o.value for o in obs if o.ts == latest.ts}
    assert vals["us.ust.par.10y"] == Decimal("4.68")
    assert vals["us.ust.par.2y"] == Decimal("4.17")


def test_nyfed_sofr_and_effr(fixture_text):
    import json

    sofr = parse_ref_rates(
        json.loads(fixture_text("nyfed_sofr_sample.json")), "us.nyfed.sofr", "sofr"
    )
    effr = parse_ref_rates(
        json.loads(fixture_text("nyfed_effr_sample.json")), "us.nyfed.effr", "effr"
    )
    assert len(sofr) == 3 and len(effr) == 3
    assert max(effr, key=lambda o: o.ts).meta["targetRateTo"] == "3.75"
    assert all(o.series_id == "us.nyfed.sofr" for o in sofr)


# --------------------------------------------------------------- ASX 30-day interbank futures

STRIP = {f"m{i}": f"au.asx.ib.implied.m{i}" for i in range(1, 19)}
HEADLINES = {
    "Crnt_Dy_Stlmnt_Price": "au.asx.ib.front_settlement",
    "Ftre_Cash_Rate": "au.asx.ib.expected_cash_rate",
    "Ftre_Cash_Rate_Change": "au.asx.ib.expected_change",
}
PROB = {"Prob_Change": "au.asx.ib.prob_change"}

# 13 Aug 2026 16:30 Sydney (AEST, UTC+10) == 06:30 UTC the same day.
SETTLED = datetime(2026, 8, 13, 6, 30, tzinfo=UTC)


def test_asx_yield_curve_parses_the_whole_strip(fixture_text):
    payload = json.loads(fixture_text("asx_rate_tracker_yield_curve_sample.json"))
    obs = parse_yield_curve(payload, STRIP)

    assert len(obs) == 18
    assert all(o.ts == SETTLED for o in obs)
    by_ref = {o.source_ref: o for o in obs}
    # Front contract: the value, and the contract it actually refers to.
    assert by_ref["m1"].value == Decimal("4.345")
    assert by_ref["m1"].series_id == "au.asx.ib.implied.m1"
    assert by_ref["m1"].meta["expiry_month"] == "Aug-26"
    assert by_ref["m1"].meta["rba_target_cash_rate"] == "4.35"
    # The strip is ordered, and position 18 is the far end of it.
    assert by_ref["m18"].meta["expiry_month"] == "Jan-28"
    assert all(Decimal("0") < o.value < Decimal("20") for o in obs)


def test_asx_yield_curve_ignores_positions_not_in_the_catalogue(fixture_text):
    payload = json.loads(fixture_text("asx_rate_tracker_yield_curve_sample.json"))
    obs = parse_yield_curve(payload, {"m1": "au.asx.ib.implied.m1", "m2": "au.asx.ib.implied.m2"})
    assert [o.source_ref for o in obs] == ["m1", "m2"]


def test_asx_yield_curve_leaves_a_gap_rather_than_inventing_a_number():
    payload = {
        "Crnt_Stlmnt_Dt": "2026-08-13",
        "RBA_Trgt_Cash_Rate": 4.35,
        "months": [
            {"Expiry_Month": "Aug-26", "Implied_Yield": 4.345},
            {"Expiry_Month": "Sep-26", "Implied_Yield": None},
            {"Expiry_Month": "Oct-26", "Implied_Yield": 4.38},
        ],
    }
    obs = parse_yield_curve(payload, STRIP)
    # m2 is missing upstream, so it is simply absent; m3 keeps its own position.
    assert [o.source_ref for o in obs] == ["m1", "m3"]
    assert obs[1].meta["expiry_month"] == "Oct-26"


def test_asx_dynamic_text_parses_headline_numbers(fixture_text):
    payload = json.loads(fixture_text("asx_rate_tracker_dynamic_text_sample.json"))
    obs = parse_dynamic_text(payload, HEADLINES)

    vals = {o.series_id: o.value for o in obs}
    assert vals["au.asx.ib.front_settlement"] == Decimal("95.65")
    assert vals["au.asx.ib.expected_cash_rate"] == Decimal("4.1")
    assert vals["au.asx.ib.expected_change"] == Decimal("-0.25")
    assert all(o.ts == SETTLED for o in obs)
    # The meeting the expectation refers to travels with the number.
    meta = next(o.meta for o in obs if o.series_id == "au.asx.ib.expected_cash_rate")
    assert meta["nxt_rba_mtng_dt"] == "2026-09-29"
    assert meta["rba_mtng_dt"] == "2026-08-11"


def test_asx_market_exp_parses_probability_history(fixture_text):
    payload = json.loads(fixture_text("asx_rate_tracker_market_exp_sample.json"))
    obs = parse_market_exp(payload, PROB)

    assert len(obs) == 15
    assert {o.series_id for o in obs} == {"au.asx.ib.prob_change"}
    assert all(Decimal("0") <= o.value <= Decimal("100") for o in obs)
    latest = max(obs, key=lambda o: o.ts)
    assert latest.ts == SETTLED
    assert latest.meta["prob_no_change"] == "100"
    assert all(o.ts.tzinfo == UTC for o in obs)


def test_asx_parsers_fail_loudly_on_a_changed_shape():
    with pytest.raises(AdapterError):
        parse_yield_curve({"Crnt_Stlmnt_Dt": "2026-08-13", "months": []}, STRIP)
    with pytest.raises(AdapterError):
        parse_market_exp({"days": "nope"}, PROB)
    with pytest.raises(AdapterError):
        parse_dynamic_text({"Crnt_Stlmnt_Dt": "13/08/2026"}, HEADLINES)
    with pytest.raises(AdapterError):
        parse_yield_curve(["not", "an", "object"], STRIP)
