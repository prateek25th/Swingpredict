"""Offline self-test using synthetic OHLCV (no network, no yfinance).

Verifies indicators, all 4 models, the backtester, SQLite history, the JSON
export, the per-stock export, and HTML rendering.

Run:
    python selftest.py
"""
from __future__ import annotations

import json
import shutil

import numpy as np
import pandas as pd

import config
from backtest import backtest_symbol_model
from trend_momentum import TrendMomentumModel
from breakout_volume import BreakoutVolumeModel
from mean_reversion import MeanReversionModel
from confluence import ConfluenceModel
import history
import stock_export
import render

ALL_MODELS = [
    TrendMomentumModel(),
    BreakoutVolumeModel(),
    MeanReversionModel(),
    ConfluenceModel(),
]


def _synthetic_ohlcv(n_days: int = 800, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = np.arange(n_days)
    trend = 0.05 * t
    cycle = 8 * np.sin(t / 18) + 4 * np.sin(t / 7 + 0.5)
    noise = rng.normal(0, 1.2, n_days).cumsum() * 0.4
    close = np.maximum(200 + trend + cycle + noise, 10)

    open_ = close + rng.normal(0, 0.6, n_days)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.8, n_days))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.8, n_days))
    volume = (5e5 + rng.normal(0, 5e4, n_days)).clip(min=1e5).astype(int)
    spike_idx = rng.choice(n_days, size=20, replace=False)
    volume[spike_idx] = (volume[spike_idx] * rng.uniform(2, 4, 20)).astype(int)

    idx = pd.date_range("2020-01-01", periods=n_days, freq="B")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def main() -> int:
    # Use a temporary DB file so we don't clobber the real one.
    test_db = config.REPORTS_DIR / "history_selftest.db"
    if test_db.exists():
        test_db.unlink()
    config.HISTORY_DB = test_db

    df = _synthetic_ohlcv()
    print(f"Synthetic series: {len(df)} bars, "
          f"range Rs.{df['close'].min():.1f}-{df['close'].max():.1f}")

    # --- 1. models + backtests ---------------------------------------------
    for model in ALL_MODELS:
        enriched = model.prepare(df)
        sigs = model.generate_signals(enriched)
        n_fires = int(sigs.fillna(False).sum())
        bt = backtest_symbol_model("SYNTH", df, model)
        # Check reasons rendering on any historical fire (the latest bar
        # usually isn't a fire, so we sample a known historical one instead).
        historical = list(enriched.index[sigs.fillna(False)])
        n_reasons = 0
        if historical:
            sample_sig = model.to_signal("SYNTH", enriched, historical[-1])
            n_reasons = len(sample_sig.reasons)
        print(f"  - {model.name:<18}  fires={n_fires:>4}  "
              f"n_signals={bt.n_signals:>4}  "
              f"hit_rate={bt.hit_rate}  avg_R={bt.avg_r_multiple}  "
              f"reasons={n_reasons}")

    # --- 2. exercise history with synthetic firings ------------------------
    # Cook a few fake fresh signals from the *middle* of the synthetic series
    # so the outcome walker has forward bars to evaluate against.
    import fetch
    df_copy = df.copy()
    fetch.load = lambda symbol: df_copy if symbol == "SYNTH" else None  # type: ignore

    fresh = []
    enriched = ALL_MODELS[3].prepare(df)
    all_sig_dates = ALL_MODELS[3].historical_signals(df)
    # Use signals from roughly the middle so there's >= HOLD_MAX_DAYS forward.
    chosen = all_sig_dates[5:8] if len(all_sig_dates) >= 8 else all_sig_dates[:3]
    for dt in chosen:
        sig = ALL_MODELS[3].to_signal("SYNTH", enriched, dt)
        d = sig.to_dict()
        d["hit_rate"] = 0.55
        d["historical_n"] = 12
        fresh.append(d)
    print(f"\nChose {len(fresh)} synthetic signals from dates {[s['signal_date'] for s in fresh]}")
    print(f"Sample reasons for first signal: {len(fresh[0]['reasons'])} bullet(s)")

    n_recorded = history.record_predictions(fresh)
    print(f"History: recorded {n_recorded} predictions.")
    n_again = history.record_predictions(fresh)
    print(f"History (idempotency check): recorded {n_again} on re-run (should be 0).")

    # --- 3. exercise the outcome-update walker -----------------------------
    outcomes = history.update_open_predictions()
    print(f"Outcomes after replay: {outcomes}")

    # --- 4. exports + render -----------------------------------------------
    history.export_snapshot_json()
    rows = history.get_all()
    stats = history.aggregate_stats()
    print(f"Aggregate stats: total={stats['total']} closed={stats['closed']} "
          f"hit_rate={stats['hit_rate']} avg_r={stats['avg_r']}")

    n_exported = stock_export.export_all_with_history(rows)
    print(f"Per-stock chart exports: {n_exported}")

    # Render all four pages with a fake report so we can sanity-check the HTML.
    fake_report = {
        "generated_at_ist": "2025-01-01 16:00 IST",
        "n_universe": 1,
        "n_signals": len(fresh),
        "signals": fresh,
    }
    render.render_dashboard(fake_report)
    render.render_history(rows, stats)
    render.render_models()
    render.render_stock_page()

    for f in (config.LATEST_HTML, config.HISTORY_HTML, config.MODELS_HTML, config.STOCK_HTML):
        size = f.stat().st_size if f.exists() else 0
        print(f"  rendered {f.name}: {size:,} bytes")

    # --- 5. cleanup the test DB --------------------------------------------
    if test_db.exists():
        test_db.unlink()

    print("\nSelf-test complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
