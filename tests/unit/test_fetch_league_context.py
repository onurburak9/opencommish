"""Tests for cron/fetch_league_context.py — week metadata logic."""

from datetime import date

from cron.fetch_league_context import get_week_metadata, TURKISH_DAYS


def test_week_metadata_monday():
    meta = get_week_metadata(
        target_date=date(2026, 3, 30),
        week_start=date(2026, 3, 30),
        week_end=date(2026, 4, 5),
        week_number=23,
    )
    assert meta["week_day_number"] == 1
    assert meta["day_name"] == "Pazartesi"
    assert meta["week"] == 23
    assert meta["week_total_days"] == 7


def test_week_metadata_sunday():
    meta = get_week_metadata(
        target_date=date(2026, 4, 5),
        week_start=date(2026, 3, 30),
        week_end=date(2026, 4, 5),
        week_number=23,
    )
    assert meta["week_day_number"] == 7
    assert meta["day_name"] == "Pazar"


def test_week_metadata_midweek():
    meta = get_week_metadata(
        target_date=date(2026, 4, 1),
        week_start=date(2026, 3, 30),
        week_end=date(2026, 4, 5),
        week_number=23,
    )
    assert meta["week_day_number"] == 3
    assert meta["day_name"] == "Çarşamba"


def test_turkish_days_complete():
    """All 7 Turkish day names are defined."""
    assert len(TURKISH_DAYS) == 7
    for i in range(7):
        assert i in TURKISH_DAYS
