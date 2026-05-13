"""Base Signal dataclass + BaseModel class for the four swing-trading models."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable

import pandas as pd

from config import HOLD_MAX_DAYS
from indicators import enrich


@dataclass
class Signal:
    model: str
    symbol: str
    signal_date: str          # ISO date
    trigger: float
    target: float
    stop: float
    atr: float
    expected_hold_days: int
    reward_risk: float
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class BaseModel:
    name: str = "base"
    k_stop: float = 1.5
    k_target: float = 3.0

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        return enrich(df)

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:  # noqa: ARG002
        raise NotImplementedError

    def _levels(self, close: float, atr_val: float) -> tuple[float, float, float]:
        """Return (trigger, target, stop) given today's close and ATR."""
        trigger = close
        stop = round(close - self.k_stop * atr_val, 2)
        target = round(close + self.k_target * atr_val, 2)
        return round(trigger, 2), target, stop

    def to_signal(self, symbol: str, df_enriched: pd.DataFrame, idx) -> Signal:
        close = float(df_enriched.loc[idx, "close"])
        atr_val = float(df_enriched.loc[idx, "atr14"])
        trigger, target, stop = self._levels(close, atr_val)
        rr = (target - trigger) / max(trigger - stop, 1e-9)
        return Signal(
            model=self.name,
            symbol=symbol,
            signal_date=pd.Timestamp(idx).date().isoformat(),
            trigger=trigger,
            target=target,
            stop=stop,
            atr=round(atr_val, 2),
            expected_hold_days=HOLD_MAX_DAYS,
            reward_risk=round(rr, 2),
        )

    def latest_signal(self, symbol: str, df: pd.DataFrame) -> Signal | None:
        """Return a Signal iff the most recent bar fires the model."""
        e = self.prepare(df)
        sigs = self.generate_signals(e)
        if sigs.empty or not bool(sigs.iloc[-1]):
            return None
        return self.to_signal(symbol, e, e.index[-1])

    def historical_signals(self, df: pd.DataFrame) -> Iterable[pd.Timestamp]:
        e = self.prepare(df)
        sigs = self.generate_signals(e)
        return list(e.index[sigs.fillna(False).astype(bool)])
