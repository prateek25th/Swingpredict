"""Helpers for deriving the confidence label from a hit-rate, and for
selecting the top-N picks per market-cap category.
"""
from __future__ import annotations

from config import (
    CATEGORY_ORDER,
    CONFIDENCE_HIGH_MIN,
    CONFIDENCE_MED_MIN,
    TOP_N_PER_CATEGORY,
)
import universe  # imported as module so the multi-cap fetch can be patched in tests
from universe import CATEGORY_LABELS


def confidence_label(profit_rate: float | None) -> tuple[str, str]:
    """Return (text_label, css_class) for a given *profit probability*.

    Profit probability = fraction of historical signals that exited with
    positive R-multiple (target hits + profitable timeouts). For a 2:1 R:R
    system the random baseline is around 50%, so:

        High    : profit_rate >= 60%   (clear edge over random)
        Medium  : profit_rate in [50%, 60%)
        Low     : profit_rate < 50%
        Unknown : fewer than 8 historical signals
    """
    if profit_rate is None:
        return ("Unknown", "muted")
    if profit_rate >= CONFIDENCE_HIGH_MIN:
        return ("High", "good")
    if profit_rate >= CONFIDENCE_MED_MIN:
        return ("Medium", "ok")
    return ("Low", "weak")


def category_lookup() -> dict[str, str]:
    """Return {symbol: category}. Built fresh per call from the universe loader."""
    return {e.symbol: e.category for e in universe.fetch_universe()}


def sort_key_hit_rate_desc(s: dict) -> tuple:
    """Sort signals so highest *profit_rate* is first (nulls last), with
    hit_rate as the first tiebreak and reward:risk as the second.
    Kept name for back-compat -- it now ranks on profit_rate, the better metric.
    """
    pr = s.get("profit_rate")
    hr = s.get("hit_rate")
    return (
        pr is None,             # nulls last
        -(pr or 0),             # higher profit_rate first
        -(hr or 0),             # tiebreak on hit_rate
        -s.get("reward_risk", 0),
    )


def top_n_per_category(
    signals: list[dict], n: int = TOP_N_PER_CATEGORY
) -> dict[str, list[dict]]:
    """Bucket signals by category and return the top N from each, ranked by profit_rate."""
    lookup = category_lookup()
    buckets: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}
    for s in signals:
        cat = lookup.get(s["symbol"], "large_cap")
        s.setdefault("category", cat)
        buckets[cat].append(s)
    for cat in buckets:
        buckets[cat].sort(key=sort_key_hit_rate_desc)
        buckets[cat] = buckets[cat][:n]
    return buckets


def annotate_signals(signals: list[dict]) -> list[dict]:
    """Attach category, confidence label/class, and a stable signal_id to every signal.

    Confidence is now derived from *profit_rate* (a more honest measure than
    raw hit-rate; see confidence_label docstring).

    Idempotent: signals with an existing 'confidence' field are left alone.
    """
    lookup = category_lookup()
    for s in signals:
        if "confidence" in s and "signal_id" in s:
            continue
        s["category"] = lookup.get(s["symbol"], "large_cap")
        s["category_label"] = CATEGORY_LABELS.get(s["category"], "")
        label, css = confidence_label(s.get("profit_rate"))
        s["confidence"] = label
        s["confidence_class"] = css
        s["signal_id"] = (
            f"{s['symbol']}-{s['model']}-{s['signal_date']}".replace(".", "_")
        )
    return signals
