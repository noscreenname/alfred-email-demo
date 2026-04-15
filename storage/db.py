"""SQLite schema + helpers for Alfred caches and action log."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS classification_cache (
    key TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    label TEXT NOT NULL,
    confidence REAL NOT NULL,
    reasoning TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS response_cache (
    key TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    contract_mode TEXT NOT NULL,
    reply TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    message_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    subject TEXT NOT NULL,
    contract_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


# --- classification cache ---

def get_classification(key: str) -> Optional[dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(
            "SELECT label, confidence, reasoning FROM classification_cache WHERE key=?",
            (key,),
        ).fetchone()
    if not row:
        return None
    return {"label": row["label"], "confidence": row["confidence"], "reasoning": row["reasoning"]}


def put_classification(key: str, message_id: str, result: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO classification_cache (key, message_id, label, confidence, reasoning, created_at) VALUES (?,?,?,?,?,?)",
            (key, message_id, result.get("label", "ambiguous"),
             float(result.get("confidence", 0.0)), result.get("reasoning", ""), _now()),
        )


# --- response cache ---

def get_response(message_id: str, contract_mode: str) -> Optional[str]:
    key = f"{message_id}:{contract_mode}"
    with connect() as conn:
        row = conn.execute(
            "SELECT reply FROM response_cache WHERE key=?", (key,)
        ).fetchone()
    return row["reply"] if row else None


def put_response(message_id: str, contract_mode: str, reply: str) -> None:
    key = f"{message_id}:{contract_mode}"
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO response_cache (key, message_id, contract_mode, reply, created_at) VALUES (?,?,?,?,?)",
            (key, message_id, contract_mode, reply, _now()),
        )


# --- action log ---

def append_action(
    message_id: str, sender: str, subject: str,
    contract_mode: str, status: str, reason: str,
) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO action_log (timestamp, message_id, sender, subject, contract_mode, status, reason) VALUES (?,?,?,?,?,?,?)",
            (_now(), message_id, sender, subject, contract_mode, status, reason),
        )


def list_actions(mode_filter: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
    q = "SELECT * FROM action_log"
    args: tuple = ()
    if mode_filter:
        q += " WHERE contract_mode=?"
        args = (mode_filter,)
    q += " ORDER BY id DESC LIMIT ?"
    args = args + (limit,)
    with connect() as conn:
        rows = conn.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def classification_count() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM classification_cache").fetchone()
    return int(row["n"])
