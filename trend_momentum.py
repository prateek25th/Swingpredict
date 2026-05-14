"""Model 1 -- Trend-Momentum Pullback.

Rationale"""Model 1 -- Trend-Momentum Pullback."""
from __future__ import annotations

import pandas as pd

from config import MODEL_PARAMS
from base_model import BaseModel

P = MODEL_PARAMS["trend_momentum"]


class TrendMomentumModel(BaseModel):
    name = "trend_momentum"
    pretty_name = "Trend-Momentum Pullback"
    k_stop = P["k_stop"]
    k_target = P["k_target"]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        c = df["close"]
        ema50 = df["ema50"]
        rsi14 = df["rsi14"]
        hist = df["macd_hist"]
        vol = df["volume"]
        vol_avg = df["vol_avg20"]

        uptrend = (c > ema50) & (ema50 > ema50.shift(5))
        pullback = rsi14.between(P["rsi_pullback_low"], P["rsi_pullback_high"])
        momentum_turn = (hist > hist.shift(1)) & (hist > hist.shift(2))
        volume_ok = vol >= P["min_volume_mult"] * vol_avg

        sig = uptrend & pullback & momentum_turn & volume_ok
        return sig.fillna(False)

    def reasons_at(self, df: pd.DataFrame, idx) -> list[str]:
        c = float(df.loc[idx, "close"])
        ema50 = float(df.loc[idx, "ema50"])
        rsi = float(df.loc[idx, "rsi14"])
        vol = float(df.loc[idx, "volume"])
        vol_avg = float(df.loc[idx, "vol_avg20"])
        return [
            f"Price (Rs.{c:.2f}) is above its 50-day EMA (Rs.{ema50:.2f}) - structural uptrend intact.",
            f"50-EMA is sloping up vs. 5 days ago - trend is healthy, not just a bounce.",
            f"RSI(14) is at {rsi:.1f}, inside the 40-55 pullback zone - momentum has cooled enough to offer a low-risk entry.",
            f"MACD histogram has turned up for two bars - momentum is rotating from down to up.",
            f"Today's volume ({vol/1e5:.1f}L) is at or above the 20-day average ({vol_avg/1e5:.1f}L) - participation confirms the signal.",
        ]

---------
The most widely-cited bread-and-butter swing setup for Indian equities:
buy *healthy pullbacks* inside an established uptrend.

Entry rules (all must hold on the signal bar):
1. Close > 50-EMA               (structural uptrend)
2. 50-EMA today > 50-EMA 5 bars ago  (slope confirms uptrend)
3. RSI(14) inside the 40-55 zone (oversold *relative to the trend*, not absolute)
4. MACD histogram turning up    (hist[t] > hist[t-1] > hist[t-2])
5. Volume >= 20-day avg         (no signal in a vacuum)
"""
from __future__ import annotations

import pandas as pd

from config import MODEL_PARAMS
from base_model import BaseModel

P = MODEL_PARAMS["trend_momentum"]


class TrendMomentumModel(BaseModel):
    name = "trend_momentum"
    k_stop = P["k_stop"]
    k_target = P["k_target"]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        c = df["close"]
        ema50 = df["ema50"]
        rsi14 = df["rsi14"]
        hist = df["macd_hist"]
        vol = df["volume"]
        vol_avg = df["vol_avg20"]

        uptrend = (c > ema50) & (ema50 > ema50.shift(5))
        pullback = rsi14.between(P["rsi_pullback_low"], P["rsi_pullback_high"])
        momentum_turn = (hist > hist.shift(1)) & (hist > hist.shift(2))
        volume_ok = vol >= P["min_volume_mult"] * vol_avg

        sig = uptrend & pullback & momentum_turn & volume_ok
        return sig.fillna(False)
