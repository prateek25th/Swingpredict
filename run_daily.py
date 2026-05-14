"""Daily orchestrator -- entry point invoked by GitHub Actions.

Sequence
--------
1. Refresh OHLCV across the full multi-cap universe (large + mid + small).
2. Update outcomes of still-open predictions in the SQLite history DB.
3. Scan every symbol for fresh signals from all four models.
4. Backtest each fresh signal -> attach hit-rate, expected days, R-multiple.
5. Attach CMP (today's close) and confidence label to every signal.
6. Record the fresh signals into history (idempotent on same-day re-runs).
7. Export SQLite -> JSON snapshot for the static front-end.
8. Export per-stock JSON for the chart page.
9. Render all four HTML pages.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from config import BACKTEST_JSON, SIGNALS_JSON
from fetch import update_universe, load
from universe import fetch_universe
from backtest import backtest_symbol_model

from trend_momentum import TrendMomentumModel
from breakout_volume import BreakoutVolumeModel
from mean_reversion import MeanReversionModel
from confluence import ConfluenceModel

import history
import stock_export
import render
import cmp as cmp_mod
import ranking

ALL_MODELS = [
    TrendMomentumModel(),
    BreakoutVolumeModel(),
    MeanReversionModel(),
    ConfluenceModel(),
]

log = logging.getLogger(__name__)


def run(bootstrap: bool = False) -> dict:
    # 1. Refresh OHLCV across the whole multi-cap universe.
    update_universe(bootstrap=bootstrap)
    entries = fetch_universe()
    symbols = [e.symbol for e in entries]

    # 2. Resolve outcomes of predictions still open from prior runs.
    outcomes = history.update_open_predictions()
    log.info("Outcome update: %s", outcomes)

    # 3-4. Scan for fresh signals and backtest each.
    fresh_signals: list[dict] = []
    backtests: list[dict] = []
    for sym in symbols:
        df = load(sym)
        if df is None or len(df) < 250:
            continue
        for model in ALL_MODELS:
            sig = model.latest_signal(sym, df)
            if sig is None:
                continue
            bt = backtest_symbol_model(sym, df, model)
            d = sig.to_dict()
            d["hit_rate"] = bt.hit_rate
            d["profit_rate"] = bt.profit_rate
            d["historical_n"] = bt.n_signals
            d["avg_days_to_target"] = bt.avg_days_to_target
            d["avg_r_multiple"] = bt.avg_r_multiple
            fresh_signals.append(d)
            backtests.append(bt.to_dict())

    # 5. CMP + confidence label + category tag.
    cmp_mod.attach_cmp(fresh_signals)
    ranking.annotate_signals(fresh_signals)

    # Sort: highest hit-rate first; nulls last.
    fresh_signals.sort(key=ranking.sort_key_hit_rate_desc)

    # 6. Persist into SQLite history.
    new_recorded = history.record_predictions(fresh_signals)
    log.info("Recorded %d new predictions in history.", new_recorded)

    report = {
        "generated_at_ist": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        "n_universe": len(symbols),
        "n_signals": len(fresh_signals),
        "signals": fresh_signals,
    }
    SIGNALS_JSON.write_text(json.dumps(report, indent=2, default=str))
    BACKTEST_JSON.write_text(json.dumps(backtests, indent=2, default=str))

    # 7. Export full history as JSON for the static front-end.
    history.export_snapshot_json()
    history_rows = history.get_all()
    stats = history.aggregate_stats()

    # 8. Per-stock JSON for the chart page.
    n_exported = stock_export.export_all_with_history(history_rows)
    log.info("Exported chart data for %d stocks.", n_exported)

    # 9. Render all HTML pages.
    render.render_dashboard(report)
    render.render_history(history_rows, stats)
    render.render_models()
    render.render_stock_page()

    log.info(
        "Done. Universe=%d. %d fresh signals; history has %d total (%d open).",
        len(symbols), len(fresh_signals), stats["total"], stats["open"],
    )
    return report


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run()
