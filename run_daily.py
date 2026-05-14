"""Daily orchestrator -- entry point invoked by GitHub Actions.

Sequence
--------
1. Refresh OHLCV for every symbol (incremental tail pull).
2. Update outcomes of still-open predictions in the SQLite history DB.
3. Scan every symbol for fresh signals from all four models.
4. Backtest each fresh signal -> attach hit-rate, expected days, R-multiple.
5. Record the fresh signals into history (idempotent on same-day re-runs).
6. Export the SQLite history table as JSON for the static front-end.
7. Export per-stock JSON for the chart page.
8. Render all four HTML pages: index, history, models, stock template.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from config import BACKTEST_JSON, SIGNALS_JSON
from fetch import update_universe, load
from universe import fetch_nifty100
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

log = logging.getLogger(__name__)


def run(bootstrap: bool = False) -> dict:
    # 1. Refresh OHLCV
    update_universe(bootstrap=bootstrap)
    symbols = fetch_nifty100()

    # 2. Resolve outcomes of any predictions still open from prior runs.
    outcomes = history.update_open_predictions()
    log.info("Outcome update: %s", outcomes)

    # 3-4. Scan for fresh signals + backtest each.
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
            d["historical_n"] = bt.n_signals
            d["avg_days_to_target"] = bt.avg_days_to_target
            d["avg_r_multiple"] = bt.avg_r_multiple
            fresh_signals.append(d)
            backtests.append(bt.to_dict())

    # Sort: highest hit-rate first; nulls last.
    fresh_signals.sort(
        key=lambda x: (x.get("hit_rate") is None, -(x.get("hit_rate") or 0))
    )

    # 5. Persist fresh signals into the SQLite history.
    new_recorded = history.record_predictions(fresh_signals)
    log.info("Recorded %d new predictions in history.", new_recorded)

    # Today's signals JSON (for the dashboard's "today" tab).
    report = {
        "generated_at_ist": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        "n_universe": len(symbols),
        "n_signals": len(fresh_signals),
        "signals": fresh_signals,
    }
    SIGNALS_JSON.write_text(json.dumps(report, indent=2, default=str))
    BACKTEST_JSON.write_text(json.dumps(backtests, indent=2, default=str))

    # 6. Export full history as JSON for the static front-end.
    history.export_snapshot_json()
    history_rows = history.get_all()
    stats = history.aggregate_stats()

    # 7. Per-stock JSON for the chart page.
    n_exported = stock_export.export_all_with_history(history_rows)
    log.info("Exported chart data for %d stocks.", n_exported)

    # 8. Render all HTML pages.
    render.render_dashboard(report)
    render.render_history(history_rows, stats)
    render.render_models()
    render.render_stock_page()

    log.info(
        "Done. %d fresh signals; history has %d total (%d open).",
        len(fresh_signals), stats["total"], stats["open"],
    )
    return report


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run()
