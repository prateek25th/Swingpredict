"""Model 2 -- Breakout with Volume confirmation.

Rationale
---------
Classic Turtle-style breakout filtered for the two failure modes that kill
naive breakout systems: low volume and a *non-coiled* setup.

Entry rules:
1. Today's close >= prior 20-bar Donchian high (excluding today).
2. Volume >= 1.5x 20-day average.
3. Bollinger bandwidth was in the bottom decile (over 100 bars) at some
   point in the prior 10 bars (the squeeze that preceded the expansion).
4. Close > 50-EMA (don't fight the bigger trend).
"""
from __future__ import annotations

import pandas as pd

from config import MODEL_PARAMS
from base_model import BaseModel

P = MODEL_PARAMS["breakout_volume"]


class BreakoutVolumeModel(BaseModel):
    name = "breakout_volume"
    k_stop = P["k_stop"]
    k_target = P["k_target"]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        c = df["close"]
        h = df["high"]
        vol = df["volume"]
        vol_avg = df["vol_avg20"]
        ema50 = df["ema50"]
        bw = df["bb_width"]

        # 20-bar Donchian high *excluding today's bar*.
        prior_don_high = h.shift(1).rolling(P["donchian_period"]).max()
        breakout = c >= prior_don_high

        big_volume = vol >= P["min_volume_mult"] * vol_avg

        bw_rank = bw.rolling(100).rank(pct=True)
        was_squeezed = bw_rank.shift(1).rolling(10).min() <= P["bb_squeeze_pct"]

        regime_ok = c > ema50

        sig = breakout & big_volume & was_squeezed & regime_ok
        return sig.fillna(False)
