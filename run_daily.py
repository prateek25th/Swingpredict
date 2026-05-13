"""Daily orchestrator. This is the entry point GitHub Actions runs.

Sequence
--------
1. Refresh OHLCV for every symbol in the universe (incremental).
2. For each symbol, run every model on the latest bar -- collect any signals.
3. For each *firing* signal, run the per-(symbol, model) backtest and attach
   the historical hit-rate as the published probability.
4. Persist signals + backtest summaries to JSON.
5. Render a static HTML dashboard to ``web/index.html``.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from config import (
    BACKTEST_JSON,
    LATEST_HTML,
    SIGNALS_JSON,
)
from fetch import update_universe, load
from universe import fetch_nifty100
from backtest import backtest_symbol_model

# Import each model directly (flat layout).
from trend_momentum import TrendMomentumModel
from breakout_volume import BreakoutVolumeModel
from mean_reversion import MeanReversionModel
from confluence import ConfluenceModel

ALL_MODELS = [
    TrendMomentumModel(),
    BreakoutVolumeModel(),
    MeanReversionModel(),
    ConfluenceModel(),
]

log = logging.getLogger(__name__)


def run(bootstrap: bool = False) -> dict:
    update_universe(bootstrap=bootstrap)
    symbols = fetch_nifty100()

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

    out = {
        "generated_at_ist": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        "n_universe": len(symbols),
        "n_signals": len(fresh_signals),
        "signals": fresh_signals,
    }
    SIGNALS_JSON.write_text(json.dumps(out, indent=2, default=str))
    BACKTEST_JSON.write_text(json.dumps(backtests, indent=2, default=str))

    render_dashboard(out)
    log.info("Done. %d signals across %d symbols.", len(fresh_signals), len(symbols))
    return out


def render_dashboard(report: dict) -> None:
    """Render a single-file static dashboard for GitHub Pages."""
    rows_html = []
    for s in report["signals"]:
        hit = s.get("hit_rate")
        hit_str = f"{hit*100:.0f}%" if hit is not None else "n/a"
        hit_cls = (
            "good" if (hit or 0) >= 0.60 else "ok" if (hit or 0) >= 0.45 else "weak"
        )
        rows_html.append(f"""
          <tr>
            <td><strong>{s['symbol']}</strong></td>
            <td>{s['model']}</td>
            <td>{s['signal_date']}</td>
            <td>&#8377;{s['trigger']:.2f}</td>
            <td>&#8377;{s['target']:.2f}</td>
            <td>&#8377;{s['stop']:.2f}</td>
            <td>{s['reward_risk']:.2f}</td>
            <td class="{hit_cls}">{hit_str}</td>
            <td>{s.get('historical_n', 0)}</td>
            <td>{s.get('avg_days_to_target') or '&mdash;'}</td>
          </tr>
        """)
    table_body = "\n".join(rows_html) if rows_html else (
        '<tr><td colspan="10" style="text-align:center;opacity:.6">'
        'No fresh signals today. Check back tomorrow after market close.</td></tr>'
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>NSE Swing Picks</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{ --bg:#0b1020; --card:#151b30; --txt:#e9edf6; --muted:#8a93ab;
          --good:#34c38f; --ok:#f5b14f; --weak:#e07a7a; --line:#1f2742; }}
  * {{ box-sizing:border-box }}
  body {{ margin:0; font-family:-apple-system,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--txt); padding:24px }}
  header {{ display:flex; justify-content:space-between; align-items:flex-end;
            margin-bottom:18px; flex-wrap:wrap; gap:8px }}
  h1 {{ margin:0; font-size:22px }}
  .muted {{ color:var(--muted); font-size:13px }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
           overflow:auto }}
  table {{ width:100%; border-collapse:collapse; font-size:14px }}
  th, td {{ padding:10px 12px; text-align:left; border-bottom:1px solid var(--line);
            white-space:nowrap }}
  th {{ background:#101632; color:var(--muted); font-weight:600; font-size:12px;
        text-transform:uppercase; letter-spacing:.04em; position:sticky; top:0 }}
  .good {{ color:var(--good); font-weight:700 }}
  .ok {{ color:var(--ok); font-weight:700 }}
  .weak {{ color:var(--weak); font-weight:700 }}
  footer {{ color:var(--muted); font-size:12px; margin-top:18px; line-height:1.5 }}
</style>
</head>
<body>
  <header>
    <div>
      <h1>NSE Swing Picks</h1>
      <div class="muted">
        Nifty 100 universe &middot; {report['n_signals']} fresh signal(s) &middot;
        Generated {report['generated_at_ist']}
      </div>
    </div>
    <div class="muted">Models: Trend-Momentum &middot; Breakout-Volume &middot; Mean-Reversion &middot; Confluence</div>
  </header>
  <div class="card">
    <table>
      <thead>
        <tr>
          <th>Symbol</th><th>Model</th><th>Signal date</th>
          <th>Trigger</th><th>Target</th><th>Stop</th>
          <th>R:R</th><th>Hist. hit-rate</th><th>n</th><th>Avg days</th>
        </tr>
      </thead>
      <tbody>{table_body}</tbody>
    </table>
  </div>
  <footer>
    Hit-rate = empirical fraction of historical comparable signals where the
    target was touched before the stop, over up to 10 trading sessions. Computed
    on 5 years of daily OHLCV per symbol with no look-ahead. Educational use only;
    not investment advice.
  </footer>
</body>
</html>
"""
    LATEST_HTML.parent.mkdir(parents=True, exist_ok=True)
    LATEST_HTML.write_text(html)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
