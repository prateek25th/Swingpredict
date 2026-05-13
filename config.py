"""Central configuration for the NSE swing-trade picker."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
WEB_DIR = ROOT / "web"
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
WEB_DIR.mkdir(exist_ok=True)

# -- Universe ----------------------------------------------------------------
# Nifty 100 = top 100 NSE stocks by free-float market cap.
NIFTY100_URL = (
    "https://archives.nseindia.com/content/indices/ind_nifty100list.csv"
)

# -- History window ----------------------------------------------------------
HISTORY_YEARS = 5
RECENT_BARS_FOR_SIGNAL = 250

# -- Holding period (swing horizon) ------------------------------------------
HOLD_MIN_DAYS = 5      # 1 week
HOLD_MAX_DAYS = 10     # 2 weeks

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

# -- Output paths ------------------------------------------------------------
SIGNALS_JSON = REPORTS_DIR / "signals.json"
BACKTEST_JSON = REPORTS_DIR / "backtest.json"
LATEST_HTML = WEB_DIR / "index.html"
