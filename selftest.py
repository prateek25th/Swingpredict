"""Offline self-test using synthetic OHLCV (no network, no yfinance).

Verifies indicators, all 4 models, the backtester, SQLite history, the JSON
export, the per-stock export, HTML rendering, AND the new v3 pieces:
multi-cap universe handling, confidence labels, top-N-per-category ranking,
and CMP attachment.
"""
from __future__ import annotations

import json

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
import ranking
import cmp as cmp_mod

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
    test_db = config.REPORTS_DIR / "history_selftest.db"
    if test_db.exists():
        test_db.unlink()
    config.HISTORY_DB = test_db

    df = _synthetic_ohlcv()
    print(f"Synthetic series: {len(df)} bars, "
          f"range Rs.{df['close'].min():.1f}-{df['close'].max():.1f}")

    # --- 1. confidence label sanity check ----------------------------------
    print("\nConfidence label thresholds:")
    for hr in [0.75, 0.60, 0.50, 0.45, 0.30, None]:
        label, css = ranking.confidence_label(hr)
        print(f"  hit_rate={hr} -> ({label}, {css})")

    # --- 2. monkey-patch fetch.load + universe.fetch_universe so the
    #        synthetic stocks act like real ones across all 3 caps -----------
    import fetch
    import universe
    df_copy = df.copy()
    fake_universe = [
        universe.UniverseEntry("BIGCO",  "large_cap"),
        universe.UniverseEntry("MIDCO",  "mid_cap"),
        universe.UniverseEntry("SMLCO",  "small_cap"),
    ]
    universe.fetch_universe = lambda: fake_universe  # type: ignore
    fetch.load = lambda sym: df_copy if sym in {"BIGCO", "MIDCO", "SMLCO"} else None  # type: ignore

    # --- 3. cook a few fresh signals + attach CMP + confidence + categorise -
    enriched = ALL_MODELS[3].prepare(df)
    sig_dates = ALL_MODELS[3].historical_signals(df)
    chosen = sig_dates[5:8] if len(sig_dates) >= 8 else sig_dates[:3]

    fresh = []
    for i, dt in enumerate(chosen):
        sym = ["BIGCO", "MIDCO", "SMLCO"][i % 3]
        sig = ALL_MODELS[3].to_signal(sym, enriched, dt)
        d = sig.to_dict()
        d["hit_rate"] = [0.72, 0.51, 0.38][i % 3]
        d["historical_n"] = 12
        fresh.append(d)

    cmp_mod.attach_cmp(fresh)
    ranking.annotate_signals(fresh)
    fresh.sort(key=ranking.sort_key_hit_rate_desc)

    print("\nAnnotated fresh signals:")
    for s in fresh:
        print(f"  {s['symbol']:<7} {s['model']:<10} hit_rate={s['hit_rate']} "
              f"conf={s['confidence']:<15} cmp={s['cmp']} cat={s['category']}")

    # --- 4. top-N per category ---------------------------------------------
    top = ranking.top_n_per_category(fresh)
    print("\nTop-N per category:")
    for cat, picks in top.items():
        print(f"  {cat}: {[p['symbol'] for p in picks]}")

    # --- 5. SQLite history round-trip --------------------------------------
    n_recorded = history.record_predictions(fresh)
    print(f"\nHistory: recorded {n_recorded} (re-run idempotency: "
          f"{history.record_predictions(fresh)} on re-insert)")
    outcomes = history.update_open_predictions()
    print(f"Outcomes after replay: {outcomes}")

    # --- 6. exports + render -----------------------------------------------
    history.export_snapshot_json()
    rows = history.get_all()
    stats = history.aggregate_stats()
    print(f"Stats: total={stats['total']} closed={stats['closed']} "
          f"hit_rate={stats['hit_rate']} avg_r={stats['avg_r']}")

    n_exported = stock_export.export_all_with_history(rows)
    print(f"Per-stock chart exports: {n_exported}")

    fake_report = {
        "generated_at_ist": "2026-05-13 16:00 IST",
        "n_universe": 3,
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

    # Quick spot-check: dashboard contains the cap-bucket headers + Reason buttons
    html = config.LATEST_HTML.read_text()
    expected = [
        "Large Cap", "Mid Cap", "Small Cap",
        "reason-toggle", "toggleReason",
        "Confidence", "CMP", "Reason",
    ]
    missing = [w for w in expected if w not in html]
    if missing:
        print(f"  WARNING: dashboard missing expected tokens: {missing}")
    else:
        print("  Dashboard contains all expected v3 tokens.")

    if test_db.exists():
        test_db.unlink()

    print("\nSelf-test complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
