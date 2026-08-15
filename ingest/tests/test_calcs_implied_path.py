"""Implied path solver tested against synthetic strips built from a KNOWN path."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from tmd.calcs.implied_path import Contract, build_design, contracts_from_prices, solve_path


def _synthetic_strip(path, valuation, months, current, realised=None):
    """Average a piecewise-constant path over calendar months -> Contracts.

    path: list of (effective_date, rate). Rate before first effective = current.
    """
    out = []
    for y, m in months:
        c = Contract(y, m, 0.0)
        tot = 0.0
        d = c.start
        while d < c.end:
            if d < valuation and realised and d in realised:
                rate = realised[d]
            else:
                rate = current
                for eff, r in path:
                    if d >= eff:
                        rate = r
            tot += rate
            d += timedelta(days=1)
        out.append(Contract(y, m, tot / c.days))
    return out


VAL = date(2026, 8, 3)
MEETINGS = [
    (date(2026, 8, 11), date(2026, 8, 12)),
    (date(2026, 9, 29), date(2026, 9, 30)),
    (date(2026, 11, 3), date(2026, 11, 4)),
    (date(2026, 12, 8), date(2026, 12, 9)),
    (date(2027, 2, 16), date(2027, 2, 17)),
]
MONTHS = [(2026, m) for m in range(8, 13)] + [(2027, m) for m in range(1, 5)]


def test_recovers_known_path_exactly():
    current = 4.35
    truth = [
        (date(2026, 8, 12), 4.35),
        (date(2026, 9, 30), 4.35),
        (date(2026, 11, 4), 4.60),
        (date(2026, 12, 9), 4.60),
        (date(2027, 2, 17), 4.85),
    ]
    strip = _synthetic_strip(truth, VAL, MONTHS, current)
    res = solve_path(strip, MEETINGS, VAL, current)
    got = [n.implied_rate for n in res.nodes]
    for g, (_, t) in zip(got, truth, strict=True):
        assert g == pytest.approx(t, abs=2e-3)
    assert res.rms_bp < 0.05
    assert res.nodes[2].step_bp == pytest.approx(25.0, abs=0.3)
    assert res.nodes[2].prob_move_at_meeting == pytest.approx(1.0, abs=0.02)
    assert res.nodes[-1].cumulative_moves == pytest.approx(2.0, abs=0.02)


def test_weak_node_flagged_when_meeting_sits_at_month_end():
    # 29 Sep meeting effective 30 Sep: only one day of the Sep contract sees it.
    current = 4.35
    truth = [(e, 4.35) for _, e in MEETINGS]
    strip = _synthetic_strip(truth, VAL, MONTHS, current)
    res = solve_path(strip, MEETINGS, VAL, current)
    sep = next(n for n in res.nodes if n.meeting_date == date(2026, 9, 29))
    # weight = 1/30 from Sep + full Oct = ~1.03; not weak by total weight, but the Oct
    # contract also carries the Nov meeting? No, Nov 4 is in Nov. So Sep node is well pinned
    # by the clean October contract. Check that logic: weight > 0.9.
    assert sep.weight > 0.9
    # Now drop the October contract: Sep node has only 1/30 of a month of data -> weak.
    strip2 = [c for c in strip if (c.year, c.month) != (2026, 10)]
    res2 = solve_path(strip2, MEETINGS, VAL, current)
    sep2 = next(n for n in res2.nodes if n.meeting_date == date(2026, 9, 29))
    assert sep2.weak
    assert any("weakly determined" in n for n in res2.notes)


def test_realised_days_in_front_month_used():
    current = 3.63
    realised = {date(2026, 8, d): 3.60 for d in range(1, 3)}  # 1-2 Aug realised lower
    truth = [(e, 3.63) for _, e in MEETINGS]
    strip = _synthetic_strip(truth, VAL, MONTHS, current, realised)
    # Without realised info the front contract looks like a tiny cut; with it, flat.
    res_flat = solve_path(strip, MEETINGS, VAL, current, realised=realised)
    assert res_flat.nodes[0].step_bp == pytest.approx(0.0, abs=0.2)
    res_naive = solve_path(strip, MEETINGS, VAL, current)
    assert res_naive.nodes[0].step_bp < res_flat.nodes[0].step_bp


def test_meetings_outside_horizon_ignored_and_prices_helper():
    prices = {(2026, 8): Decimal("95.65"), (2026, 9): Decimal("95.65")}
    strip = contracts_from_prices(prices)
    assert strip[0].implied_rate == pytest.approx(4.35)
    res = solve_path(strip, MEETINGS, VAL, 4.35)
    assert [n.meeting_date for n in res.nodes] == [date(2026, 8, 11), date(2026, 9, 29)]
    assert any("ignored" in n for n in res.notes)


def test_design_matrix_rows_sum_to_one_including_known_part():
    strip = _synthetic_strip([], VAL, [(2026, 8), (2026, 9)], 4.35)
    a, b = build_design(strip, [date(2026, 8, 12)], VAL, 4.35)
    # August: 11 days known (1-11), 20 days under regime 1
    assert a[0, 0] == pytest.approx(20 / 31)
    assert a[1, 0] == pytest.approx(1.0)
    assert b[0] == pytest.approx(4.35 - 4.35 * 11 / 31)
