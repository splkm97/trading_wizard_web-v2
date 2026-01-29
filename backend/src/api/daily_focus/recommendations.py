"""Daily Focus recommendations API endpoint.

GET /api/daily-focus/recommendations - Get buy recommendations
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.db.database import get_db
from backend.src.services.signal_scanner import scan_for_buy_signals

from .schemas import (
    BollingerBandsResponse,
    ErrorResponse,
    MACDIndicatorResponse,
    StockResponse,
    TechnicalIndicatorsResponse,
)

router = APIRouter(prefix="/api/daily-focus", tags=["Daily Focus"])


class BuyRecommendationResponse(BaseModel):
    symbol: str
    stock: StockResponse
    confidenceScore: float
    signalReason: str
    indicators: TechnicalIndicatorsResponse
    generatedAt: datetime


class ParametersResponse(BaseModel):
    bollingerPeriod: int
    bollingerStdDev: float
    confidenceThreshold: float
    squeezeThresholdPct: float
    squeezeLookbackDays: int
    bbWidthMAPeriod: int
    rsiPeriod: int
    macdFast: int
    macdSlow: int
    macdSignal: int
    volumeAvgPeriod: int
    trendLookbackDays: int
    trendBelowMaThreshold: int
    trendMaSlopeLookback: int


class RecommendationsListResponse(BaseModel):
    recommendations: list[BuyRecommendationResponse]
    totalScanned: int
    generatedAt: datetime
    parameters: ParametersResponse


@router.get(
    "/recommendations",
    response_model=RecommendationsListResponse,
    responses={503: {"model": ErrorResponse}}
)
async def get_recommendations(
    confidence_threshold: float = Query(55.0, ge=0, le=100, alias="confidence_threshold"),
    bollinger_period: int = Query(12, ge=5, le=50, alias="bollinger_period"),
    bollinger_std_dev: float = Query(1.3, ge=0.5, le=3.0, alias="bollinger_std_dev"),
    squeeze_threshold_pct: float = Query(55.0, ge=0, le=100, alias="squeeze_threshold_pct"),
    squeeze_lookback_days: int = Query(5, ge=1, le=30, alias="squeeze_lookback_days"),
    bb_width_ma_period: int = Query(10, ge=5, le=50, alias="bb_width_ma_period"),
    rsi_period: int = Query(14, ge=5, le=50, alias="rsi_period"),
    macd_fast: int = Query(12, ge=5, le=50, alias="macd_fast"),
    macd_slow: int = Query(26, ge=10, le=100, alias="macd_slow"),
    macd_signal: int = Query(9, ge=3, le=50, alias="macd_signal"),
    volume_avg_period: int = Query(20, ge=5, le=100, alias="volume_avg_period"),
    trend_lookback_days: int = Query(20, ge=5, le=60, alias="trend_lookback_days"),
    trend_below_ma_threshold: int = Query(15, ge=1, le=60, alias="trend_below_ma_threshold"),
    trend_ma_slope_lookback: int = Query(10, ge=1, le=30, alias="trend_ma_slope_lookback"),
    db: AsyncSession = Depends(get_db),
) -> RecommendationsListResponse:
    """Get buy recommendations based on Bollinger Band squeeze strategy.

    Scans KOSPI Top 100 stocks and returns recommendations sorted by confidence score.
    Uses two-tier caching (Redis + PostgreSQL) to minimize yfinance API calls.
    """
    try:
        result = await scan_for_buy_signals(
            confidence_threshold=confidence_threshold,
            bollinger_period=bollinger_period,
            bollinger_std_dev=bollinger_std_dev,
            squeeze_threshold_pct=squeeze_threshold_pct,
            squeeze_lookback_days=squeeze_lookback_days,
            bb_width_ma_period=bb_width_ma_period,
            rsi_period=rsi_period,
            macd_fast=macd_fast,
            macd_slow=macd_slow,
            macd_signal=macd_signal,
            volume_avg_period=volume_avg_period,
            trend_lookback_days=trend_lookback_days,
            trend_below_ma_threshold=trend_below_ma_threshold,
            trend_ma_slope_lookback=trend_ma_slope_lookback,
            db_session=db,
        )

        recommendations = []
        for rec in result.recommendations:
            recommendations.append(BuyRecommendationResponse(
                symbol=rec.symbol,
                stock=StockResponse(
                    symbol=rec.stock.symbol,
                    name=rec.stock.name,
                    market=rec.stock.market,
                    currentPrice=rec.stock.current_price,
                    previousClose=rec.stock.previous_close,
                    changePercent=rec.stock.change_percent,
                    volume=rec.stock.volume,
                    updatedAt=rec.stock.updated_at,
                ),
                confidenceScore=rec.confidence_score,
                signalReason=rec.signal_reason,
                indicators=TechnicalIndicatorsResponse(
                    bollinger=BollingerBandsResponse(
                        upper=rec.indicators.bollinger.upper,
                        middle=rec.indicators.bollinger.middle,
                        lower=rec.indicators.bollinger.lower,
                        width=rec.indicators.bollinger.width,
                        widthMA=rec.indicators.bollinger.width_ma,
                        isInSqueeze=rec.indicators.bollinger.is_in_squeeze,
                        isExpanding=rec.indicators.bollinger.is_expanding,
                    ),
                    rsi=rec.indicators.rsi,
                    macd=MACDIndicatorResponse(
                        macd=rec.indicators.macd.macd,
                        signal=rec.indicators.macd.signal,
                        histogram=rec.indicators.macd.histogram,
                    ),
                    volumeRatio=rec.indicators.volume_ratio,
                    isCorrectionTrend=rec.indicators.is_correction_trend,
                    calculatedAt=rec.indicators.calculated_at,
                ),
                generatedAt=rec.generated_at,
            ))

        return RecommendationsListResponse(
            recommendations=recommendations,
            totalScanned=result.total_scanned,
            generatedAt=result.generated_at,
            parameters=ParametersResponse(
                bollingerPeriod=bollinger_period,
                bollingerStdDev=bollinger_std_dev,
                confidenceThreshold=confidence_threshold,
                squeezeThresholdPct=squeeze_threshold_pct,
                squeezeLookbackDays=squeeze_lookback_days,
                bbWidthMAPeriod=bb_width_ma_period,
                rsiPeriod=rsi_period,
                macdFast=macd_fast,
                macdSlow=macd_slow,
                macdSignal=macd_signal,
                volumeAvgPeriod=volume_avg_period,
                trendLookbackDays=trend_lookback_days,
                trendBelowMaThreshold=trend_below_ma_threshold,
                trendMaSlopeLookback=trend_ma_slope_lookback,
            ),
        )

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "SERVICE_UNAVAILABLE", "message": f"데이터 조회에 실패했습니다: {str(e)}"},
        ) from e
