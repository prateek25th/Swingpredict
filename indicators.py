"""Pure-pandas implementations of all indicators used by the models.

We deliberately avoid TA-Lib (binary install pain on GitHub runners) and
keep the math explicit so it's easy to audit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(close, fast) - ema(close, slow)
    sig = ema(macd_line, signal)
    hist = macd_line - sig
    return pd.DataFrame({"macd": macd_line, "signal": sig, "hist": hist})


def bollinger(close: pd.Series, period: int = 20, n_std: float = 2.0) -> pd.DataFrame:
    mid = sma(close, period)
    std = close.rolling(period).std()
    upper = mid + n_std * std
    lower = mid - n_std * std
    width = (upper - lower) / mid
    return pd.DataFrame({"bb_mid": mid, "bb_upper": upper, "bb_lower": lower, "bb_width": width})


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def donchian(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    upper = df["high"].rolling(period).max()
    lower = df["low"].rolling(period).min()
    return pd.DataFrame({"don_upper": upper, "don_lower": lower})


def avg_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    return volume.rolling(period).mean()


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Attach a standard set of indicators we reuse across models."""
    out = df.copy()
    out["ema20"] = ema(out["close"], 20)
    out["ema50"] = ema(out["close"], 50)
    out["ema200"] = ema(out["close"], 200)
    out["rsi14"] = rsi(out["close"], 14)
    m = macd(out["close"])
    out[["macd", "macd_sig", "macd_hist"]] = m
    bb = bollinger(out["close"])
    out[["bb_mid", "bb_upper", "bb_lower", "bb_width"]] = bb
    out["atr14"] = atr(out, 14)
    don = donchian(out, 20)
    out[["don_upper", "don_lower"]] = don
    out["vol_avg20"] = avg_volume(out["volume"], 20)
    return out
