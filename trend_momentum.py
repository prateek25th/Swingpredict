"""Model 1 -- Trend-Momentum Pullback.

Rationale
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
