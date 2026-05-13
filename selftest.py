"""Offline self-test using synthetic OHLCV (no network, no yfinance).

Verifies the indicators, all 4 models, and the backtester work end-to-end.

Run with:
    python selftest.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest import backtest_symbol_model
from trend_momentum import TrendMomentumModel
from breakout_volume import BreakoutVolumeModel
from mean_reversion import MeanReversionModel
from confluence import ConfluenceModel

ALL_MODELS = [
    TrendMomentumModel(),
    BreakoutVolumeModel(),
    MeanReversionModel(),
    ConfluenceModel(),
]


def _synthetic_ohlcv(n_days: int = 800, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # Trend + cycle + noise -- gives us pullbacks, breakouts, mean-reversion all
    # in one series so each model has something to fire on.
    t = np.arange(n_days)
    trend = 0.05 * t
    cycle = 8 * np.sin(t / 18) + 4 * np.sin(t / 7 + 0.5)
    noise = rng.normal(0, 1.2, n_days).cumsum() * 0.4
    close = 200 + trend + cycle + noise
    close = np.maximum(close, 10)

    open_ = close + rng.normal(0, 0.6, n_days)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.8, n_days))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.8, n_days))
    volume = (5e5 + rng.normal(0, 5e4, n_days)).clip(min=1e5).astype(int)
    # Occasional volume spikes for the breakout model
    spike_idx = rng.choice(n_days, size=20, replace=False)
    volume[spike_idx] = (volume[spike_idx] * rng.uniform(2, 4, 20)).astype(int)

    idx = pd.date_range("2020-01-01", periods=n_days, freq="B")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def main() -> int:
    df = _synthetic_ohlcv()
    print(f"Synthetic series: {len(df)} bars, "
          f"range Rs.{df['close'].min():.1f}-{df['close'].max():.1f}")

    issues = 0
    for model in ALL_MODELS:
        enriched = model.prepare(df)
        sigs = model.generate_signals(enriched)
        n_fires = int(sigs.fillna(False).sum())
        bt = backtest_symbol_model("SYNTH", df, model)
        print(
            f"  - {model.name:<18}  fires={n_fires:>4}  "
            f"n_signals={bt.n_signals:>4}  "
            f"hit_rate={bt.hit_rate}  "
            f"avg_R={bt.avg_r_multiple}"
        )
        if n_fires == 0:
            print(f"    (info) no signals for {model.name} on synthetic data")

    print()
    print("Self-test complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
