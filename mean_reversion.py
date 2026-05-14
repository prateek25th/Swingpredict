"""Model 3 -- Bollinger / RSI Mean-Reversion (in-trend)."""
from __future__ import annotations

import pandas as pd

from config import MODEL_PARAMS
from base_model import BaseModel

P = MODEL_PARAMS["mean_reversion"]


class MeanReversionModel(BaseModel):
    name = "mean_reversion"
    pretty_name = "Mean-Reversion (in-trend)"
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

    def reasons_at(self, df: pd.DataFrame, idx) -> list[str]:
        c = float(df.loc[idx, "close"])
        o = float(df.loc[idx, "open"])
        low = float(df.loc[idx, "low"])
        rsi = float(df.loc[idx, "rsi14"])
        bb_low = float(df.loc[idx, "bb_lower"])
        ema50 = float(df.loc[idx, "ema50"])
        return [
            f"Today's low (Rs.{low:.2f}) touched or pierced the lower Bollinger Band (Rs.{bb_low:.2f}) - a statistical overshoot of normal volatility.",
            f"RSI(14) is at {rsi:.1f}, below the 30 oversold threshold - momentum is fully washed out.",
            f"50-EMA (Rs.{ema50:.2f}) is still rising - we're buying a dip *inside* an uptrend, not a falling knife.",
            f"Today closed (Rs.{c:.2f}) above today's open (Rs.{o:.2f}) - a rejection bar showing buyers stepped in.",
        ]
