"""Unit tests for period_dates utility."""

from datetime import date
from types import SimpleNamespace

import pytest

from app.utils.period_dates import (
    add_business_days,
    compute_period_dates,
    days_30_360,
    is_business_day,
    next_business_day_on_or_after,
)


# ── is_business_day / next_business_day ──


def test_is_business_day_monday_friday():
    assert is_business_day(date(2026, 4, 13))  # Monday
    assert is_business_day(date(2026, 4, 17))  # Friday


def test_is_business_day_weekend():
    assert not is_business_day(date(2026, 4, 18))  # Saturday
    assert not is_business_day(date(2026, 4, 19))  # Sunday


def test_next_business_day_noop_on_weekday():
    d = date(2026, 4, 15)  # Wed
    assert next_business_day_on_or_after(d) == d


def test_next_business_day_bumps_saturday_to_monday():
    assert next_business_day_on_or_after(date(2026, 4, 18)) == date(2026, 4, 20)


def test_next_business_day_bumps_sunday_to_monday():
    assert next_business_day_on_or_after(date(2026, 4, 19)) == date(2026, 4, 20)


# ── add_business_days ──


def test_add_business_days_zero():
    d = date(2026, 4, 15)
    assert add_business_days(d, 0) == d


def test_add_business_days_skip_weekend():
    # Fri + 1 business day → Mon
    assert add_business_days(date(2026, 4, 17), 1) == date(2026, 4, 20)


def test_add_business_days_negative():
    # Mon - 1 business day → Fri
    assert add_business_days(date(2026, 4, 20), -1) == date(2026, 4, 17)


def test_add_business_days_four_before_distribution():
    # Distribution = Fri 2025-12-12. 4 business days before = Mon 2025-12-08.
    assert add_business_days(date(2025, 12, 12), -4) == date(2025, 12, 8)


def test_add_business_days_crosses_multiple_weeks():
    # 10 business days from a Monday lands 2 weeks later on Monday.
    assert add_business_days(date(2026, 4, 13), 10) == date(2026, 4, 27)


# ── days_30_360 ──


def test_days_30_360_same_month():
    assert days_30_360(date(2026, 1, 1), date(2026, 1, 31)) == 30


def test_days_30_360_full_year():
    assert days_30_360(date(2025, 1, 1), date(2026, 1, 1)) == 360


def test_days_30_360_month_end_d1_31_treated_as_30():
    # D1 = Jan 31 → treated as 30. End = Feb 28 → 30*1 + (28-30) = 28.
    assert days_30_360(date(2026, 1, 31), date(2026, 2, 28)) == 28


def test_days_30_360_month_end_d2_31_with_d1_gte_30():
    # D1 = Jan 30, D2 = Feb 31 (impossible but tests the rule). Use real ends.
    # Rule: if d2==31 and d1>=30, d2 → 30. Test D1=Dec 30, D2=Jan 31.
    assert days_30_360(date(2025, 12, 30), date(2026, 1, 31)) == 30


def test_days_30_360_d2_31_d1_less_than_30_keeps_31():
    # D1=Dec 15, D2=Jan 31 → (31-15) + 30 = 46
    assert days_30_360(date(2025, 12, 15), date(2026, 1, 31)) == 46


# ── compute_period_dates ──


def _deal(**overrides):
    """Build a lightweight Deal-like object with just the fields the utility reads."""
    defaults = dict(
        distribution_day_of_month=None,
        determination_business_days_before=None,
        initial_cutoff_date=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_compute_period_dates_happy_path():
    # 12th of Dec 2025 = Friday (business day, no bump).
    deal = _deal(
        distribution_day_of_month=12,
        determination_business_days_before=4,
        initial_cutoff_date=date(2025, 10, 7),
    )
    pd = compute_period_dates(deal, "2025-12", prior_distribution_date=None)

    assert pd.distribution_date == date(2025, 12, 12)
    # 4 business days before Fri Dec 12 → Mon Dec 8
    assert pd.determination_date == date(2025, 12, 8)
    # Day-count anchor: previous-month computed distribution date (2025-11-12).
    # This is the preferred recurring-cadence fallback now.
    assert pd.anchor_date == date(2025, 11, 12)
    assert pd.anchor_source == "prior_month_computed"
    assert pd.days_in_period_actual == 30
    assert pd.days_in_period_30_360 == 30


def test_compute_period_dates_weekend_bump():
    # Day-of-month 14 in Nov 2025: Nov 14 is a Friday actually; pick a weekend case.
    # Nov 15 2025 is Saturday → bump to Monday Nov 17.
    deal = _deal(distribution_day_of_month=15, initial_cutoff_date=date(2025, 10, 7))
    pd = compute_period_dates(deal, "2025-11", prior_distribution_date=None)
    assert pd.distribution_date == date(2025, 11, 17)


def test_compute_period_dates_day_beyond_month_length():
    # Feb 2026 has only 28 days. Day-of-month=31 → min(31, 28) = 28.
    deal = _deal(distribution_day_of_month=31, initial_cutoff_date=date(2026, 1, 1))
    pd = compute_period_dates(deal, "2026-02", prior_distribution_date=None)
    # Feb 28 2026 is a Saturday → bump to Mon Mar 2
    assert pd.distribution_date == date(2026, 3, 2)


def test_compute_period_dates_missing_day_returns_none():
    deal = _deal(distribution_day_of_month=None)
    pd = compute_period_dates(deal, "2025-12", prior_distribution_date=None)
    assert pd.distribution_date is None
    assert pd.determination_date is None
    assert pd.days_in_period_actual is None
    assert pd.days_in_period_30_360 is None


def test_compute_period_dates_invalid_report_period():
    deal = _deal(distribution_day_of_month=12)
    pd = compute_period_dates(deal, "not-a-period", prior_distribution_date=None)
    assert pd.distribution_date is None


def test_compute_period_dates_uses_prior_distribution_over_cutoff():
    deal = _deal(
        distribution_day_of_month=12,
        determination_business_days_before=4,
        initial_cutoff_date=date(2025, 10, 7),
    )
    pd = compute_period_dates(
        deal,
        "2026-01",
        prior_distribution_date=date(2025, 12, 12),
    )
    # Jan 12 2026 is Monday
    assert pd.distribution_date == date(2026, 1, 12)
    # Calendar days from prior distribution (not initial cutoff)
    assert pd.days_in_period_actual == (date(2026, 1, 12) - date(2025, 12, 12)).days
    assert pd.days_in_period_30_360 == 30


def test_compute_period_dates_initial_cutoff_fallback_for_first_run():
    """First run: prior-month computed date would be BEFORE initial_cutoff → fall back to cutoff."""
    deal = _deal(
        distribution_day_of_month=12,
        determination_business_days_before=4,
        # Initial cutoff is Oct 7 2025 — for the Nov 2025 run, prior-month
        # computed distribution would be Oct 12 2025 (>= cutoff), which is valid.
        # But if we're running the deal's very first period and the "prior
        # month" falls before the deal existed, use the cutoff instead.
        initial_cutoff_date=date(2025, 11, 1),
    )
    # Nov 2025: prior month would be Oct 2025 → Oct 12 computed. Oct 12 < Nov 1 cutoff → skip.
    pd = compute_period_dates(deal, "2025-11", prior_distribution_date=None)
    assert pd.distribution_date == date(2025, 11, 12)
    assert pd.anchor_date == date(2025, 11, 1)
    assert pd.anchor_source == "initial_cutoff"
    assert pd.days_in_period_actual == 11


def test_compute_period_dates_missing_initial_cutoff_still_anchors_to_prior_month():
    """Without initial_cutoff, the previous-month computed dist date still provides a usable anchor."""
    deal = _deal(
        distribution_day_of_month=12,
        determination_business_days_before=4,
        initial_cutoff_date=None,
    )
    pd = compute_period_dates(deal, "2025-12", prior_distribution_date=None)
    assert pd.distribution_date == date(2025, 12, 12)
    # Previous-month fallback kicks in regardless of initial_cutoff
    assert pd.anchor_date == date(2025, 11, 12)
    assert pd.anchor_source == "prior_month_computed"
    assert pd.days_in_period_30_360 == 30


def test_compute_period_dates_determination_only_when_days_set():
    deal = _deal(
        distribution_day_of_month=12,
        determination_business_days_before=None,
    )
    pd = compute_period_dates(deal, "2025-12", prior_distribution_date=None)
    assert pd.distribution_date == date(2025, 12, 12)
    assert pd.determination_date is None


@pytest.mark.parametrize(
    "start,end,expected",
    [
        (date(2026, 1, 1), date(2026, 2, 1), 30),
        (date(2026, 1, 15), date(2026, 2, 15), 30),
        (date(2026, 2, 15), date(2026, 3, 15), 30),
        (date(2025, 10, 7), date(2025, 12, 12), 65),
    ],
)
def test_days_30_360_various(start, end, expected):
    assert days_30_360(start, end) == expected
