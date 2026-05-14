"""Prediction history tracker (SQLite-backed).

Schema
------
Single table, ``predictions``:
    symbol            TEXT     part of composite primary key
    model             TEXT     part of composite primary key
    signal_date       TEXT     part of composite primary key (ISO date)
    trigger           REAL
    target            REAL
    stop              REAL
    atr               REAL
    reward_risk       REAL
    hit_rate_at_pick  REAL     hit-rate the model published when the pick was made
    historical_n      INTEGER  signals that fed the published hit-rate
    reasons_json      TEXT     list of plain-English reasons (JSON)
    status            TEXT     'open' | 'target' | 'stop' | 'timeout'
    exit_date         TEXT     ISO date, null while open
    exit_price        REAL     null while open
    days_held         INTEGER  null while open
    r_multiple        REAL     null while open
    created_at        TEXT     ISO timestamp the row was inserted

Lifecycle
---------
1. ``record_predictions`` inserts today's fresh signals as status='open'.
   Composite PK makes re-runs on the same day idempotent (INSERT OR IGNORE).
2. ``update_open_predictions`` walks each open row through the price history
   since the signal date, updating to 'target' / 'stop' / 'timeout' once
   resolved. Conservative tie-break: if both target and stop fall within a
   single bar's high-low range, stop wins.
3. ``export_snapshot_json`` writes ``web/history.json`` so the static front-end
   (which can't run SQL queries) can read the history client-side. The DB
   remains the source of truth.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from config import HISTORY_DB, HISTORY_EXPORT_JSON, HOLD_MAX_DAYS
import fetch  # imported as module so selftest can monkey-patch fetch.load

log = logging.getLogger(__name__)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    symbol              TEXT    NOT NULL,
    model               TEXT    NOT NULL,
    signal_date         TEXT    NOT NULL,
    trigger             REAL    NOT NULL,
    target              REAL    NOT NULL,
    stop                REAL    NOT NULL,
    atr                 REAL,
    reward_risk         REAL,
    hit_rate_at_pick    REAL,
    profit_rate_at_pick REAL,
    historical_n        INTEGER,
    reasons_json        TEXT,
    status              TEXT    NOT NULL DEFAULT 'open',
    exit_date           TEXT,
    exit_price          REAL,
    days_held           INTEGER,
    r_multiple          REAL,
    created_at          TEXT    NOT NULL,
    PRIMARY KEY (symbol, model, signal_date)
);

CREATE INDEX IF NOT EXISTS ix_predictions_status      ON predictions(status);
CREATE INDEX IF NOT EXISTS ix_predictions_signal_date ON predictions(signal_date);
CREATE INDEX IF NOT EXISTS ix_predictions_symbol      ON predictions(symbol);
"""


def _ensure_profit_rate_column(con: sqlite3.Connection) -> None:
    """Schema migration: add profit_rate_at_pick column if it's missing.
    Run on every connection so upgrades from v3 -> v3a are transparent.
    """
    cols = {row[1] for row in con.execute("PRAGMA table_info(predictions)").fetchall()}
    if "profit_rate_at_pick" not in cols:
        con.execute("ALTER TABLE predictions ADD COLUMN profit_rate_at_pick REAL")


@contextmanager
def _conn():
    """Yield a SQLite connection with row_factory set to dict-like rows."""
    HISTORY_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(HISTORY_DB)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(_SCHEMA)
        _ensure_profit_rate_column(con)
        yield con
        con.commit()
    finally:
        con.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    raw = d.pop("reasons_json", None)
    try:
        d["reasons"] = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        d["reasons"] = []
    return d


# --------------------------------------------------------------------------- #
# Writes
# --------------------------------------------------------------------------- #
def record_predictions(fresh_signals: list[dict]) -> int:
    """Insert today's fresh signals. Returns count of *new* records.

    INSERT OR IGNORE on the composite PK means re-running the daily job on the
    same day will not create duplicates.
    """
    if not fresh_signals:
        return 0

    now = datetime.utcnow().isoformat(timespec="seconds")
    new_count = 0
    with _conn() as con:
        for s in fresh_signals:
            cur = con.execute(
                """
                INSERT OR IGNORE INTO predictions
                  (symbol, model, signal_date, trigger, target, stop, atr,
                   reward_risk, hit_rate_at_pick, profit_rate_at_pick,
                   historical_n, reasons_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                (
                    s["symbol"], s["model"], s["signal_date"],
                    s["trigger"], s["target"], s["stop"], s.get("atr"),
                    s.get("reward_risk"),
                    s.get("hit_rate"), s.get("profit_rate"),
                    s.get("historical_n", 0),
                    json.dumps(s.get("reasons", [])),
                    now,
                ),
            )
            if cur.rowcount:
                new_count += 1
    log.info("Recorded %d new predictions.", new_count)
    return new_count


def update_open_predictions() -> dict[str, int]:
    """Walk every open prediction forward; mark target/stop/timeout outcomes."""
    summary = {"target": 0, "stop": 0, "timeout": 0, "still_open": 0}

    with _conn() as con:
        open_rows = con.execute(
            "SELECT rowid, * FROM predictions WHERE status = 'open'"
        ).fetchall()

        for row in open_rows:
            sym = row["symbol"]
            sig_date = pd.Timestamp(row["signal_date"])
            df = fetch.load(sym)
            if df is None or df.empty:
                summary["still_open"] += 1
                continue

            forward = df[df.index > sig_date].iloc[:HOLD_MAX_DAYS]
            if forward.empty:
                summary["still_open"] += 1
                continue

            trigger = row["trigger"]
            target = row["target"]
            stop = row["stop"]
            risk = max(trigger - stop, 1e-9)

            outcome = None
            exit_idx = None
            exit_price = None
            days_held = None

            for i, (ts, bar) in enumerate(forward.iterrows(), start=1):
                if bar["low"] <= stop:
                    outcome, exit_idx, exit_price, days_held = "stop", ts, stop, i
                    break
                if bar["high"] >= target:
                    outcome, exit_idx, exit_price, days_held = "target", ts, target, i
                    break

            if outcome is None:
                if len(forward) >= HOLD_MAX_DAYS:
                    outcome = "timeout"
                    exit_idx = forward.index[-1]
                    exit_price = float(forward["close"].iloc[-1])
                    days_held = len(forward)
                else:
                    summary["still_open"] += 1
                    continue

            r = (exit_price - trigger) / risk
            con.execute(
                """
                UPDATE predictions
                   SET status = ?, exit_date = ?, exit_price = ?,
                       days_held = ?, r_multiple = ?
                 WHERE rowid = ?
                """,
                (outcome, pd.Timestamp(exit_idx).date().isoformat(),
                 round(float(exit_price), 2), int(days_held), round(r, 2),
                 row["rowid"]),
            )
            summary[outcome] += 1

    log.info("Updated outcomes: %s", summary)
    return summary


# --------------------------------------------------------------------------- #
# Reads / exports
# --------------------------------------------------------------------------- #
def get_all() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM predictions ORDER BY signal_date DESC, symbol ASC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_for_symbol(symbol: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM predictions WHERE symbol = ? ORDER BY signal_date ASC",
            (symbol,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def aggregate_stats() -> dict:
    """Top-line stats for the history page header."""
    with _conn() as con:
        total = con.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        rows = con.execute(
            """
            SELECT status, COUNT(*) AS n, AVG(r_multiple) AS avg_r
              FROM predictions
             GROUP BY status
            """
        ).fetchall()

    by_status = {r["status"]: r["n"] for r in rows}
    avg_r_overall = None
    closed_total = sum(by_status.get(s, 0) for s in ("target", "stop", "timeout"))
    if closed_total:
        with _conn() as con:
            avg = con.execute(
                "SELECT AVG(r_multiple) FROM predictions WHERE status != 'open'"
            ).fetchone()[0]
        if avg is not None:
            avg_r_overall = round(avg, 3)

    return {
        "total": total,
        "open": by_status.get("open", 0),
        "closed": closed_total,
        "target": by_status.get("target", 0),
        "stop": by_status.get("stop", 0),
        "timeout": by_status.get("timeout", 0),
        "hit_rate": round(by_status.get("target", 0) / closed_total, 3) if closed_total else None,
        "avg_r": avg_r_overall,
    }


def export_snapshot_json() -> int:
    """Export the full history table as JSON for the static front-end.

    Returns the number of records exported. The static site can't query SQL,
    so this snapshot is what the history page and per-stock page read.
    """
    rows = get_all()
    HISTORY_EXPORT_JSON.write_text(json.dumps(rows, default=str))
    log.info("Exported %d history rows -> %s", len(rows), HISTORY_EXPORT_JSON)
    return len(rows)
