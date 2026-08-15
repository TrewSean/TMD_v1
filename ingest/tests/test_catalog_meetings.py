"""meetings.yaml is hand-transcribed from two HTML pages, so these tests are the
only thing standing between a typo and a wrong implied path. They are deliberately
picky about shape, order and weekday."""

from datetime import date

import pytest

from tmd.catalog import meetings as mtg


def test_loads_both_banks_with_the_expected_shape():
    banks = mtg.load()
    assert set(banks) == {"rba", "fomc"}
    for bank in banks.values():
        assert bank.meetings, f"{bank.id} has no meetings"
        assert bank.source_url.startswith("https://")
        assert all(isinstance(m.decision, date) for m in bank.meetings)
        assert all(isinstance(m.effective, date) for m in bank.meetings)


def test_decision_dates_ascend_and_are_unique():
    for bank in mtg.load().values():
        decisions = [m.decision for m in bank.meetings]
        assert decisions == sorted(decisions), f"{bank.id} out of order"
        assert len(decisions) == len(set(decisions)), f"{bank.id} has duplicates"


def test_effective_is_the_day_after_the_decision():
    for bank in mtg.load().values():
        for m in bank.meetings:
            assert m.effective > m.decision
            assert (m.effective - m.decision).days == 1, f"{bank.id} {m.decision}"


def test_decisions_fall_on_the_published_weekday():
    # RBA announces Tuesday, FOMC announces Wednesday; both take effect the next
    # business day. If a transcribed date lands on the wrong weekday it is a typo.
    assert mtg.get("rba").decision_weekday == 1
    assert mtg.get("fomc").decision_weekday == 2
    for bank in mtg.load().values():
        for m in bank.meetings:
            assert m.decision.weekday() == bank.decision_weekday, f"{bank.id} {m.decision}"
            assert m.effective.weekday() < 5, f"{bank.id} {m.effective} is a weekend"


def test_calendar_covers_the_rest_of_2026_and_all_of_2027():
    for bank in mtg.load().values():
        years = {m.decision.year for m in bank.meetings}
        assert years == {2026, 2027}
        # Both banks meet eight times a year; 2027 must be complete.
        assert sum(1 for m in bank.meetings if m.decision.year == 2027) == 8


def test_known_dates_match_the_publishers():
    # Spot checks against the two published schedules. The ASX rate tracker file
    # independently reports Nxt_RBA_Mtng_Dt = 2026-09-29, which agrees.
    rba = [m.decision for m in mtg.get("rba").meetings]
    assert rba[0] == date(2026, 9, 29)
    assert date(2027, 5, 4) in rba
    fomc = mtg.get("fomc").meetings
    assert fomc[0].decision == date(2026, 9, 16)
    assert fomc[0].projections is True
    assert next(m for m in fomc if m.decision == date(2026, 10, 28)).projections is False


def test_pairs_and_upcoming_filter_by_date():
    rba = mtg.get("rba")
    pairs = rba.pairs()
    assert pairs[0] == (date(2026, 9, 29), date(2026, 9, 30))
    assert all(isinstance(p, tuple) and len(p) == 2 for p in pairs)
    # `since` drops meetings already in force.
    later = rba.pairs(since=date(2027, 1, 1))
    assert later[0] == (date(2027, 2, 9), date(2027, 2, 10))
    assert len(later) < len(pairs)
    assert rba.next_after(date(2026, 10, 1)).decision == date(2026, 11, 3)
    assert rba.next_after(date(2030, 1, 1)) is None


def test_loader_rejects_an_inconsistent_calendar(tmp_path):
    bad = tmp_path / "meetings.yaml"
    base = (
        "banks:\n"
        "  - id: rba\n"
        "    name: Test\n"
        "    country: AU\n"
        "    rate_series: au.rba.cash_rate_target\n"
        "    source_url: https://example.org/\n"
        "    reviewed: 2026-08-15\n"
        "    decision_weekday: 1\n"
        "    meetings:\n"
    )
    # effective before decision
    bad.write_text(base + "      - {decision: 2026-09-29, effective: 2026-09-28}\n")
    with pytest.raises(mtg.MeetingsError, match="must be after"):
        mtg.load.__wrapped__(bad)
    # out of order
    bad.write_text(
        base
        + "      - {decision: 2026-11-03, effective: 2026-11-04}\n"
        + "      - {decision: 2026-09-29, effective: 2026-09-30}\n"
    )
    with pytest.raises(mtg.MeetingsError, match="ascend"):
        mtg.load.__wrapped__(bad)
    # wrong weekday (2026-09-30 is a Wednesday, not a Tuesday)
    bad.write_text(base + "      - {decision: 2026-09-30, effective: 2026-10-01}\n")
    with pytest.raises(mtg.MeetingsError, match="expected weekday"):
        mtg.load.__wrapped__(bad)
    # no banks at all
    bad.write_text("banks: []\n")
    with pytest.raises(mtg.MeetingsError, match="no banks"):
        mtg.load.__wrapped__(bad)
