"""Download daily OHLCV for the Nifty 100 universe and cache to parquet.

Run modes:
    python fetch.py --bootstrap   # full 5-yr pull (one-time)
    python fetch.py               # incremental tail refresh
"""
from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from config import DATA_DIR, HISTORY_YEARS
from universe import fetch_nifty100, to_yf_symbol

log = logging.getLogger(__name__)


def _local_path(symbol: str) -> Path:
    # Replace characters that aren't valid in filenames on every OS.
    safe = symbol.replace("&", "_AND_").replace("/", "_")
    return DATA_DIR / f"{safe}.parquet"


def fetch_one(symbol: str, years: float = HISTORY_YEARS) -> pd.DataFrame | None:
    """Pull `years` of daily history for one NSE symbol."""
    end = date.today()
    start = end - timedelta(days=int(years * 365.25) + 5)
    try:
        df = yf.download(
            to_yf_symbol(symbol),
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)
        keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
        df = df[keep].dropna()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.index.name = "date"
        return df
    except Exception as exc:  # noqa: BLE001
        log.warning("Fetch failed for %s: %s", symbol, exc)
        return None


def update_universe(bootstrap: bool = False, max_workers: int = 6) -> dict[str, int]:
    """Refresh history for every symbol in the universe."""
    symbols = fetch_nifty100()
    log.info("Refreshing %d symbols (bootstrap=%s)...", len(symbols), bootstrap)

    summary: dict[str, int] = {}

    def _task(sym: str) -> tuple[str, int]:
        path = _local_path(sym)
        if bootstrap or not path.exists():
            df = fetch_one(sym, years=HISTORY_YEARS)
        else:
            tail = fetch_one(sym, years=0.1)  # ~36 days
            if tail is None:
                return sym, 0
            old = pd.read_parquet(path)
            df = pd.concat([old, tail])
            df = df[~df.index.duplicated(keep="last")].sort_index()
        if df is None or df.empty:
            return sym, 0
        df.to_parquet(path)
        return sym, len(df)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(_task, s): s for s in symbols}
        for f in as_completed(futs):
            sym, n = f.result()
            summary[sym] = n

    ok = sum(1 for v in summary.values() if v > 0)
    log.info("Done. %d/%d symbols have data.", ok, len(symbols))
    return summary


def load(symbol: str) -> pd.DataFrame | None:
    path = _local_path(symbol)
    if not path.exists():
        return None
    return pd.read_parquet(path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", action="store_true", help="full 5-yr re-pull")
    args = ap.parse_args()
    update_universe(bootstrap=args.bootstrap)
