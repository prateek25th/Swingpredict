"""Export per-stock OHLCV + indicators + signal markers as JSON for the
client-side chart page (web/stock.html).

For each stock that has *ever* had a signal in history, we write
``web/stockdata/<symbol>.json`` containing the last ``CHART_HISTORY_DAYS``
bars of OHLCV plus the 50-EMA / 20-Bollinger overlays and a list of
historical signal markers (one per past prediction). The chart page
fetches this file and renders it with Lightweight Charts.
"""
from __future__ import annotations

import json
import logging

import pandas as pd

import fetch  # imported as module so selftest can monkey-patch fetch.load
from config import CHART_HISTORY_DAYS, STOCK_DATA_DIR
from indicators import enrich

log = logging.getLogger(__name__)


def export_stock(symbol: str, signals_for_stock: list[dict]) -> bool:
    """Write one ``stockdata/<symbol>.json``. Returns True on success."""
    df = fetch.load(symbol)
    if df is None or df.empty:
        return False

    e = enrich(df).tail(CHART_HISTORY_DAYS)
    if e.empty:
        return False

    bars = []
    for ts, row in e.iterrows():
        bars.append({
            "time": pd.Timestamp(ts).date().isoformat(),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
        })

    overlays = {
        "ema50": [
            {"time": pd.Timestamp(ts).date().isoformat(),
             "value": None if pd.isna(v) else round(float(v), 2)}
            for ts, v in e["ema50"].items()
        ],
        "bb_upper": [
            {"time": pd.Timestamp(ts).date().isoformat(),
             "value": None if pd.isna(v) else round(float(v), 2)}
            for ts, v in e["bb_upper"].items()
        ],
        "bb_lower": [
            {"time": pd.Timestamp(ts).date().isoformat(),
             "value": None if pd.isna(v) else round(float(v), 2)}
            for ts, v in e["bb_lower"].items()
        ],
    }
    # Strip leading None values so the chart doesn't warn.
    for k in list(overlays.keys()):
        overlays[k] = [p for p in overlays[k] if p["value"] is not None]

    # Markers: every historical prediction for this stock that falls within
    # the chart window.
    window_start = e.index.min()
    markers = []
    for s in signals_for_stock:
        sd = pd.Timestamp(s["signal_date"])
        if sd < window_start:
            continue
        marker = {
            "time": s["signal_date"],
            "model": s["model"],
            "status": s.get("status", "open"),
            "trigger": s["trigger"],
            "target": s["target"],
            "stop": s["stop"],
        }
        markers.append(marker)

    payload = {
        "symbol": symbol,
        "bars": bars,
        "ema50": overlays["ema50"],
        "bb_upper": overlays["bb_upper"],
        "bb_lower": overlays["bb_lower"],
        "markers": markers,
    }
    path = STOCK_DATA_DIR / f"{symbol.replace('&', '_AND_').replace('/', '_')}.json"
    path.write_text(json.dumps(payload, default=str))
    return True


def export_all_with_history(history: list[dict]) -> int:
    """Export one JSON per unique symbol seen in history. Returns count."""
    by_symbol: dict[str, list[dict]] = {}
    for h in history:
        by_symbol.setdefault(h["symbol"], []).append(h)

    n = 0
    for sym, sigs in by_symbol.items():
        if export_stock(sym, sigs):
            n += 1
        else:
            log.warning("Could not export stock data for %s", sym)
    return n
