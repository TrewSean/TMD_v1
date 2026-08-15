"""Implied policy-rate path from a strip of monthly-average futures.

Works for both:
  * ASX 30-day interbank cash rate futures (settle to the monthly average of the RBA
    interbank overnight cash rate, AONIA; price = 100 - average).
  * CME 30-day fed funds futures, ZQ (settle to the monthly average of the daily
    effective fed funds rate, EFFR; price = 100 - average).
Both average over CALENDAR days, with non-business days carrying the prior business
day's rate, which a piecewise-constant daily model reproduces exactly.

Method
------
Unknowns: the reference rate after each future policy meeting, r_1..r_k (r_0 = the
current reference rate, known). The rate is piecewise constant, changing only on each
meeting's *effective* date (RBA: the day after the decision; Fed: the day after).
Each contract i covering calendar month M_i has implied rate

    f_i = sum_j w_ij * r_j,   w_ij = (days of M_i under regime j) / (days in M_i)

Days already elapsed in the front month use `realised` daily rates if supplied,
else r_0. This is a linear system A r = f. It is often under- or ill-determined
(two meetings in one month; a meeting effective on the 30th leaves one day of
information), so we solve a ridge-regularised least squares that prefers
"no change from the previous meeting" where the data are silent:

    minimise ||A r - f||^2 + lam * ||D r||^2,   D = first differences (r_j - r_{j-1})

with lam small (default 1e-4). Nodes whose total data weight (column sum of A) is
below `weak_weight` are flagged `weak=True`; treat those levels as indicative only.

Error bounds
------------
On synthetic strips the fit is exact to floating point. Against real quotes expect
+/-1 to 3 bp for RBA and +/-2 to 5 bp for the Fed relative to a Bloomberg WIRP-style
screen, driven by half-tick quoting, convexity, and whether the screen builds from
OIS rather than futures. Nodes flagged weak can be off by 10 bp or more.

Everything here is pure: no I/O, no dates from the clock; the caller supplies
`valuation_date`.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

import numpy as np

STEP = 0.25  # standard policy move, in percentage points


@dataclass(frozen=True)
class Contract:
    """One futures contract, expressed as an implied average rate for a calendar month."""

    year: int
    month: int
    implied_rate: float  # 100 - price, in percent

    @property
    def start(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def end(self) -> date:  # exclusive
        y, m = (self.year + 1, 1) if self.month == 12 else (self.year, self.month + 1)
        return date(y, m, 1)

    @property
    def days(self) -> int:
        return calendar.monthrange(self.year, self.month)[1]


@dataclass(frozen=True)
class MeetingNode:
    meeting_date: date  # decision date (for display)
    effective_date: date  # first day the new rate applies
    implied_rate: float  # % after this meeting
    change_from_current_bp: float  # cumulative vs r_0
    step_bp: float  # incremental vs previous node
    cumulative_moves: float  # change_from_current / 25bp
    prob_move_at_meeting: float  # step / 25bp, clipped to [-1, 1] for display
    weight: float  # sum of A column: how much data pins this node
    weak: bool


@dataclass(frozen=True)
class PathResult:
    current_rate: float
    valuation_date: date
    nodes: list[MeetingNode]
    residuals_bp: list[float]  # per contract, model - market, bp
    rms_bp: float
    notes: list[str] = field(default_factory=list)


def _regime_index(d: date, effective_dates: list[date]) -> int:
    """0 before the first effective date, j after the j-th (1-based)."""
    j = 0
    for eff in effective_dates:
        if d >= eff:
            j += 1
        else:
            break
    return j


def build_design(
    contracts: list[Contract],
    effective_dates: list[date],
    valuation_date: date,
    current_rate: float,
    realised: dict[date, float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (A, b) for the unknowns r_1..r_k, with known r_0 folded into b."""
    k = len(effective_dates)
    a = np.zeros((len(contracts), k))
    b = np.zeros(len(contracts))
    realised = realised or {}
    for i, c in enumerate(contracts):
        known = 0.0
        d = c.start
        while d < c.end:
            if d < valuation_date:
                known += realised.get(d, current_rate)
            else:
                j = _regime_index(d, effective_dates)
                if j == 0:
                    known += current_rate
                else:
                    a[i, j - 1] += 1.0
            d += timedelta(days=1)
        a[i] /= c.days
        b[i] = c.implied_rate - known / c.days
    return a, b


def solve_path(
    contracts: list[Contract],
    meetings: list[tuple[date, date]],
    valuation_date: date,
    current_rate: float,
    realised: dict[date, float] | None = None,
    lam: float = 1e-4,
    weak_weight: float = 0.15,
) -> PathResult:
    """Fit meeting-by-meeting implied rates.

    meetings : list of (decision_date, effective_date), ascending. Only meetings whose
               effective date is >= valuation_date and <= last contract end are used.
    """
    notes: list[str] = []
    contracts = sorted(contracts, key=lambda c: (c.year, c.month))
    if not contracts:
        raise ValueError("no contracts")
    horizon = contracts[-1].end
    used = [(m, e) for (m, e) in meetings if valuation_date <= e < horizon]
    dropped = len(meetings) - len(used)
    if dropped:
        notes.append(f"{dropped} meeting(s) outside the strip horizon ignored")
    if not used:
        notes.append("no meetings in range")
        return PathResult(current_rate, valuation_date, [], [], 0.0, notes)

    eff = [e for _, e in used]
    a, b = build_design(contracts, eff, valuation_date, current_rate, realised)
    k = len(eff)

    # Ridge on first differences, anchored so r_1 is pulled toward r_0.
    d = np.zeros((k, k))
    for j in range(k):
        d[j, j] = 1.0
        if j > 0:
            d[j, j - 1] = -1.0
    # anchor: r_1 - r_0 = 0 -> D row 0 is just r_1, target current_rate
    lhs = a.T @ a + lam * (d.T @ d)
    rhs = a.T @ b + lam * (d.T @ np.r_[current_rate, np.zeros(k - 1)])
    r = np.linalg.solve(lhs, rhs)

    fitted = a @ r  # model value of the unknown part; b is the market's
    resid_bp = ((fitted - b) * 100).tolist()
    rms = float(np.sqrt(np.mean(np.square(resid_bp)))) if resid_bp else 0.0

    weights = a.sum(axis=0)
    nodes: list[MeetingNode] = []
    prev = current_rate
    for j, (mdate, edate) in enumerate(used):
        rate = float(r[j])
        step = (rate - prev) * 100
        cum = (rate - current_rate) * 100
        nodes.append(
            MeetingNode(
                meeting_date=mdate,
                effective_date=edate,
                implied_rate=round(rate, 4),
                change_from_current_bp=round(cum, 1),
                step_bp=round(step, 1),
                cumulative_moves=round(cum / (STEP * 100), 2),
                prob_move_at_meeting=round(max(-1.0, min(1.0, step / (STEP * 100))), 2),
                weight=round(float(weights[j]), 3),
                weak=bool(weights[j] < weak_weight),
            )
        )
        prev = rate
    weak = [n.meeting_date.isoformat() for n in nodes if n.weak]
    if weak:
        notes.append(f"weakly determined nodes (little contract coverage): {weak}")
    return PathResult(
        current_rate, valuation_date, nodes, [round(x, 2) for x in resid_bp], round(rms, 2), notes
    )


def contracts_from_prices(prices: dict[tuple[int, int], Decimal | float]) -> list[Contract]:
    """{(year, month): price} -> Contracts with implied_rate = 100 - price."""
    return [Contract(y, m, float(Decimal("100") - Decimal(str(p)))) for (y, m), p in prices.items()]
