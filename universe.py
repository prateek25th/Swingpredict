"""Load the multi-cap NSE universe.

Three categories drawn from the published NSE index constituent CSVs:
- large_cap : Nifty 100   (~100 names)
- mid_cap   : Nifty Midcap 150
- small_cap : Nifty Smallcap 250

Each loader tries the live NSE archive first, then an on-disk cache, then a
hard-coded fallback list (only the large-cap fallback is exhaustive; mid and
small fall back to empty so a missing cache fails loud rather than silently
running on stale data).
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import pandas as pd
import requests

from config import DATA_DIR

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Index source URLs (published by NSE)
# ---------------------------------------------------------------------------
INDEX_URLS = {
    "large_cap": "https://archives.nseindia.com/content/indices/ind_nifty100list.csv",
    "mid_cap":   "https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
    "small_cap": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
}

CATEGORY_LABELS = {
    "large_cap": "Large Cap",
    "mid_cap":   "Mid Cap",
    "small_cap": "Small Cap",
}


@dataclass
class UniverseEntry:
    symbol: str
    category: str        # 'large_cap' | 'mid_cap' | 'small_cap'

    def to_dict(self) -> dict:
        return {"symbol": self.symbol, "category": self.category}


# Hard-coded fallback for large-cap only. Mid and small cap have 150/250 names
# each and rebalance quarterly; we'd rather fail loudly than serve stale data.
_LARGE_CAP_FALLBACK = [
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


def _fetch_index_csv(url: str) -> list[str] | None:
    """Pull symbol list from a single NSE index CSV. None on failure."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        col = "Symbol" if "Symbol" in df.columns else df.columns[2]
        symbols = df[col].astype(str).str.strip().tolist()
        symbols = [s for s in symbols if s and s.upper() != "SYMBOL"]
        return symbols if symbols else None
    except Exception as exc:  # noqa: BLE001
        log.warning("Index CSV fetch failed for %s: %s", url, exc)
        return None


def _cache_path(category: str) -> str:
    return DATA_DIR / f"universe_{category}.csv"


def _fetch_or_cached(category: str, fallback: list[str] | None) -> list[str]:
    """Try live URL, then on-disk cache, then fallback."""
    url = INDEX_URLS[category]
    symbols = _fetch_index_csv(url)
    if symbols and len(symbols) >= 50:    # sanity check
        _cache_path(category).write_text("\n".join(symbols))
        log.info("Fetched %d %s symbols from NSE.", len(symbols), category)
        return symbols

    cache = _cache_path(category)
    if cache.exists():
        symbols = [s for s in cache.read_text().splitlines() if s.strip()]
        if symbols:
            log.info("Using cached %s universe (%d symbols).", category, len(symbols))
            return symbols

    if fallback:
        log.warning("Using hardcoded fallback for %s.", category)
        return list(fallback)

    log.warning("No data for %s; returning empty list.", category)
    return []


def fetch_universe() -> list[UniverseEntry]:
    """Return the full multi-cap universe with per-stock category tags.

    A symbol that appears in multiple index files is assigned to the *largest*
    cap it appears in (large > mid > small) -- this prevents double-counting.
    """
    by_cat = {
        "large_cap": _fetch_or_cached("large_cap", _LARGE_CAP_FALLBACK),
        "mid_cap":   _fetch_or_cached("mid_cap",   None),
        "small_cap": _fetch_or_cached("small_cap", None),
    }

    seen: set[str] = set()
    out: list[UniverseEntry] = []
    for cat in ("large_cap", "mid_cap", "small_cap"):
        for sym in by_cat[cat]:
            if sym in seen:
                continue
            seen.add(sym)
            out.append(UniverseEntry(symbol=sym, category=cat))

    log.info(
        "Multi-cap universe: %d total (large=%d, mid=%d, small=%d).",
        len(out),
        sum(1 for e in out if e.category == "large_cap"),
        sum(1 for e in out if e.category == "mid_cap"),
        sum(1 for e in out if e.category == "small_cap"),
    )
    return out


# Back-compat alias so older modules calling fetch_nifty100() keep working.
def fetch_nifty100() -> list[str]:
    return [e.symbol for e in fetch_universe() if e.category == "large_cap"]


def to_yf_symbol(nse_symbol: str) -> str:
    """Convert an NSE symbol to a yfinance-compatible ticker."""
    return f"{nse_symbol.replace('&', '%26')}.NS"
