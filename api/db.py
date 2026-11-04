"""Persistence layer.

SQLite is the zero-config local store; ``supabase/migrations`` holds the same
schema for Postgres. Progress is an append-only event log, so replay and the
dashboard both read the same rows.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from .config import settings

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS communities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    households INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS residents (
    id TEXT PRIMARY KEY,
    community_id TEXT NOT NULL REFERENCES communities(id),
    flat_number TEXT,
    language TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS demand_requests (
    id TEXT PRIMARY KEY,
    resident_id TEXT,
    community_id TEXT NOT NULL,
    product TEXT NOT NULL,
    qty INTEGER NOT NULL,
    frequency TEXT NOT NULL DEFAULT 'weekly',
    delivery_day TEXT,
    language TEXT,
    status TEXT NOT NULL DEFAULT 'confirmed',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    persona TEXT NOT NULL,
    product TEXT NOT NULL,
    free_delivery_qty INTEGER,
    delivery_days INTEGER,
    delivery_charge REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendor_offers (
    id TEXT PRIMARY KEY,
    negotiation_id TEXT,
    vendor_id TEXT NOT NULL,
    product TEXT NOT NULL,
    unit_price REAL NOT NULL,
    delivery_charge REAL NOT NULL DEFAULT 0,
    min_qty INTEGER,
    valid_days INTEGER,
    source TEXT NOT NULL DEFAULT 'simulated',
    round INTEGER NOT NULL DEFAULT 0,
    eligible INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS negotiations (
    id TEXT PRIMARY KEY,
    community_id TEXT NOT NULL,
    vendor_id TEXT,
    product TEXT NOT NULL,
    qty INTEGER NOT NULL,
    state TEXT NOT NULL,
    round INTEGER NOT NULL DEFAULT 0,
    max_rounds INTEGER NOT NULL DEFAULT 3,
    language TEXT,
    first_quote REAL,
    best_quote REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS negotiation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negotiation_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_events_negotiation
    ON negotiation_events(negotiation_id, id);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    negotiation_id TEXT NOT NULL,
    offer_id TEXT,
    admin_id TEXT,
    decision TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);
"""

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def connect(path: Optional[str] = None) -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn
    target = Path(path or settings.database_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _conn = conn
    return conn


def reset_connection() -> None:
    """Used by tests."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def init_db(path: Optional[str] = None) -> sqlite3.Connection:
    return connect(path)


# --------------------------------------------------------------------------- seed
COMMUNITY_ID = "green-residency"


def seed(conn: sqlite3.Connection) -> None:
    """Idempotent synthetic seed: Green Residency, 360 baseline cans, three vendors."""
    stamp = now_iso()
    with conn:
        if not conn.execute("SELECT id FROM communities WHERE id = ?", (COMMUNITY_ID,)).fetchone():
            conn.execute(
                "INSERT INTO communities (id, name, households, created_at) VALUES (?,?,?,?)",
                (COMMUNITY_ID, "Green Residency", 120, stamp),
            )
        vendors = [
            ("vendor-stubborn", "Sri Lakshmi Water Agency", "stubborn", 300, 2, 60.0),
            ("vendor-friendly", "Bengaluru Aqua Distributors", "friendly volume-hungry", 240, 1, 0.0),
            ("vendor-cheap-slow", "Cauvery Can Supply", "cheap but slow", 500, 3, 40.0),
        ]
        for vendor_id, name, persona, free_qty, days, charge in vendors:
            conn.execute(
                """INSERT OR IGNORE INTO vendors
                   (id, name, persona, product, free_delivery_qty, delivery_days, delivery_charge, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (vendor_id, name, persona, "water can", free_qty, days, charge, stamp),
            )

        # 120 households x 3 water cans = the 360/week verified baseline. Fixed
        # ids, so a second boot never double-counts and resident-added rows sit
        # on top of it (360 -> 363 after one confirmed request).
        residents = [
            (f"res-{index}", COMMUNITY_ID, f"A-{index:03d}", "kn-IN", stamp)
            for index in range(1, 121)
        ]
        conn.executemany(
            """INSERT OR IGNORE INTO residents
               (id, community_id, flat_number, language, created_at)
               VALUES (?,?,?,?,?)""",
            residents,
        )
        demands = [
            (
                f"dem-{index}",
                f"res-{index}",
                COMMUNITY_ID,
                "water can",
                3,
                "weekly",
                "Saturday",
                "kn-IN",
                "confirmed",
                stamp,
            )
            for index in range(1, 121)
        ]
        conn.executemany(
            """INSERT OR IGNORE INTO demand_requests
               (id, resident_id, community_id, product, qty, frequency, delivery_day,
                language, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            demands,
        )


def health() -> dict[str, Any]:
    try:
        conn = connect()
        conn.execute("SELECT 1")
        return {"ok": True, "database": "sqlite", "path": settings.database_path}
    except Exception as exc:  # pragma: no cover - surfaced in /api/health
        return {"ok": False, "database": "sqlite", "error": str(exc)}


# ---------------------------------------------------------------------- mutations
def create_negotiation(
    *,
    community_id: str = COMMUNITY_ID,
    product: str,
    qty: int,
    language: str,
    state: str = "ASK_QUOTE",
    max_rounds: int = 3,
) -> str:
    conn = connect()
    negotiation_id = f"neg-{uuid.uuid4().hex[:10]}"
    stamp = now_iso()
    with conn:
        conn.execute(
            """INSERT INTO negotiations
               (id, community_id, product, qty, state, round, max_rounds, language, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (negotiation_id, community_id, product, qty, state, 0, max_rounds, language, stamp, stamp),
        )
    return negotiation_id


def update_negotiation(
    negotiation_id: str,
    *,
    state: Optional[str] = None,
    round_no: Optional[int] = None,
    first_quote: Optional[float] = None,
    best_quote: Optional[float] = None,
) -> None:
    conn = connect()
    fields: list[str] = ["updated_at = ?"]
    values: list[Any] = [now_iso()]
    if state is not None:
        fields.append("state = ?")
        values.append(state)
    if round_no is not None:
        fields.append("round = ?")
        values.append(round_no)
    if first_quote is not None:
        fields.append("first_quote = ?")
        values.append(first_quote)
    if best_quote is not None:
        fields.append("best_quote = ?")
        values.append(best_quote)
    values.append(negotiation_id)
    with conn:
        conn.execute(f"UPDATE negotiations SET {', '.join(fields)} WHERE id = ?", values)


def add_event(
    negotiation_id: str,
    *,
    actor: str,
    type: str,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO negotiation_events (negotiation_id, ts, actor, type, payload) VALUES (?,?,?,?,?)",
            (negotiation_id, now_iso(), actor, type, json.dumps(payload or {}, ensure_ascii=False)),
        )


def save_offer(
    negotiation_id: str,
    *,
    vendor_id: str,
    product: str,
    unit_price: float,
    delivery_charge: float,
    min_qty: Optional[int],
    valid_days: Optional[int],
    round_no: int,
    eligible: bool,
    source: str = "simulated",
) -> str:
    conn = connect()
    offer_id = f"offer-{uuid.uuid4().hex[:10]}"
    with conn:
        conn.execute(
            """INSERT INTO vendor_offers
               (id, negotiation_id, vendor_id, product, unit_price, delivery_charge, min_qty,
                valid_days, source, round, eligible, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                offer_id,
                negotiation_id,
                vendor_id,
                product,
                float(unit_price),
                float(delivery_charge or 0),
                min_qty,
                valid_days,
                source,
                round_no,
                1 if eligible else 0,
                now_iso(),
            ),
        )
    return offer_id


def save_demand(
    *,
    resident_id: Optional[str],
    community_id: str,
    product: str,
    qty: int,
    frequency: str,
    delivery_day: Optional[str],
    language: str,
) -> str:
    conn = connect()
    demand_id = f"dem-{uuid.uuid4().hex[:10]}"
    with conn:
        conn.execute(
            """INSERT INTO demand_requests
               (id, resident_id, community_id, product, qty, frequency, delivery_day, language, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                demand_id,
                resident_id,
                community_id,
                product,
                qty,
                frequency,
                delivery_day,
                language,
                "confirmed",
                now_iso(),
            ),
        )
    return demand_id


def aggregate_demand(community_id: str = COMMUNITY_ID, product: str = "water can") -> dict[str, Any]:
    conn = connect()
    row = conn.execute(
        """SELECT COALESCE(SUM(qty),0) AS total, COUNT(*) AS requests, COUNT(DISTINCT resident_id) AS households
           FROM demand_requests WHERE community_id = ? AND product = ? AND status = 'confirmed'""",
        (community_id, product),
    ).fetchone()
    return {
        "product": product,
        "total_qty": int(row["total"] or 0),
        "requests": int(row["requests"] or 0),
        "households": int(row["households"] or 0),
    }


def save_approval(
    *,
    negotiation_id: str,
    decision: str,
    note: str = "",
    admin_id: str = "committee-admin",
    offer_id: Optional[str] = None,
) -> str:
    conn = connect()
    approval_id = f"apr-{uuid.uuid4().hex[:10]}"
    with conn:
        conn.execute(
            """INSERT INTO approvals (id, negotiation_id, offer_id, admin_id, decision, note, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (approval_id, negotiation_id, offer_id, admin_id, decision, note, now_iso()),
        )
    return approval_id


# ------------------------------------------------------------------------ queries
def list_sessions(limit: int = 20) -> list[dict[str, Any]]:
    conn = connect()
    rows = conn.execute(
        """SELECT n.id, n.community_id, n.product, n.qty, n.state, n.round, n.language,
                  n.created_at, c.name AS community,
                  (SELECT COUNT(*) FROM negotiation_events e WHERE e.negotiation_id = n.id) AS events
           FROM negotiations n
           LEFT JOIN communities c ON c.id = n.community_id
           ORDER BY n.created_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_events(negotiation_id: str) -> list[dict[str, Any]]:
    conn = connect()
    rows = conn.execute(
        "SELECT ts, actor, type, payload FROM negotiation_events WHERE negotiation_id = ? ORDER BY id",
        (negotiation_id,),
    ).fetchall()
    events = []
    for row in rows:
        payload = row["payload"]
        try:
            payload = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            payload = {}
        events.append({"ts": row["ts"], "actor": row["actor"], "type": row["type"], "payload": payload})
    return events


def list_vendors() -> list[dict[str, Any]]:
    conn = connect()
    rows = conn.execute("SELECT * FROM vendors ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def demand_summary(community_id: str = COMMUNITY_ID) -> dict[str, Any]:
    """Households and total weekly quantity per product, from confirmed rows."""
    conn = connect()
    rows = conn.execute(
        """SELECT product,
                  COALESCE(SUM(qty), 0) AS total_qty,
                  COUNT(*) AS requests,
                  COUNT(DISTINCT resident_id) AS households
           FROM demand_requests
           WHERE community_id = ? AND status = 'confirmed'
           GROUP BY product
           ORDER BY total_qty DESC""",
        (community_id,),
    ).fetchall()
    community = conn.execute(
        "SELECT name, households FROM communities WHERE id = ?", (community_id,)
    ).fetchone()
    products = [
        {
            "product": row["product"],
            "total_qty": int(row["total_qty"] or 0),
            "requests": int(row["requests"] or 0),
            "households": int(row["households"] or 0),
            "unit": "can" if row["product"] == "water can" else "unit",
        }
        for row in rows
    ]
    return {
        "community_id": community_id,
        "community": community["name"] if community else "Green Residency",
        "households": int(community["households"]) if community else 0,
        "products": products,
        "total_qty": sum(item["total_qty"] for item in products),
    }


def list_demand(community_id: str = COMMUNITY_ID, limit: int = 20) -> list[dict[str, Any]]:
    """The resident's request history, newest first."""
    conn = connect()
    rows = conn.execute(
        """SELECT d.id, d.product, d.qty, d.frequency, d.delivery_day, d.language,
                  d.status, d.created_at, r.flat_number
           FROM demand_requests d
           LEFT JOIN residents r ON r.id = d.resident_id
           WHERE d.community_id = ?
           ORDER BY d.created_at DESC, d.id DESC
           LIMIT ?""",
        (community_id, max(1, min(limit, 200))),
    ).fetchall()
    return [dict(row) for row in rows]
