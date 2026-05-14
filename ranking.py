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


def confidence_label(hit_rate: float | None) -> tuple[str, str]:
    """Return (text_label, css_class) for a given hit-rate.

    Returns one of:
        ("High",    "good")
        ("Medium",  "ok")
        ("Low",     "weak")
        ("Unknown", "muted")    # for n/a hit-rate (too few historical signals)
    """
    if hit_rate is None:
        return ("Unknown", "muted")
    if hit_rate >= CONFIDENCE_HIGH_MIN:
        return ("High", "good")
    if hit_rate >= CONFIDENCE_MED_MIN:
        return ("Medium", "ok")
    return ("Low", "weak")


def category_lookup() -> dict[str, str]:
    """Return {symbol: category}. Built fresh per call from the universe loader."""
    return {e.symbol: e.category for e in universe.fetch_universe()}


def sort_key_hit_rate_desc(s: dict) -> tuple:
    """Sort signals so highest hit-rate is first, nulls last, ties broken by R:R."""
    hr = s.get("hit_rate")
    return (hr is None, -(hr or 0), -s.get("reward_risk", 0))


def top_n_per_category(
    signals: list[dict], n: int = TOP_N_PER_CATEGORY
) -> dict[str, list[dict]]:
    """Bucket signals by category and return the top N from each."""
    lookup = category_lookup()
    buckets: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}
    for s in signals:
        cat = lookup.get(s["symbol"], "large_cap")  # default if unknown
        s.setdefault("category", cat)
        buckets[cat].append(s)
    for cat in buckets:
        buckets[cat].sort(key=sort_key_hit_rate_desc)
        buckets[cat] = buckets[cat][:n]
    return buckets


def annotate_signals(signals: list[dict]) -> list[dict]:
    """Attach category, confidence label/class, and a stable signal_id to every signal.

    Idempotent: if a signal already has a 'confidence' field, it's left alone.
    The signal_id is used as the inline-expand row anchor in the HTML.
    """
    lookup = category_lookup()
    for s in signals:
        if "confidence" in s and "signal_id" in s:
            continue
        s["category"] = lookup.get(s["symbol"], "large_cap")
        s["category_label"] = CATEGORY_LABELS.get(s["category"], "")
        label, css = confidence_label(s.get("hit_rate"))
        s["confidence"] = label
        s["confidence_class"] = css
        s["signal_id"] = (
            f"{s['symbol']}-{s['model']}-{s['signal_date']}".replace(".", "_")
        )
    return signals
