"""Model 4 -- Multi-Indicator Confluence.

Rationale
---------
The single biggest improvement in swing-trading literature comes from
*confluence* -- requiring multiple independent indicator families to agree.
Case studies cited across both Indian and global sources put the lift at
roughly +15 percentage points of win-rate vs. single-indicator systems.

We require >= 3 of the following 4 "votes" to fire on the same bar:
  - Trend vote:      close > 50-EMA AND 50-EMA rising
  - Momentum vote:   MACD > Signal AND RSI > 50
  - Volatility vote: close > 20-Bollinger middle band, but below upper band
  - Volume vote:     volume >= 1.2x 20-day average

By design this fires *less often* but with the best historical hit-rate.
"""
from __future__ import annotations

import pandas as pd

from config import MODEL_PARAMS
from base_model import BaseModel

P = MODEL_PARAMS["confluence"]


class ConfluenceModel(BaseModel):
    name = "confluence"
    k_stop = P["k_stop"]
    k_target = P["k_target"]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        c = df["close"]
        ema50 = df["ema50"]
        rsi14 = df["rsi14"]
        macd_l = df["macd"]
        macd_s = df["macd_sig"]
        bb_mid = df["bb_mid"]
        bb_up = df["bb_upper"]
        vol = df["volume"]
        vol_avg = df["vol_avg20"]

        trend_vote = (c > ema50) & (ema50 > ema50.shift(5))
        momentum_vote = (macd_l > macd_s) & (rsi14 > P["rsi_long_min"])
        volatility_vote = (c > bb_mid) & (c < bb_up)   # rising but not exhausted
        volume_vote = vol >= P["min_volume_mult"] * vol_avg

        votes = (
            trend_vote.astype(int)
            + momentum_vote.astype(int)
            + volatility_vote.astype(int)
            + volume_vote.astype(int)
        )
        sig = votes >= P["min_agree"]
        # Edge: avoid firing on every consecutive bar -- require the vote count
        # to have *just* crossed up to the threshold.
        sig = sig & (votes.shift(1).fillna(0) < P["min_agree"])
        return sig.fillna(False)
