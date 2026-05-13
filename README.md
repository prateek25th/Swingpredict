# NSE Swing-Trade Picker

Automated stock picker for the Indian (NSE) market. Scans the **top 100 NSE stocks by market cap (Nifty 100)** every trading day after market close, runs four independent swing-trading models (1–2 week horizon), backtests each suggestion on 5+ years of history, and publishes a ranked list with **entry trigger, target, stop-loss, and a historical probability of hitting target before stop**.

Runs on **GitHub Actions** with a daily cron at **16:00 IST** (after the 15:30 NSE close). Dashboard publishes free via **GitHub Pages**.

---

## File layout (everything is one flat folder — no subdirs)

```
nse-swing/
├── README.md
├── requirements.txt
├── .gitignore
├── daily.yml                   # → upload to .github/workflows/ on GitHub
│
├── config.py                   # central config
├── universe.py                 # Nifty 100 list loader
├── fetch.py                    # OHLCV fetcher
├── indicators.py               # RSI / MACD / BB / ATR / Donchian
├── base_model.py               # base Signal + model class
├── trend_momentum.py           # Model 1
├── breakout_volume.py          # Model 2
├── mean_reversion.py           # Model 3
├── confluence.py               # Model 4
├── backtest.py                 # historical replay + hit-rate
├── run_daily.py                # orchestrator (entry point)
└── selftest.py                 # offline pipeline test
```

> **Two folders are auto-created at runtime** by the scripts: `data/` (parquet cache) and `reports/` + `web/` (outputs). You don't need to upload those.

> The workflow file is named `daily.yml` in the flat upload. On GitHub, create the path `.github/workflows/daily.yml` and paste its contents — GitHub's web UI lets you do this without uploading folders.

---

## The four models and why they're trustworthy

Research consensus across swing-trading literature converges on the same short list of indicators for a 1–2 week horizon: 50-EMA, RSI(14), MACD(12,26,9), Bollinger Bands(20,2), Donchian-20, ATR(14), and 20-day average volume. Each model below combines them differently.

1. **Trend-Momentum Pullback** — Buy healthy pullbacks in uptrends. Price > 50-EMA, RSI in 40–55, MACD histogram turning up.
2. **Breakout-Volume** — 20-day Donchian high break with volume ≥ 1.5× the 20-day average, preceded by a Bollinger squeeze.
3. **Mean-Reversion** — Lower-Bollinger touch + RSI < 30 + 50-EMA still rising (don't catch falling knives).
4. **Confluence** — Three of four "votes" (trend, momentum, volatility, volume) must agree. Lowest frequency, best historical hit-rate.

All four models output **trigger / target / stop in ATR units** so they auto-adapt to each stock's volatility, with R:R ≥ 2:1 by construction.

---

## Trigger / Target / Stop logic

- **Trigger** = signal-bar close.
- **Stop** = trigger − `k_stop × ATR(14)`. `k_stop` = 1.5 for trend models, 2.0 for mean-reversion.
- **Target** = trigger + `k_target × ATR(14)`, sized so reward:risk ≥ 2:1.
- **Time stop** = exit at the close of the 10th session if neither level is hit.

---

## Backtest = your probability score

For each fresh signal the backtester:
1. Replays the same model rules over 5 years of that stock's history.
2. Walks every past signal forward up to 10 bars, recording whether target hit before stop.
3. Reports the empirical hit-rate — that's the "probability of touching target" on the dashboard.
4. Also reports average days to target, R-multiple expectancy, and the last few historical outcomes.

No look-ahead: indicators are computed on the full series, but the outcome of any historical signal only uses bars *after* that signal.

---

## Setup

Upload all these files to a new GitHub repo (one click in the GitHub web UI, multi-select all files):

```
README.md, requirements.txt, .gitignore, config.py, universe.py, fetch.py,
indicators.py, base_model.py, trend_momentum.py, breakout_volume.py,
mean_reversion.py, confluence.py, backtest.py, run_daily.py, selftest.py
```

Then create the workflow file separately:
1. In your repo, click **Add file → Create new file**.
2. Type `.github/workflows/daily.yml` as the filename (GitHub will create the folders for you).
3. Paste the contents of `daily.yml` into it.

**To run locally:**

```bash
pip install -r requirements.txt
python selftest.py             # offline pipeline check, no network needed
python fetch.py --bootstrap    # one-off: 5 yrs of history for all Nifty 100
python run_daily.py            # generate today's signals
```

Results land in `reports/signals.json` and `web/index.html`.

**To enable the daily automation:** push to GitHub, enable Actions, and enable Pages on the `gh-pages` branch. The workflow already commits reports back to the repo and publishes the dashboard.

---

## Disclaimer

Research / educational tool. Historical hit-rates reflect past behaviour and don't guarantee future results. Not investment advice. Respect your risk budget — typically ≤1–2% of account per trade.
