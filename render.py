"""HTML renderer for all four static pages of the dashboard.

Pages
-----
- index.html    : today's fresh picks (the home page)
- history.html  : every prediction ever made + outcome
- models.html   : plain-English explainers for each of the 4 models
- stock.html    : per-stock detail page (template; reads ?symbol= from URL)

All pages share a tiny inline CSS block so the site stays as a self-contained
set of static files (no build step, no framework).
"""
from __future__ import annotations

import json
from datetime import datetime

from config import (
    HISTORY_HTML,
    LATEST_HTML,
    MODELS_HTML,
    STOCK_HTML,
)


# --------------------------------------------------------------------------- #
# Shared header / footer
# --------------------------------------------------------------------------- #
_BASE_CSS = """
:root { --bg:#0b1020; --card:#151b30; --txt:#e9edf6; --muted:#8a93ab;
        --good:#34c38f; --ok:#f5b14f; --weak:#e07a7a; --line:#1f2742;
        --accent:#6ea8ff; }
* { box-sizing:border-box }
body { margin:0; font-family:-apple-system,Segoe UI,Roboto,sans-serif;
       background:var(--bg); color:var(--txt); padding:24px; line-height:1.5 }
a { color:var(--accent); text-decoration:none }
a:hover { text-decoration:underline }
nav { display:flex; gap:18px; margin-bottom:18px; flex-wrap:wrap; font-size:14px }
nav .current { color:var(--txt); font-weight:600 }
header { display:flex; justify-content:space-between; align-items:flex-end;
         margin-bottom:18px; flex-wrap:wrap; gap:8px }
h1 { margin:0; font-size:22px }
h2 { margin:24px 0 12px; font-size:18px }
.muted { color:var(--muted); font-size:13px }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px;
        overflow:auto; margin-bottom:18px }
.card .pad { padding:16px 18px }
table { width:100%; border-collapse:collapse; font-size:14px }
th, td { padding:10px 12px; text-align:left; border-bottom:1px solid var(--line);
         white-space:nowrap }
th { background:#101632; color:var(--muted); font-weight:600; font-size:12px;
     text-transform:uppercase; letter-spacing:.04em; position:sticky; top:0 }
.good { color:var(--good); font-weight:700 }
.ok { color:var(--ok); font-weight:700 }
.weak { color:var(--weak); font-weight:700 }
.pill { display:inline-block; padding:2px 8px; border-radius:999px;
        font-size:12px; font-weight:600 }
.pill.target { background:rgba(52,195,143,.15); color:var(--good) }
.pill.stop   { background:rgba(224,122,122,.15); color:var(--weak) }
.pill.timeout { background:rgba(245,177,79,.15); color:var(--ok) }
.pill.open   { background:rgba(110,168,255,.15); color:var(--accent) }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
        gap:12px }
.stat { background:var(--card); border:1px solid var(--line); border-radius:12px;
        padding:14px 16px }
.stat .label { color:var(--muted); font-size:12px; text-transform:uppercase;
               letter-spacing:.04em }
.stat .value { font-size:24px; font-weight:700; margin-top:4px }
footer { color:var(--muted); font-size:12px; margin-top:24px; line-height:1.6 }
.reason-list { margin:0; padding-left:20px }
.reason-list li { margin-bottom:6px }
"""

def _nav(current: str) -> str:
    items = [
        ("index.html", "Today's Picks", "home"),
        ("history.html", "History", "history"),
        ("models.html", "About the Models", "models"),
    ]
    parts = []
    for href, label, key in items:
        cls = "current" if key == current else ""
        parts.append(f'<a href="{href}" class="{cls}">{label}</a>')
    return f'<nav>{"".join(parts)}</nav>'


def _page(title: str, current: str, body: str, extra_head: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{_BASE_CSS}</style>
{extra_head}
</head>
<body>
{_nav(current)}
{body}
<footer>
  Educational research tool only &middot; not investment advice &middot;
  Backtested hit-rates reflect historical behaviour and do not guarantee future results.
</footer>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# Page 1 : today's picks
# --------------------------------------------------------------------------- #
def render_dashboard(report: dict) -> None:
    rows = []
    for s in report["signals"]:
        hit = s.get("hit_rate")
        hit_str = f"{hit*100:.0f}%" if hit is not None else "n/a"
        hit_cls = (
            "good" if (hit or 0) >= 0.60 else "ok" if (hit or 0) >= 0.45 else "weak"
        )
        sym_link = (
            f'<a href="stock.html?symbol={s["symbol"]}'
            f'&amp;model={s["model"]}&amp;date={s["signal_date"]}">{s["symbol"]}</a>'
        )
        rows.append(f"""
          <tr>
            <td><strong>{sym_link}</strong></td>
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
    body_table = "\n".join(rows) if rows else (
        '<tr><td colspan="10" style="text-align:center;opacity:.6">'
        'No fresh signals today. Check back tomorrow after market close.</td></tr>'
    )

    body = f"""
<header>
  <div>
    <h1>NSE Swing Picks &mdash; Today</h1>
    <div class="muted">Nifty 100 &middot; {report['n_signals']} fresh signal(s)
       &middot; Generated {report['generated_at_ist']}</div>
  </div>
  <div class="muted">Click any symbol for chart + reasoning</div>
</header>
<div class="card"><table>
  <thead>
    <tr><th>Symbol</th><th>Model</th><th>Signal date</th>
        <th>Trigger</th><th>Target</th><th>Stop</th>
        <th>R:R</th><th>Hist. hit-rate</th><th>n</th><th>Avg days</th></tr>
  </thead>
  <tbody>{body_table}</tbody>
</table></div>
"""
    LATEST_HTML.write_text(_page("NSE Swing Picks", "home", body))


# --------------------------------------------------------------------------- #
# Page 2 : history
# --------------------------------------------------------------------------- #
def render_history(history: list[dict], stats: dict) -> None:
    # Newest first
    history = sorted(history, key=lambda e: e["signal_date"], reverse=True)
    rows = []
    for h in history:
        status = h["status"]
        outcome_pill = f'<span class="pill {status}">{status.upper()}</span>'
        exit_info = h.get("exit_date") or "&mdash;"
        days = h.get("days_held")
        days_str = str(days) if days is not None else "&mdash;"
        r = h.get("r_multiple")
        r_str = f"{r:+.2f}R" if r is not None else "&mdash;"
        r_cls = ""
        if r is not None:
            r_cls = "good" if r > 0 else "weak"
        sym_link = (
            f'<a href="stock.html?symbol={h["symbol"]}'
            f'&amp;model={h["model"]}&amp;date={h["signal_date"]}">{h["symbol"]}</a>'
        )
        rows.append(f"""
          <tr>
            <td><strong>{sym_link}</strong></td>
            <td>{h['model']}</td>
            <td>{h['signal_date']}</td>
            <td>&#8377;{h['trigger']:.2f}</td>
            <td>&#8377;{h['target']:.2f}</td>
            <td>&#8377;{h['stop']:.2f}</td>
            <td>{outcome_pill}</td>
            <td>{exit_info}</td>
            <td>{days_str}</td>
            <td class="{r_cls}">{r_str}</td>
          </tr>
        """)
    table_body = "\n".join(rows) if rows else (
        '<tr><td colspan="10" style="text-align:center;opacity:.6">'
        'No prediction history yet. The first daily run will start populating this.</td></tr>'
    )

    hit_rate = stats.get("hit_rate")
    hit_str = f"{hit_rate*100:.1f}%" if hit_rate is not None else "n/a"
    avg_r = stats.get("avg_r")
    avg_r_str = f"{avg_r:+.2f}R" if avg_r is not None else "n/a"

    body = f"""
<header>
  <div>
    <h1>Prediction History</h1>
    <div class="muted">Every pick the system has ever made, with the outcome
       it actually achieved over its 1-2 week window.</div>
  </div>
</header>

<div class="grid">
  <div class="stat"><div class="label">Total picks</div>
       <div class="value">{stats['total']}</div></div>
  <div class="stat"><div class="label">Closed</div>
       <div class="value">{stats['closed']}</div></div>
  <div class="stat"><div class="label">Still open</div>
       <div class="value">{stats['open']}</div></div>
  <div class="stat"><div class="label">Target hit</div>
       <div class="value good">{stats['target']}</div></div>
  <div class="stat"><div class="label">Stopped out</div>
       <div class="value weak">{stats['stop']}</div></div>
  <div class="stat"><div class="label">Timed out</div>
       <div class="value ok">{stats['timeout']}</div></div>
  <div class="stat"><div class="label">Realised hit-rate</div>
       <div class="value">{hit_str}</div></div>
  <div class="stat"><div class="label">Avg R-multiple</div>
       <div class="value">{avg_r_str}</div></div>
</div>

<div class="card"><table>
  <thead>
    <tr><th>Symbol</th><th>Model</th><th>Signal date</th>
        <th>Trigger</th><th>Target</th><th>Stop</th>
        <th>Outcome</th><th>Exit date</th><th>Days</th><th>R-mult</th></tr>
  </thead>
  <tbody>{table_body}</tbody>
</table></div>
"""
    HISTORY_HTML.write_text(_page("Prediction History", "history", body))


# --------------------------------------------------------------------------- #
# Page 3 : about the models
# --------------------------------------------------------------------------- #
_MODEL_EXPLAINERS = [
    {
        "id": "trend_momentum",
        "name": "Trend-Momentum Pullback",
        "summary": "Buy healthy pullbacks inside an established uptrend.",
        "intuition": (
            "Markets in real uptrends don't move in straight lines &mdash; they make "
            "two steps forward, one step back. The best risk:reward entries come on "
            "the 'one step back' phase, after the herd has already pushed momentum "
            "indicators into oversold territory but the larger trend is still intact. "
            "This is the most-cited bread-and-butter swing setup for Indian equities."
        ),
        "rules": [
            "Close is above the 50-day EMA (price is in a structural uptrend).",
            "The 50-EMA today is higher than it was 5 sessions ago (trend slope is up).",
            "RSI(14) is between 40 and 55 &mdash; pulled back from overbought but not crashing.",
            "MACD histogram has turned up for two consecutive bars (momentum rotating up).",
            "Today's volume is at or above the 20-day average (real participation).",
        ],
        "tp_sl": "Target = trigger + 3.0 x ATR(14). Stop = trigger - 1.5 x ATR(14). Reward:Risk = 2.0.",
    },
    {
        "id": "breakout_volume",
        "name": "Breakout + Volume",
        "summary": "Catch fresh expansion out of a coiled, low-volatility range.",
        "intuition": (
            "Bollinger Band 'squeezes' &mdash; periods where volatility contracts to "
            "an unusual low &mdash; reliably precede explosive moves. The two failure "
            "modes for naive breakout systems are low-volume fakeouts and breakouts "
            "that fight the larger trend; this model filters out both."
        ),
        "rules": [
            "Close breaks above the prior 20-day Donchian high (a fresh range expansion).",
            "Volume on the breakout is at least 1.5x the 20-day average.",
            "Bollinger bandwidth was in the bottom 10% of the last 100 sessions within "
            "the prior 10 bars &mdash; confirming a real squeeze preceded the move.",
            "Close is still above the 50-day EMA (breakout aligns with the bigger trend).",
        ],
        "tp_sl": "Target = trigger + 3.0 x ATR(14). Stop = trigger - 1.5 x ATR(14). Reward:Risk = 2.0.",
    },
    {
        "id": "mean_reversion",
        "name": "Mean-Reversion (in-trend)",
        "summary": "Buy statistical overshoots, but only inside an uptrend.",
        "intuition": (
            "Plain RSI &lt; 30 on Indian equities often signals real damage, not a "
            "buyable dip. The fix is to add a regime filter: only take oversold "
            "bounces when the larger trend (50-EMA slope) is still rising. The "
            "rejection-bar requirement ensures buyers actually stepped in on the day."
        ),
        "rules": [
            "Today's low touched or pierced the lower Bollinger Band (statistical overshoot).",
            "RSI(14) closed below 30 (momentum fully washed out).",
            "The 50-day EMA is still rising vs. 5 sessions ago (uptrend regime intact).",
            "Today's close is above today's open &mdash; a rejection bar showing buyers responded.",
        ],
        "tp_sl": (
            "Target = trigger + 4.0 x ATR(14). Stop = trigger - 2.0 x ATR(14) "
            "(wider stop because mean-reversion entries need more breathing room). "
            "Reward:Risk = 2.0."
        ),
    },
    {
        "id": "confluence",
        "name": "Multi-Indicator Confluence",
        "summary": "Fire only when 3 of 4 independent indicator families all agree.",
        "intuition": (
            "Case studies cited across both Indian and global swing-trading "
            "literature put the lift at roughly +15 percentage points of win-rate "
            "vs. single-indicator systems. This model fires far less often than the "
            "others, but historically with the highest hit-rate."
        ),
        "rules": [
            "Trend vote: close &gt; 50-EMA AND 50-EMA rising.",
            "Momentum vote: MACD line &gt; signal line AND RSI &gt; 50.",
            "Volatility vote: close is above the Bollinger midline but below the upper band (room to run).",
            "Volume vote: today's volume &ge; 1.2x the 20-day average.",
            "<strong>At least 3 of these 4 votes must be True, and the vote count must have just crossed up to 3</strong> "
            "(prevents firing every bar inside an existing trend).",
        ],
        "tp_sl": "Target = trigger + 3.5 x ATR(14). Stop = trigger - 1.5 x ATR(14). Reward:Risk = 2.3.",
    },
]


def render_models() -> None:
    blocks = []
    for m in _MODEL_EXPLAINERS:
        rules_html = "\n".join(f"<li>{r}</li>" for r in m["rules"])
        blocks.append(f"""
<div class="card" id="{m['id']}"><div class="pad">
  <h2 style="margin-top:0">{m['name']}</h2>
  <p style="margin:0 0 12px"><strong>{m['summary']}</strong></p>
  <p class="muted" style="margin:0 0 12px">{m['intuition']}</p>
  <h3 style="font-size:14px; margin:14px 0 6px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em">Entry rules</h3>
  <ul class="reason-list">{rules_html}</ul>
  <h3 style="font-size:14px; margin:14px 0 6px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em">Target / Stop</h3>
  <p style="margin:0">{m['tp_sl']}</p>
</div></div>
""")

    body = f"""
<header>
  <div>
    <h1>About the Models</h1>
    <div class="muted">Each model has its own entry logic, but they all share the
       same ATR-scaled target/stop framework and the same 1-2 week (5-10 bar) horizon.</div>
  </div>
</header>

<div class="card"><div class="pad">
  <h2 style="margin-top:0">Why these four?</h2>
  <p>Across both Indian and global swing-trading research, the same short list of
     indicators keeps coming up as the most reliable for a 1-2 week horizon:
     <strong>50-EMA</strong> (trend), <strong>RSI(14)</strong> (momentum exhaustion),
     <strong>MACD(12,26,9)</strong> (momentum direction), <strong>Bollinger Bands(20,2)</strong>
     (volatility), <strong>Donchian-20</strong> (range), <strong>ATR(14)</strong> (sizing),
     and <strong>20-day average volume</strong> (participation).</p>
  <p>Rather than pick a single 'best' combination, we run four independent models
     that each combine these primitives differently. The dashboard publishes the
     historical hit-rate per model per stock so you can see <em>empirically</em>
     which one works best on each name &mdash; rather than trusting any one
     approach in the abstract.</p>
</div></div>

{"".join(blocks)}

<div class="card"><div class="pad">
  <h2 style="margin-top:0">Shared mechanics</h2>
  <h3 style="font-size:14px; margin:14px 0 6px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em">Trigger / Target / Stop</h3>
  <ul class="reason-list">
    <li><strong>Trigger</strong> = the close of the signal bar.</li>
    <li><strong>Stop</strong> = trigger &minus; <em>k_stop</em> &times; ATR(14). ATR-scaling means stops adapt to each stock's own volatility.</li>
    <li><strong>Target</strong> = trigger + <em>k_target</em> &times; ATR(14). Sized so reward:risk &ge; 2:1 on every model.</li>
    <li><strong>Time stop</strong> = exit at the close of the 10th session if neither target nor stop has been hit.</li>
  </ul>
  <h3 style="font-size:14px; margin:14px 0 6px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em">Historical hit-rate (the published probability)</h3>
  <p style="margin:0">For every fresh signal we replay the same model rules across the prior 5 years of that stock's history, walk every past signal forward up to 10 bars, and report the empirical fraction that hit target before stop. That is the number shown as 'Hist. hit-rate' on the dashboard. It uses only bars <em>after</em> each historical signal &mdash; no look-ahead.</p>
</div></div>
"""
    MODELS_HTML.write_text(_page("About the Models", "models", body))


# --------------------------------------------------------------------------- #
# Page 4 : per-stock detail (template; reads ?symbol= from URL)
# --------------------------------------------------------------------------- #
def render_stock_page() -> None:
    """The detail page is a single template that fetches data client-side
    based on the ?symbol=... &model=... &date=... URL params."""

    extra_head = (
        '<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>'
    )

    body = """
<header>
  <div>
    <h1 id="symHeader">Stock detail</h1>
    <div class="muted" id="subHeader">Loading...</div>
  </div>
  <div class="muted"><a href="index.html">&larr; Back to today's picks</a></div>
</header>

<div class="card"><div class="pad">
  <div id="chart" style="width:100%; height:500px"></div>
  <div class="muted" id="chartLegend" style="margin-top:10px"></div>
</div></div>

<div class="card"><div class="pad">
  <h2 style="margin-top:0">Why this stock was picked</h2>
  <div id="whyBlock">Loading reasoning...</div>
</div></div>

<div class="card"><div class="pad">
  <h2 style="margin-top:0">All historical signals for this stock</h2>
  <div id="markerTable"></div>
</div></div>

<script>
const params = new URLSearchParams(location.search);
const symbol = params.get('symbol');
const wantedModel = params.get('model');
const wantedDate = params.get('date');

function fmtRs(v) { return '\u20B9' + Number(v).toFixed(2); }

async function load() {
  if (!symbol) {
    document.getElementById('subHeader').textContent = 'No symbol specified in URL.';
    return;
  }
  document.getElementById('symHeader').textContent = symbol;

  // 1. Pull per-stock JSON
  let data;
  try {
    const safe = symbol.replace('&', '_AND_').replace('/', '_');
    const resp = await fetch('stockdata/' + safe + '.json');
    if (!resp.ok) throw new Error(resp.status);
    data = await resp.json();
  } catch (e) {
    document.getElementById('subHeader').textContent =
      'Stock data file not found. (' + e + ')';
    return;
  }
  document.getElementById('subHeader').textContent =
    data.bars.length + ' bars  \u00B7  ' + data.markers.length + ' historical signal(s)';

  // 2. Render candlestick chart
  const chart = LightweightCharts.createChart(document.getElementById('chart'), {
    layout: { background: { color: '#151b30' }, textColor: '#e9edf6' },
    grid: { vertLines: { color: '#1f2742' }, horzLines: { color: '#1f2742' } },
    timeScale: { borderColor: '#1f2742' },
    rightPriceScale: { borderColor: '#1f2742' },
    crosshair: { mode: 0 },
    autoSize: true,
  });
  const candles = chart.addCandlestickSeries({
    upColor: '#34c38f', downColor: '#e07a7a',
    borderUpColor: '#34c38f', borderDownColor: '#e07a7a',
    wickUpColor: '#34c38f', wickDownColor: '#e07a7a',
  });
  candles.setData(data.bars);

  if (data.ema50.length) {
    chart.addLineSeries({ color: '#6ea8ff', lineWidth: 2, priceLineVisible: false })
         .setData(data.ema50);
  }
  if (data.bb_upper.length) {
    chart.addLineSeries({ color: '#8a93ab', lineWidth: 1, priceLineVisible: false, lineStyle: 2 })
         .setData(data.bb_upper);
  }
  if (data.bb_lower.length) {
    chart.addLineSeries({ color: '#8a93ab', lineWidth: 1, priceLineVisible: false, lineStyle: 2 })
         .setData(data.bb_lower);
  }

  // 3. Markers for every historical signal
  const markers = data.markers.map(m => ({
    time: m.time,
    position: 'belowBar',
    color: m.status === 'target' ? '#34c38f'
         : m.status === 'stop'   ? '#e07a7a'
         : m.status === 'timeout'? '#f5b14f'
         : '#6ea8ff',
    shape: 'arrowUp',
    text: m.model.split('_').map(w=>w[0].toUpperCase()).join(''),
  }));
  candles.setMarkers(markers);

  document.getElementById('chartLegend').innerHTML =
    'Blue line = 50-EMA &nbsp;\u00B7&nbsp; Grey dashed = Bollinger Bands(20,2) &nbsp;\u00B7&nbsp; ' +
    '<span class="good">\u25B2</span> target hit &nbsp;' +
    '<span class="weak">\u25B2</span> stopped &nbsp;' +
    '<span class="ok">\u25B2</span> timed out &nbsp;' +
    '<span style="color:#6ea8ff">\u25B2</span> still open. ' +
    'Arrow letters: TM = Trend-Momentum, BV = Breakout-Volume, MR = Mean-Reversion, C = Confluence.';

  // 4. "Why this stock" - find the specific prediction matching ?model= & ?date=
  let target = null;
  if (wantedModel && wantedDate) {
    target = data.markers.find(m => m.model === wantedModel && m.time === wantedDate);
  }
  if (!target && data.markers.length) {
    target = data.markers[data.markers.length - 1];
  }

  const whyDiv = document.getElementById('whyBlock');
  if (!target) {
    whyDiv.textContent = 'No specific signal selected.';
  } else {
    try {
      const histResp = await fetch('history.json');
      const hist = await histResp.json();
      const match = hist.find(h =>
        h.symbol === symbol && h.model === target.model && h.signal_date === target.time);
      if (match) {
        const reasons = (match.reasons || []).map(r => '<li>' + r + '</li>').join('');
        whyDiv.innerHTML = `
          <p><strong>Model:</strong> ${match.model} &nbsp;\u00B7&nbsp;
             <strong>Signal date:</strong> ${match.signal_date}</p>
          <p>
            <strong>Trigger:</strong> ${fmtRs(match.trigger)} &nbsp;\u00B7&nbsp;
            <strong>Target:</strong> ${fmtRs(match.target)} &nbsp;\u00B7&nbsp;
            <strong>Stop:</strong> ${fmtRs(match.stop)} &nbsp;\u00B7&nbsp;
            <strong>R:R:</strong> ${Number(match.reward_risk).toFixed(2)}
          </p>
          <p><strong>Status:</strong> <span class="pill ${match.status}">${match.status.toUpperCase()}</span>
            ${match.exit_date ? '\u00B7 exited ' + match.exit_date + ' at ' + fmtRs(match.exit_price) : ''}
          </p>
          <h3 style="font-size:14px; margin:14px 0 6px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em">Confirming signals that day</h3>
          <ul class="reason-list">${reasons || '<li>(no reasons recorded)</li>'}</ul>
          <p class="muted" style="margin-top:10px">
            See the <a href="models.html#${match.model}">full model description</a> for the complete rule set.
          </p>`;
      } else {
        whyDiv.textContent = 'Signal found on chart but not in history (it may be older than the history file).';
      }
    } catch (e) {
      whyDiv.textContent = 'Could not load history: ' + e;
    }
  }

  // 5. Marker table
  const markerTbl = document.getElementById('markerTable');
  if (!data.markers.length) {
    markerTbl.innerHTML = '<p class="muted">No historical signals in the chart window.</p>';
  } else {
    const rows = [...data.markers].reverse().map(m => `
      <tr>
        <td>${m.time}</td>
        <td>${m.model}</td>
        <td><span class="pill ${m.status}">${m.status.toUpperCase()}</span></td>
        <td>${fmtRs(m.trigger)}</td>
        <td>${fmtRs(m.target)}</td>
        <td>${fmtRs(m.stop)}</td>
      </tr>`).join('');
    markerTbl.innerHTML = `<table>
      <thead><tr><th>Date</th><th>Model</th><th>Outcome</th><th>Trigger</th><th>Target</th><th>Stop</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  }
}
load();
</script>
"""
    STOCK_HTML.write_text(_page("Stock detail", "home", body, extra_head=extra_head))
