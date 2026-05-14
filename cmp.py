"""Current Market Price helper.

Since GitHub Actions runs ~30 minutes after the 15:30 IST NSE close, the
freshest price we have for any stock is its closing price *today*. We pull
it from the cached parquet that ``fetch.update_universe`` just refreshed.

This is not a live intraday quote -- it's "today's close", and the dashboard
labels it as such. Live intraday would require a paid feed and a different
deployment model.
"""
from __future__ import annotations

import logging

import pandas as pd

import fetch

log = logging.getLogger(__name__)


def latest_price(symbol: str) -> dict | None:
    """Return {price, as_of} for the latest close of ``symbol``, or None."""
    df = fetch.load(symbol)
    if df is None or df.empty:
        return None
    last = df.iloc[-1]
    return {
        "price": round(float(last["close"]), 2),
        "as_of": pd.Timestamp(df.index[-1]).date().isoformat(),
    }


def attach_cmp(signals: list[dict]) -> list[dict]:
    """Mutate every signal in place, attaching ``cmp`` and ``cmp_as_of`` fields."""
    cache: dict[str, dict | None] = {}
    for s in signals:
        sym = s["symbol"]
        if sym not in cache:
            cache[sym] = latest_price(sym)
        info = cache[sym]
        if info is None:
            s["cmp"] = None
            s["cmp_as_of"] = None
        else:
            s["cmp"] = info["price"]
            s["cmp_as_of"] = info["as_of"]
    return signals
