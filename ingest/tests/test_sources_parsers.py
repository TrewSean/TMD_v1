"""Parser tests run against recorded fixtures. No network in CI."""

from datetime import UTC, datetime
from decimal import Decimal

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
