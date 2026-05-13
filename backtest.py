"""Historical-replay backtester.

For every historical signal a model would have fired, walk forward up to
``HOLD_MAX_DAYS`` bars and record whether target was hit before stop.
Aggregate to a per-(symbol, model) hit-rate, which is what we publish as
the "probability of touching target before stop".

No look-ahead: indicators are computed on the full series, but the
outcome of any historical signal uses only the bars *after* that signal.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from config import HOLD_MAX_DAYS, MIN_HISTORICAL_SIGNALS_FOR_PROB
from base_model import BaseModel


@dataclass
class BacktestSummary:
    symbol: str
    model: str
    n_signals: int
    n_target_hit: int
    n_stop_hit: int
    n_timeout: int
    hit_rate: float | None         # probability of target before stop
    avg_days_to_target: float | None
    avg_r_multiple: float | None   # expectancy in R units
    last_signals_outcomes: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def _walk_forward(df: pd.DataFrame, signal_idx: pd.Timestamp,
                  trigger: float, target: float, stop: float,
                  max_days: int) -> tuple[str, int, float]:
    """Replay the next ``max_days`` bars after ``signal_idx``.

    Returns (outcome, days_to_exit, r_multiple).
        outcome      : 'target' | 'stop' | 'timeout'
        days_to_exit : bars elapsed at exit
        r_multiple   : (exit_price - trigger) / (trigger - stop)

    Conservative rule: if both target and stop fall within a single bar's
    high-low range, we assume the stop was hit first.
    """
    pos = df.index.get_loc(signal_idx)
    forward = df.iloc[pos + 1 : pos + 1 + max_days]
    if forward.empty:
        return ("timeout", 0, 0.0)

    risk = trigger - stop
    for i, (_, bar) in enumerate(forward.iterrows(), start=1):
        if bar["low"] <= stop:
            r = (stop - trigger) / max(risk, 1e-9)
            return ("stop", i, r)
        if bar["high"] >= target:
            r = (target - trigger) / max(risk, 1e-9)
            return ("target", i, r)

    exit_price = float(forward["close"].iloc[-1])
    r = (exit_price - trigger) / max(risk, 1e-9)
    return ("timeout", len(forward), r)


def backtest_symbol_model(symbol: str, df: pd.DataFrame, model: BaseModel,
                           max_days: int = HOLD_MAX_DAYS) -> BacktestSummary:
    enriched = model.prepare(df)
    sig_mask = model.generate_signals(enriched).fillna(False).astype(bool)
    sig_dates = enriched.index[sig_mask]

    outcomes: list[dict] = []
    target_hits = stop_hits = timeouts = 0
    days_to_target: list[int] = []
    r_multiples: list[float] = []

    for idx in sig_dates:
        close = float(enriched.loc[idx, "close"])
        atr_val = float(enriched.loc[idx, "atr14"])
        if not np.isfinite(atr_val) or atr_val == 0:
            continue
        trigger = close
        stop = round(trigger - model.k_stop * atr_val, 2)
        target = round(trigger + model.k_target * atr_val, 2)

        outcome, days, r_mult = _walk_forward(
            enriched, idx, trigger, target, stop, max_days
        )
        if outcome == "target":
            target_hits += 1
            days_to_target.append(days)
        elif outcome == "stop":
            stop_hits += 1
        else:
            timeouts += 1
        r_multiples.append(r_mult)

        outcomes.append({
            "signal_date": pd.Timestamp(idx).date().isoformat(),
            "trigger": round(trigger, 2),
            "target": target,
            "stop": stop,
            "outcome": outcome,
            "days": days,
            "r_multiple": round(r_mult, 2),
        })

    n = len(outcomes)
    hit_rate = (target_hits / n) if n >= MIN_HISTORICAL_SIGNALS_FOR_PROB else None
    avg_d = float(np.mean(days_to_target)) if days_to_target else None
    avg_r = float(np.mean(r_multiples)) if r_multiples else None

    return BacktestSummary(
        symbol=symbol,
        model=model.name,
        n_signals=n,
        n_target_hit=target_hits,
        n_stop_hit=stop_hits,
        n_timeout=timeouts,
        hit_rate=round(hit_rate, 3) if hit_rate is not None else None,
        avg_days_to_target=round(avg_d, 2) if avg_d is not None else None,
        avg_r_multiple=round(avg_r, 3) if avg_r is not None else None,
        last_signals_outcomes=outcomes[-5:],
    )
