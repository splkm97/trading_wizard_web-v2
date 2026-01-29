"""Tests for recommendations API parameter passing.

Tests that all settings parameters from the frontend are properly:
1. Accepted by the API endpoint (function signature inspection)
2. Passed to the signal scanner (mock verification)

These tests verify the function signature of get_recommendations to ensure
all required parameters are present.
"""

import inspect
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# All parameters that should be in the API signature (excluding 'db')
EXPECTED_PARAMS = [
    "confidence_threshold",
    "bollinger_period",
    "bollinger_std_dev",
    "squeeze_threshold_pct",
    "squeeze_lookback_days",
    "bb_width_ma_period",
    "rsi_period",
    "macd_fast",
    "macd_slow",
    "macd_signal",
    "volume_avg_period",
    "trend_lookback_days",
    "trend_below_ma_threshold",
    "trend_ma_slope_lookback",
]


class TestRecommendationsParameterSignature:
    """Tests for API function signature - verifies parameters are accepted."""

    @pytest.mark.parametrize("param_name", EXPECTED_PARAMS)
    def test_parameter_in_signature(self, param_name: str):
        """API should accept {param_name} parameter."""
        from backend.src.api.daily_focus.recommendations import get_recommendations

        sig = inspect.signature(get_recommendations)
        param_names = list(sig.parameters.keys())

        assert param_name in param_names, \
            f"{param_name} parameter should be in API signature"


class TestRecommendationsParameterPassing:
    """Tests for parameter passing from API to signal scanner."""

    @pytest.mark.asyncio
    async def test_all_parameters_passed_to_scanner(self):
        """All parameters should be passed to scan_for_buy_signals."""
        with patch("backend.src.api.daily_focus.recommendations.scan_for_buy_signals") as mock_scan:
            mock_scan.return_value = MagicMock(
                recommendations=[],
                total_scanned=100,
                generated_at=datetime.now(),
                parameters={
                    "bollingerPeriod": 15,
                    "bollingerStdDev": 2.0,
                    "confidenceThreshold": 60,
                },
            )

            from backend.src.api.daily_focus.recommendations import get_recommendations

            # Create a mock db session
            mock_db = AsyncMock()

            # Test values for each parameter
            test_params = {
                "confidence_threshold": 60.0,
                "bollinger_period": 15,
                "bollinger_std_dev": 2.0,
                "squeeze_threshold_pct": 50.0,
                "squeeze_lookback_days": 7,
                "bb_width_ma_period": 15,
                "rsi_period": 21,
                "macd_fast": 8,
                "macd_slow": 21,
                "macd_signal": 5,
                "volume_avg_period": 30,
                "trend_lookback_days": 25,
                "trend_below_ma_threshold": 10,
                "trend_ma_slope_lookback": 15,
            }

            # Call the function with custom parameters
            await get_recommendations(**test_params, db=mock_db)

            # Verify scan_for_buy_signals was called with correct parameters
            mock_scan.assert_called_once()
            call_kwargs = mock_scan.call_args.kwargs

            # Verify each parameter was passed correctly
            for param_name, expected_value in test_params.items():
                assert call_kwargs[param_name] == expected_value, \
                    f"{param_name} should be passed to scanner with value {expected_value}"
