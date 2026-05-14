NSE Swing-Trade Picker
Automated stock picker for the Indian (NSE) market. Scans the top 100 NSE stocks by market cap (Nifty 100) every trading day after market close, runs four independent swing-trading models (1–2 week horizon), backtests each suggestion on 5+ years of history, and publishes a ranked list with entry trigger, target, stop-loss, and a historical probability of hitting target before stop.
Runs on GitHub Actions with a daily cron at 16:00 IST (after the 15:30 NSE close). Dashboard publishes free via GitHub Pages.
---
What the site shows
Four interlinked pages, all static HTML/JS:
Today's Picks (`index.html`) — fresh signals from the latest scan with trigger / target / stop / historical hit-rate. Each stock symbol is a link to its detail page.
History (`history.html`) — every prediction ever made with its actual outcome (target hit / stopped out / timed out), days held, and R-multiple. Top of page has realised-hit-rate stats.
About the Models (`models.html`) — plain-English explainers for each of the 4 models: intuition, entry rules, and target/stop framework.
Per-Stock Detail (`stock.html?symbol=…`) — candlestick chart (TradingView Lightweight Charts) with the 50-EMA, Bollinger Bands, and every historical signal marked with arrows colour-coded by outcome. Below the chart: a "Why this stock was picked" block that lists the exact conditions that triggered the signal that day.
---
File layout (flat — every file at repo root)
```
README.md                       requirements.txt              .gitignore
config.py                       universe.py                   fetch.py
indicators.py                   base_model.py                 backtest.py
trend_momentum.py               breakout_volume.py            mean_reversion.py
confluence.py                   history.py    (SQLite)        stock_export.py
render.py    (HTML renderer)    run_daily.py  (entry point)   selftest.py
daily.yml                                   → upload to .github/workflows/ on GitHub
```
Auto-created at runtime (don't upload): `data/` (parquet cache), `reports/` (DB + JSONs), `web/` (HTML site, including the `stockdata/` subfolder with one JSON per stock).
---
Models and indicators
Research consensus across swing-trading literature converges on the same short list for a 1–2 week horizon: 50-EMA, RSI(14), MACD(12,26,9), Bollinger Bands(20,2), Donchian-20, ATR(14), 20-day avg volume.
Model	Setup
Trend-Momentum Pullback	Healthy pullbacks in uptrends. Price > 50-EMA, RSI in 40–55, MACD hist turning up.
Breakout + Volume	Donchian-20 high break with volume ≥ 1.5× 20-day avg, preceded by a Bollinger squeeze.
Mean-Reversion (in-trend)	Lower-Bollinger touch + RSI < 30 + 50-EMA still rising (no falling knives).
Confluence	3 of 4 votes (trend / momentum / volatility / volume) must agree on the same bar.
All four produce trigger / target / stop in ATR units, so they auto-adapt to each stock's volatility, with R:R ≥ 2:1 by construction. See the Models page on the live site for the full rule sets.
---
How the probability is computed
For each fresh signal we replay the same model rules across 5 years of that stock's history, walk every past signal forward up to 10 bars, and report the empirical fraction that hit target before stop. That's the "Hist. hit-rate" column on the dashboard. No look-ahead — outcomes use only bars after each historical signal.
As the system runs daily and accumulates real picks, the History page shows the realised hit-rate (predictions that have actually played out), which is the eventual ground truth.
---
Storage architecture
SQLite (`reports/history.db`) is the source of truth for every prediction ever made and its outcome. Composite primary key on (symbol, model, signal_date) makes daily re-runs idempotent.
JSON snapshot (`web/history.json`) is exported from SQLite on every run so the static front-end (which can't query SQL in the browser) can read history client-side.
Per-stock JSON (`web/stockdata/<SYMBOL>.json`) — last 6 months of OHLCV + 50-EMA + Bollinger + signal markers — is what the chart page fetches when you click a symbol.
---
Setup
Upload all 16 Python/text files to a new GitHub repo. Create the workflow separately:
Add file → Create new file, name it `.github/workflows/daily.yml`.
Paste the contents of `daily.yml` from this repo.
Local development:
```bash
pip install -r requirements.txt
python selftest.py             # offline pipeline check, no network
python fetch.py --bootstrap    # one-off: 5 yrs of history for all Nifty 100
python run_daily.py            # generate today's signals + render site
```
Open `web/index.html` in a browser to see the dashboard locally. For the chart page links to work locally, serve the `web/` folder with a tiny HTTP server: `cd web && python -m http.server 8000`, then open `http://localhost:8000/`.
---
Disclaimer
Research / educational tool. Historical hit-rates reflect past behaviour and don't guarantee future results. Not investment advice. Respect your risk budget — typically ≤1–2% of account per trade.
