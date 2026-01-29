import axios from 'axios';
import type {
  BuyRecommendation,
  Stock,
  TechnicalIndicators,
  DailyFocusSettings,
} from '@trading-wizard/shared-ui/types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface RecommendationsResponse {
  recommendations: BuyRecommendation[];
  totalScanned: number;
  generatedAt: string;
  parameters: {
    bollingerPeriod: number;
    bollingerStdDev: number;
    confidenceThreshold: number;
    squeezeThresholdPct: number;
    squeezeLookbackDays: number;
    bbWidthMAPeriod: number;
    rsiPeriod: number;
    macdFast: number;
    macdSlow: number;
    macdSignal: number;
    volumeAvgPeriod: number;
    trendLookbackDays: number;
    trendBelowMaThreshold: number;
    trendMaSlopeLookback: number;
  };
}

export interface StockDetailResponse {
  stock: Stock;
  indicators: TechnicalIndicators;
  recommendation: BuyRecommendation | null;
  priceHistory: Array<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
}

export async function fetchRecommendations(
  settings?: Partial<DailyFocusSettings>
): Promise<RecommendationsResponse> {
  const params: Record<string, number> = {};

  if (settings?.confidenceThreshold !== undefined) {
    params.confidence_threshold = settings.confidenceThreshold;
  }
  if (settings?.bollingerPeriod !== undefined) {
    params.bollinger_period = settings.bollingerPeriod;
  }
  if (settings?.bollingerStdDev !== undefined) {
    params.bollinger_std_dev = settings.bollingerStdDev;
  }
  if (settings?.squeezeThresholdPct !== undefined) {
    params.squeeze_threshold_pct = settings.squeezeThresholdPct;
  }
  if (settings?.squeezeLookbackDays !== undefined) {
    params.squeeze_lookback_days = settings.squeezeLookbackDays;
  }
  if (settings?.bbWidthMAPeriod !== undefined) {
    params.bb_width_ma_period = settings.bbWidthMAPeriod;
  }
  if (settings?.rsiPeriod !== undefined) {
    params.rsi_period = settings.rsiPeriod;
  }
  if (settings?.macdFast !== undefined) {
    params.macd_fast = settings.macdFast;
  }
  if (settings?.macdSlow !== undefined) {
    params.macd_slow = settings.macdSlow;
  }
  if (settings?.macdSignal !== undefined) {
    params.macd_signal = settings.macdSignal;
  }
  if (settings?.volumeAvgPeriod !== undefined) {
    params.volume_avg_period = settings.volumeAvgPeriod;
  }
  if (settings?.trendLookbackDays !== undefined) {
    params.trend_lookback_days = settings.trendLookbackDays;
  }
  if (settings?.trendBelowMaThreshold !== undefined) {
    params.trend_below_ma_threshold = settings.trendBelowMaThreshold;
  }
  if (settings?.trendMaSlopeLookback !== undefined) {
    params.trend_ma_slope_lookback = settings.trendMaSlopeLookback;
  }

  const response = await apiClient.get<RecommendationsResponse>(
    '/api/daily-focus/recommendations',
    { params }
  );
  return response.data;
}

export async function fetchStockDetail(symbol: string): Promise<StockDetailResponse> {
  const response = await apiClient.get<StockDetailResponse>(
    `/api/daily-focus/stock/${encodeURIComponent(symbol)}`
  );
  return response.data;
}

export default apiClient;
