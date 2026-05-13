"""Load the Nifty 100 universe (top 100 NSE stocks by market cap)."""
from __future__ import annotations

import io
import logging

import pandas as pd
import requests

from config import DATA_DIR, NIFTY100_URL

log = logging.getLogger(__name__)

UNIVERSE_CACHE = DATA_DIR / "universe.csv"

# Hard-coded fallback list — refresh quarterly if NSE rebalances the index.
_HARDCODED_FALLBACK = [
    "RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "ICICIBANK", "INFY", "SBIN",
    "HINDUNILVR", "ITC", "LT", "BAJFINANCE", "KOTAKBANK", "AXISBANK", "HCLTECH",
    "MARUTI", "SUNPHARMA", "ADANIENT", "ASIANPAINT", "ULTRACEMCO", "TITAN",
    "WIPRO", "M&M", "NTPC", "TATAMOTORS", "POWERGRID", "BAJAJFINSV", "JSWSTEEL",
    "DMART", "ADANIPORTS", "ONGC", "NESTLEIND", "COALINDIA", "TECHM", "HINDALCO",
    "TATASTEEL", "BAJAJ-AUTO", "HDFCLIFE", "GRASIM", "BRITANNIA", "SBILIFE",
    "DRREDDY", "EICHERMOT", "INDUSINDBK", "DIVISLAB", "CIPLA", "TATACONSUM",
    "HEROMOTOCO", "APOLLOHOSP", "BPCL", "UPL", "IOC", "DLF", "VEDL", "PIDILITIND",
    "GODREJCP", "BAJAJHLDNG", "AMBUJACEM", "SHRIRAMFIN", "ADANIGREEN", "TRENT",
    "HAVELLS", "ICICIPRULI", "SIEMENS", "ABB", "BANKBARODA", "GAIL", "TVSMOTOR",
    "ZOMATO", "DABUR", "MARICO", "CHOLAFIN", "INDIGO", "JINDALSTEL", "PFC",
    "RECLTD", "BERGEPAINT", "MUTHOOTFIN", "ADANIPOWER", "ATGL", "TORNTPHARM",
    "VBL", "SBICARD", "CANBK", "BHEL", "HAL", "BOSCHLTD", "MOTHERSON", "PNB",
    "TATAPOWER", "LICI", "NAUKRI", "MFSL", "COLPAL", "BIOCON", "POLYCAB",
    "PIIND", "JIOFIN", "SRF", "IRCTC", "INDUSTOWER", "CGPOWER",
]


def fetch_nifty100() -> list[str]:
    """Return ticker symbols (no `.NS` suffix) for the Nifty 100 universe.

    Tries: live NSE archives CSV -> on-disk cache -> hardcoded fallback.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(NIFTY100_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        col = "Symbol" if "Symbol" in df.columns else df.columns[2]
        symbols = df[col].astype(str).str.strip().tolist()
        symbols = [s for s in symbols if s and s.upper() != "SYMBOL"]
        if len(symbols) >= 90:
            UNIVERSE_CACHE.write_text("\n".join(symbols))
            log.info("Fetched %d symbols from NSE live CSV.", len(symbols))
            return symbols
    except Exception as exc:  # noqa: BLE001
        log.warning("NSE live fetch failed: %s", exc)

    if UNIVERSE_CACHE.exists():
        symbols = [s for s in UNIVERSE_CACHE.read_text().splitlines() if s.strip()]
        if symbols:
            log.info("Using cached universe (%d symbols).", len(symbols))
            return symbols

    log.warning("Using hardcoded fallback universe.")
    return _HARDCODED_FALLBACK


def to_yf_symbol(nse_symbol: str) -> str:
    """Convert an NSE symbol to a yfinance-compatible ticker."""
    return f"{nse_symbol.replace('&', '%26')}.NS"
