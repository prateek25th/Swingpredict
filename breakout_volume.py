"""Model 2 -- Breakout with Volume confirmation."""
from __future__ import annotations

import pandas as pd

from config import MODEL_PARAMS
from base_model import BaseModel

P = MODEL_PARAMS["breakout_volume"]


class BreakoutVolumeModel(BaseModel):
    name = "breakout_volume"
    pretty_name = "Breakout + Volume"
    k_stop = P["k_stop"]
    k_target = P["k_target"]

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        c = df["close"]
        h = df["high"]
        vol = df["volume"]
        vol_avg = df["vol_avg20"]
        ema50 = df["ema50"]
        bw = df["bb_width"]

        prior_don_high = h.shift(1).rolling(P["donchian_period"]).max()
        breakout = c >= prior_don_high

        big_volume = vol >= P["min_volume_mult"] * vol_avg

        bw_rank = bw.rolling(100).rank(pct=True)
        was_squeezed = bw_rank.shift(1).rolling(10).min() <= P["bb_squeeze_pct"]

        regime_ok = c > ema50

        sig = breakout & big_volume & was_squeezed & regime_ok
        return sig.fillna(False)

    def reasons_at(self, df: pd.DataFrame, idx) -> list[str]:
        c = float(df.loc[idx, "close"])
        ema50 = float(df.loc[idx, "ema50"])
        vol = float(df.loc[idx, "volume"])
        vol_avg = float(df.loc[idx, "vol_avg20"])
        vol_mult = vol / max(vol_avg, 1)
        pos = df.index.get_loc(idx)
        prior_high = float(df["high"].iloc[max(0, pos - 20):pos].max())
        return [
            f"Close (Rs.{c:.2f}) broke above the prior 20-day Donchian high (Rs.{prior_high:.2f}) - fresh momentum.",
            f"Volume on the breakout is {vol_mult:.1f}x the 20-day average - real participation, not a low-liquidity fakeout.",
            f"Bollinger bandwidth was in the bottom 10% of the last 100 bars within the past 10 sessions - the stock was coiled before this expansion.",
            f"Price is above the 50-EMA (Rs.{ema50:.2f}) - the breakout aligns with the larger trend.",
        ]
