"""Central configuration for the NSE swing-trade picker."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
WEB_DIR = ROOT / "web"
STOCK_DATA_DIR = WEB_DIR / "stockdata"   # per-stock JSON for the chart page
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
WEB_DIR.mkdir(exist_ok=True)
STOCK_DATA_DIR.mkdir(exist_ok=True)

# -- Universe ----------------------------------------------------------------
NIFTY100_URL = (
    "https://archives.nseindia.com/content/indices/ind_nifty100list.csv"
)

# -- History window ----------------------------------------------------------
HISTORY_YEARS = 5
RECENT_BARS_FOR_SIGNAL = 250

# -- Holding period (swing horizon) ------------------------------------------
HOLD_MIN_DAYS = 5      # 1 week
HOLD_MAX_DAYS = 10     # 2 weeks

# -- Per-stock chart page ----------------------------------------------------
CHART_HISTORY_DAYS = 126       # ~6 months of bars on the detail page

# -- Risk / reward defaults (ATR multiples) ----------------------------------
MODEL_PARAMS = {
    "trend_momentum": {
        "ema_trend": 50,
        "rsi_period": 14,
        "rsi_pullback_low": 40,
        "rsi_pullback_high": 55,
        "macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
        "atr_period": 14,
        "k_stop": 1.5,
        "k_target": 3.0,
        "min_volume_mult": 1.0,
    },
    "breakout_volume": {
        "donchian_period": 20,
        "bb_period": 20, "bb_std": 2.0,
        "bb_squeeze_pct": 0.10,
        "atr_period": 14,
        "k_stop": 1.5,
        "k_target": 3.0,
        "min_volume_mult": 1.5,
    },
    "mean_reversion": {
        "bb_period": 20, "bb_std": 2.0,
        "rsi_period": 14,
        "rsi_oversold": 30,
        "ema_regime": 50,
        "atr_period": 14,
        "k_stop": 2.0,
        "k_target": 4.0,
        "min_volume_mult": 1.0,
    },
    "confluence": {
        "ema_trend": 50,
        "rsi_period": 14,
        "rsi_long_min": 50,
        "macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
        "bb_period": 20, "bb_std": 2.0,
        "atr_period": 14,
        "k_stop": 1.5,
        "k_target": 3.5,
        "min_volume_mult": 1.2,
        "min_agree": 3,
    },
}

# -- Backtest ----------------------------------------------------------------
BACKTEST_LOOKBACK_YEARS = 5
MIN_HISTORICAL_SIGNALS_FOR_PROB = 8

# -- Top-N ranking per market-cap category -----------------------------------
TOP_N_PER_CATEGORY = 5     # how many picks to feature per cap bucket

# -- Confidence thresholds (applied to historical hit-rate) ------------------
CONFIDENCE_HIGH_MIN = 0.65   # >= this   -> "High"
CONFIDENCE_MED_MIN  = 0.50   # in [med, high) -> "Medium"; below -> "Low"
# n/a hit-rate (too few historical signals) -> "Unknown"

CATEGORY_ORDER = ["large_cap", "mid_cap", "small_cap"]

# -- Output paths ------------------------------------------------------------
SIGNALS_JSON = REPORTS_DIR / "signals.json"
BACKTEST_JSON = REPORTS_DIR / "backtest.json"
HISTORY_DB = REPORTS_DIR / "history.db"
HISTORY_EXPORT_JSON = WEB_DIR / "history.json"   # for client-side reads on stock page
LATEST_HTML = WEB_DIR / "index.html"
HISTORY_HTML = WEB_DIR / "history.html"
MODELS_HTML = WEB_DIR / "models.html"
STOCK_HTML = WEB_DIR / "stock.html"
