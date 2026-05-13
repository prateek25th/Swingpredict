"""Model 3 -- Bollinger / RSI Mean-Reversion (in-trend).

Rationale
---------
We don't catch falling knives -- we buy *temporary* oversold conditions
inside a structural uptrend. This is widely documented as more robust than
plain RSI<30 on Indian equities, where deep oversold often signals real
damage rather than a buyable dip.

Entry rules:
1. Low of today touched / pierced the lower Bollinger Band (20, 2 sigma).
2. RSI(14) < 30 at the close of today.
3. 50-EMA is still rising (regime filter -- only bounce trades *with* the trend).
4. Today's close > today's open (rejection / hammer-style bar, not free-fall).
"""
from __future__ import annotations

import pandas as pd

from config import MODEL_PARAMS
from base_model import BaseModel

P = MODEL_PARAMS["mean_reversion"]


class MeanReversionModel(BaseModel):
    name = "mean_reversion"
    k_stop = P["k_stop"]
    k_target = P["k_target"]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        low = df["low"]
        c = df["close"]
        o = df["open"]
        rsi14 = df["rsi14"]
        bb_low = df["bb_lower"]
        ema50 = df["ema50"]

        touched_band = low <= bb_low
        oversold = rsi14 < P["rsi_oversold"]
        uptrend = ema50 > ema50.shift(5)
        rejection_bar = c > o

        sig = touched_band & oversold & uptrend & rejection_bar
        return sig.fillna(False)
