"""Business-day and period-date utilities.

Business-day rules here are Mon–Fri only (no holiday calendar). They're used
strictly for *bumping* distribution/determination dates off weekends. Day-count
for interest accrual uses calendar days or the 30/360 convention, never
business days.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.deal import Deal


def is_business_day(d: date) -> bool:
    """True for Mon–Fri."""
    return d.weekday() < 5


def next_business_day_on_or_after(d: date) -> date:
    """Return d if it's Mon–Fri, else the next Mon–Fri."""
    while not is_business_day(d):
        d = d + timedelta(days=1)
    return d


def add_business_days(d: date, n: int) -> date:
    """Add n Mon–Fri days. n may be negative."""
    if n == 0:
        return d
    step = 1 if n > 0 else -1
    remaining = abs(n)
    current = d
    while remaining > 0:
        current = current + timedelta(days=step)
        if is_business_day(current):
            remaining -= 1
    return current


def days_30_360(start: date, end: date) -> int:
    """Days between two dates under the 30/360 (US) convention.

    Rule: (Y2-Y1)*360 + (M2-M1)*30 + (D2-D1) with end-of-month adjustments:
      - if D1 == 31, treat as 30
      - if D2 == 31 and D1 >= 30, treat D2 as 30
    """
    y1, m1, d1 = start.year, start.month, start.day
    y2, m2, d2 = end.year, end.month, end.day
    if d1 == 31:
        d1 = 30
    if d2 == 31 and d1 >= 30:
        d2 = 30
    return (y2 - y1) * 360 + (m2 - m1) * 30 + (d2 - d1)


@dataclass
class PeriodDates:
    distribution_date: date | None
    determination_date: date | None
    days_in_period_actual: int | None
    days_in_period_30_360: int | None
    # Anchor used for day-count. Either the prior run's distribution date,
    # the previous month's computed distribution date, or the deal's initial
    # cutoff date for the very first run.
    anchor_date: date | None = None
    anchor_source: str | None = None  # "prior_run" | "prior_month_computed" | "initial_cutoff"


def _parse_period(report_period: str) -> tuple[int, int] | None:
    """Parse YYYY-MM into (year, month), or return None if invalid."""
    try:
        y_str, m_str = report_period.split("-", 1)
        y, m = int(y_str), int(m_str)
        if not (1 <= m <= 12):
            return None
        return y, m
    except (ValueError, AttributeError):
        return None


def compute_distribution_date(
    deal: "Deal",
    report_period: str,
) -> date | None:
    """Scheduled distribution date for the given report period, bumped off weekends."""
    if not deal.distribution_day_of_month:
        return None
    parsed = _parse_period(report_period)
    if not parsed:
        return None
    year, month = parsed
    last_dom = calendar.monthrange(year, month)[1]
    day = min(deal.distribution_day_of_month, last_dom)
    return next_business_day_on_or_after(date(year, month, day))


def compute_determination_date(
    deal: "Deal",
    distribution_date: date | None,
) -> date | None:
    if distribution_date is None or deal.determination_business_days_before is None:
        return None
    return add_business_days(distribution_date, -int(deal.determination_business_days_before))


def _previous_report_period(report_period: str) -> str | None:
    """Return the YYYY-MM string for the month before `report_period`."""
    parsed = _parse_period(report_period)
    if not parsed:
        return None
    y, m = parsed
    if m == 1:
        return f"{y - 1}-12"
    return f"{y}-{m - 1:02d}"


def compute_period_dates(
    deal: "Deal",
    report_period: str,
    prior_distribution_date: date | None,
) -> PeriodDates:
    """Compute all period dates for a deal + report_period.

    Day-count anchor selection (in priority order):
      1. Prior run's actual distribution_date (when a prior run exists).
      2. Previous month's computed distribution date (recurring cadence).
         Used when no prior run exists but the deal has been active for a
         while — avoids spuriously anchoring to `initial_cutoff_date` many
         years back.
      3. Deal's `initial_cutoff_date` (first-month-ever / origination run).
    """
    dist = compute_distribution_date(deal, report_period)
    det = compute_determination_date(deal, dist)

    anchor: date | None = None
    anchor_source: str | None = None

    if prior_distribution_date is not None:
        anchor = prior_distribution_date
        anchor_source = "prior_run"
    else:
        # Try previous-month computed distribution date
        prior_period = _previous_report_period(report_period)
        if prior_period:
            prior_month_dist = compute_distribution_date(deal, prior_period)
            if prior_month_dist is not None and (
                deal.initial_cutoff_date is None
                or prior_month_dist >= deal.initial_cutoff_date
            ):
                anchor = prior_month_dist
                anchor_source = "prior_month_computed"

        # Fall back to initial cutoff (first-ever run)
        if anchor is None and deal.initial_cutoff_date is not None:
            anchor = deal.initial_cutoff_date
            anchor_source = "initial_cutoff"

    if dist is not None and anchor is not None:
        days_actual: int | None = (dist - anchor).days
        days_30_360_val: int | None = days_30_360(anchor, dist)
    else:
        days_actual = None
        days_30_360_val = None

    return PeriodDates(
        distribution_date=dist,
        determination_date=det,
        days_in_period_actual=days_actual,
        days_in_period_30_360=days_30_360_val,
        anchor_date=anchor,
        anchor_source=anchor_source,
    )
