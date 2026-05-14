"""Model 4 -- Multi-Indicator Confluence."""
from __future__ import annotations

import pandas as pd

from config import MODEL_PARAMS
from base_model import BaseModel

P = MODEL_PARAMS["confluence"]


class ConfluenceModel(BaseModel):
    name = "confluence"
    pretty_name = "Multi-Indicator Confluence"
    k_stop = P["k_stop"]
    k_target = P["k_target"]

    def _votes(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        c = df["close"]
        ema50 = df["ema50"]
        rsi14 = df["rsi14"]
        macd_l = df["macd"]
        macd_s = df["macd_sig"]
        bb_mid = df["bb_mid"]
        bb_up = df["bb_upper"]
        vol = df["volume"]
        vol_avg = df["vol_avg20"]

        return {
            "trend": (c > ema50) & (ema50 > ema50.shift(5)),
            "momentum": (macd_l > macd_s) & (rsi14 > P["rsi_long_min"]),
            "volatility": (c > bb_mid) & (c < bb_up),
            "volume": vol >= P["min_volume_mult"] * vol_avg,
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        votes = self._votes(df)
        total = sum(v.astype(int) for v in votes.values())
        sig = total >= P["min_agree"]
        # Fire only when vote count *crosses* threshold, not every bar above it.
        sig = sig & (total.shift(1).fillna(0) < P["min_agree"])
        return sig.fillna(False)

    def reasons_at(self, df: pd.DataFrame, idx) -> list[str]:
        votes = self._votes(df)
        c = float(df.loc[idx, "close"])
        ema50 = float(df.loc[idx, "ema50"])
        rsi = float(df.loc[idx, "rsi14"])
        macd_l = float(df.loc[idx, "macd"])
        macd_s = float(df.loc[idx, "macd_sig"])
        bb_mid = float(df.loc[idx, "bb_mid"])
        bb_up = float(df.loc[idx, "bb_upper"])
        vol = float(df.loc[idx, "volume"])
        vol_avg = float(df.loc[idx, "vol_avg20"])

        agreed = [name for name, s in votes.items() if bool(s.loc[idx])]
        explanations = {
            "trend": f"Trend vote OK: price (Rs.{c:.2f}) > 50-EMA (Rs.{ema50:.2f}) and 50-EMA is rising.",
            "momentum": f"Momentum vote OK: MACD ({macd_l:.2f}) > Signal ({macd_s:.2f}) and RSI ({rsi:.1f}) > 50.",
            "volatility": f"Volatility vote OK: price is above Bollinger midline (Rs.{bb_mid:.2f}) but not yet at the upper band (Rs.{bb_up:.2f}) - room to run.",
            "volume": f"Volume vote OK: today's volume is at or above 1.2x the 20-day average ({vol/1e5:.1f}L vs. {vol_avg/1e5:.1f}L).",
        }
        header = f"{len(agreed)} of 4 votes agree (threshold: 3) - high-confidence confluence:"
        return [header] + [explanations[v] for v in agreed]
