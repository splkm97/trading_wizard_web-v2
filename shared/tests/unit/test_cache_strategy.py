"""Tests for cache_strategy module.

Tests the cache refresh decision logic, especially the bug fix for:
- During market hours, should refresh if cached_period_end < today
  (regardless of elapsed time)
"""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

# Import directly from the module file to avoid __init__.py circular dependencies
import importlib.util
import sys
from pathlib import Path

# Load cache_strategy module directly (bypassing __init__.py)
_module_path = Path(__file__).parent.parent.parent / "data" / "cache_strategy.py"
_spec = importlib.util.spec_from_file_location("cache_strategy", _module_path)
_cache_strategy = importlib.util.module_from_spec(_spec)
sys.modules["cache_strategy"] = _cache_strategy
_spec.loader.exec_module(_cache_strategy)

# Extract what we need
KST = _cache_strategy.KST
INTRADAY_REFRESH_MINUTES = _cache_strategy.INTRADAY_REFRESH_MINUTES
MARKET_CLOSE = _cache_strategy.MARKET_CLOSE
MARKET_OPEN = _cache_strategy.MARKET_OPEN
get_last_trading_date = _cache_strategy.get_last_trading_date
is_korean_market_open = _cache_strategy.is_korean_market_open
is_weekend = _cache_strategy.is_weekend
now_kst = _cache_strategy.now_kst
should_refresh_history = _cache_strategy.should_refresh_history
today_kst = _cache_strategy.today_kst


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_market_open_time():
    """Mock time to 10:00 KST on a weekday (market open)."""
    # Wednesday 2026-01-28 10:00:00 KST
    mock_now = datetime(2026, 1, 28, 10, 0, 0, tzinfo=KST)
    with patch("cache_strategy.now_kst", return_value=mock_now):
        yield mock_now


@pytest.fixture
def mock_market_closed_time():
    """Mock time to 16:00 KST on a weekday (market closed)."""
    # Wednesday 2026-01-28 16:00:00 KST
    mock_now = datetime(2026, 1, 28, 16, 0, 0, tzinfo=KST)
    with patch("cache_strategy.now_kst", return_value=mock_now):
        yield mock_now


@pytest.fixture
def mock_weekend_time():
    """Mock time to Saturday."""
    # Saturday 2026-01-31 10:00:00 KST
    mock_now = datetime(2026, 1, 31, 10, 0, 0, tzinfo=KST)
    with patch("cache_strategy.now_kst", return_value=mock_now):
        yield mock_now


# =============================================================================
# P0: Error Cases (Bug Regression Tests)
# =============================================================================


class TestShouldRefreshHistoryErrorCases:
    """P0: Error cases - must pass to prevent regressions."""

    def test_no_cache_last_fetched_none_returns_true(self):
        """No cache (last_fetched_at is None) -> should refresh."""
        result = should_refresh_history(
            last_fetched_at=None,
            cached_period_end=date(2026, 1, 27),
        )
        assert result is True

    def test_no_cache_period_end_none_returns_true(self):
        """No cache (cached_period_end is None) -> should refresh."""
        result = should_refresh_history(
            last_fetched_at=datetime(2026, 1, 28, 9, 0, tzinfo=KST),
            cached_period_end=None,
        )
        assert result is True

    def test_market_open_yesterday_data_short_elapsed_should_refresh(
        self, mock_market_open_time
    ):
        """BUG FIX: Market open + yesterday's data + elapsed < 30min -> should refresh.

        This is the main bug being fixed. Previously, the function only checked
        elapsed time during market hours, ignoring whether cached data is stale.
        """
        # Current time: 2026-01-28 10:00 KST (Wednesday, market open)
        # Last fetched: 2026-01-28 09:50 KST (10 minutes ago)
        # Cached period end: 2026-01-27 (yesterday - stale!)
        result = should_refresh_history(
            last_fetched_at=datetime(2026, 1, 28, 9, 50, tzinfo=KST),
            cached_period_end=date(2026, 1, 27),  # Yesterday's data
        )
        # Should refresh because we don't have today's data
        assert result is True, (
            "BUG: Should refresh when market is open and cache doesn't have today's data, "
            "regardless of elapsed time"
        )


# =============================================================================
# P1: Edge Cases
# =============================================================================


class TestShouldRefreshHistoryEdgeCases:
    """P1: Edge cases - boundary conditions."""

    def test_market_open_today_data_exactly_30min_elapsed(self, mock_market_open_time):
        """Market open + today's data + exactly 30min elapsed -> boundary test."""
        # Current time: 2026-01-28 10:00 KST
        # Last fetched: 2026-01-28 09:30 KST (exactly 30 min ago)
        # Cached period end: 2026-01-28 (today)
        result = should_refresh_history(
            last_fetched_at=datetime(2026, 1, 28, 9, 30, tzinfo=KST),
            cached_period_end=date(2026, 1, 28),  # Today's data
        )
        # At exactly 30 min, should NOT refresh (boundary: > 30 min required)
        assert result is False

    def test_market_open_today_data_just_over_30min_elapsed(self, mock_market_open_time):
        """Market open + today's data + 30min + 1sec elapsed -> should refresh."""
        # Current time: 2026-01-28 10:00 KST
        # Last fetched: 2026-01-28 09:29:59 KST (30 min + 1 sec ago)
        result = should_refresh_history(
            last_fetched_at=datetime(2026, 1, 28, 9, 29, 59, tzinfo=KST),
            cached_period_end=date(2026, 1, 28),
        )
        assert result is True

    def test_weekend_with_friday_data_no_refresh(self, mock_weekend_time):
        """Weekend + Friday's data -> should not refresh."""
        # Current time: 2026-01-31 (Saturday) 10:00 KST
        # Cached period end: 2026-01-30 (Friday)
        result = should_refresh_history(
            last_fetched_at=datetime(2026, 1, 30, 16, 0, tzinfo=KST),
            cached_period_end=date(2026, 1, 30),  # Friday
        )
        assert result is False

    def test_timezone_naive_last_fetched_at_handled(self, mock_market_open_time):
        """Timezone-naive last_fetched_at should be handled correctly."""
        # Naive datetime (no timezone)
        result = should_refresh_history(
            last_fetched_at=datetime(2026, 1, 28, 9, 50),  # Naive
            cached_period_end=date(2026, 1, 28),
        )
        # Should work without error
        assert result is False  # Today's data, < 30 min elapsed


# =============================================================================
# P2: Happy Paths
# =============================================================================


class TestShouldRefreshHistoryHappyPaths:
    """P2: Happy paths - normal operation."""

    def test_market_open_today_data_short_elapsed_no_refresh(self, mock_market_open_time):
        """Market open + today's data + elapsed < 30min -> no refresh."""
        result = should_refresh_history(
            last_fetched_at=datetime(2026, 1, 28, 9, 50, tzinfo=KST),
            cached_period_end=date(2026, 1, 28),  # Today
        )
        assert result is False

    def test_market_open_today_data_long_elapsed_should_refresh(
        self, mock_market_open_time
    ):
        """Market open + today's data + elapsed > 30min -> should refresh."""
        result = should_refresh_history(
            last_fetched_at=datetime(2026, 1, 28, 9, 0, tzinfo=KST),  # 60 min ago
            cached_period_end=date(2026, 1, 28),
        )
        assert result is True

    def test_market_closed_today_data_no_refresh(self, mock_market_closed_time):
        """Market closed + today's data -> no refresh."""
        # Current time: 2026-01-28 16:00 KST (market closed)
        # Cached period end: 2026-01-28 (today)
        result = should_refresh_history(
            last_fetched_at=datetime(2026, 1, 28, 15, 35, tzinfo=KST),
            cached_period_end=date(2026, 1, 28),
        )
        assert result is False

    def test_market_closed_yesterday_data_should_refresh(self, mock_market_closed_time):
        """Market closed + yesterday's data -> should refresh."""
        # Current time: 2026-01-28 16:00 KST (market closed)
        # Cached period end: 2026-01-27 (yesterday)
        result = should_refresh_history(
            last_fetched_at=datetime(2026, 1, 27, 16, 0, tzinfo=KST),
            cached_period_end=date(2026, 1, 27),
        )
        assert result is True


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestIsKoreanMarketOpen:
    """Tests for is_korean_market_open()."""

    def test_market_open_during_trading_hours(self):
        """Market is open during 09:00-15:30 KST on weekdays."""
        mock_now = datetime(2026, 1, 28, 10, 0, tzinfo=KST)  # Wednesday 10:00
        with patch("cache_strategy.now_kst", return_value=mock_now):
            assert is_korean_market_open() is True

    def test_market_closed_before_open(self):
        """Market is closed before 09:00 KST."""
        mock_now = datetime(2026, 1, 28, 8, 59, tzinfo=KST)
        with patch("cache_strategy.now_kst", return_value=mock_now):
            assert is_korean_market_open() is False

    def test_market_closed_after_close(self):
        """Market is closed after 15:30 KST."""
        mock_now = datetime(2026, 1, 28, 15, 31, tzinfo=KST)
        with patch("cache_strategy.now_kst", return_value=mock_now):
            assert is_korean_market_open() is False

    def test_market_closed_on_weekend(self):
        """Market is closed on weekends."""
        mock_now = datetime(2026, 1, 31, 10, 0, tzinfo=KST)  # Saturday
        with patch("cache_strategy.now_kst", return_value=mock_now):
            assert is_korean_market_open() is False


class TestGetLastTradingDate:
    """Tests for get_last_trading_date()."""

    def test_weekday_after_market_close_returns_today(self):
        """After market close on weekday, returns today."""
        mock_now = datetime(2026, 1, 28, 16, 0, tzinfo=KST)  # Wednesday 16:00
        with patch("cache_strategy.now_kst", return_value=mock_now):
            result = get_last_trading_date()
            assert result == date(2026, 1, 28)

    def test_weekday_before_market_close_returns_yesterday(self):
        """Before market close on weekday, returns yesterday."""
        mock_now = datetime(2026, 1, 28, 10, 0, tzinfo=KST)  # Wednesday 10:00
        with patch("cache_strategy.now_kst", return_value=mock_now):
            result = get_last_trading_date()
            assert result == date(2026, 1, 27)  # Tuesday

    def test_weekend_returns_friday(self):
        """On weekend, returns Friday."""
        mock_now = datetime(2026, 1, 31, 10, 0, tzinfo=KST)  # Saturday
        with patch("cache_strategy.now_kst", return_value=mock_now):
            result = get_last_trading_date()
            assert result == date(2026, 1, 30)  # Friday


class TestIsWeekend:
    """Tests for is_weekend()."""

    def test_saturday_is_weekend(self):
        assert is_weekend(date(2026, 1, 31)) is True

    def test_sunday_is_weekend(self):
        assert is_weekend(date(2026, 2, 1)) is True

    def test_monday_is_not_weekend(self):
        assert is_weekend(date(2026, 1, 26)) is False

    def test_friday_is_not_weekend(self):
        assert is_weekend(date(2026, 1, 30)) is False
