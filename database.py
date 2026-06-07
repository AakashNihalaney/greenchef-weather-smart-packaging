"""
database.py — SQLite database layer for Weather-Smart Fulfillment
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "fulfillment.db"


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id        TEXT UNIQUE NOT NULL,
            customer_name   TEXT NOT NULL,
            delivery_address TEXT NOT NULL,
            city            TEXT NOT NULL,
            state           TEXT NOT NULL,
            zip_code        TEXT NOT NULL,
            delivery_date   TEXT NOT NULL,
            items_json      TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS manifests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id        TEXT NOT NULL,
            manifest_json   TEXT NOT NULL,
            weather_json    TEXT NOT NULL,
            theoretical_weight_kg REAL,
            actual_weight_kg REAL,
            weight_ok       INTEGER DEFAULT 1,
            packed_at       TEXT DEFAULT (datetime('now')),
            packed_by       TEXT DEFAULT 'worker',
            FOREIGN KEY(order_id) REFERENCES orders(order_id)
        );

        CREATE TABLE IF NOT EXISTS system_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            level           TEXT NOT NULL,
            module          TEXT NOT NULL,
            message         TEXT NOT NULL,
            logged_at       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS p2l_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id        TEXT NOT NULL,
            bin_id          TEXT NOT NULL,
            item_name       TEXT NOT NULL,
            flash_count     INTEGER NOT NULL,
            triggered_at    TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# ── Orders ──────────────────────────────────────────────────────────────────

def upsert_order(order: dict):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO orders (order_id, customer_name, delivery_address, city, state,
                            zip_code, delivery_date, items_json)
        VALUES (:order_id, :customer_name, :delivery_address, :city, :state,
                :zip_code, :delivery_date, :items_json)
        ON CONFLICT(order_id) DO UPDATE SET
            customer_name    = excluded.customer_name,
            delivery_address = excluded.delivery_address,
            city             = excluded.city,
            state            = excluded.state,
            zip_code         = excluded.zip_code,
            delivery_date    = excluded.delivery_date,
            items_json       = excluded.items_json,
            updated_at       = datetime('now')
    """, {**order, "items_json": json.dumps(order.get("items", []))})
    conn.commit()
    conn.close()


def get_all_orders():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["items"] = json.loads(d["items_json"])
        result.append(d)
    return result


def get_order(order_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM orders WHERE order_id = ?", (order_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["items"] = json.loads(d["items_json"])
    return d


def update_order_status(order_id: str, status: str):
    conn = get_conn()
    conn.execute(
        "UPDATE orders SET status = ?, updated_at = datetime('now') WHERE order_id = ?",
        (status, order_id)
    )
    conn.commit()
    conn.close()


def add_manual_order(order_data: dict):
    """Insert a manually entered order from the UI."""
    upsert_order(order_data)


# ── Manifests ───────────────────────────────────────────────────────────────

def save_manifest(order_id: str, manifest: dict, weather: dict,
                  theoretical_kg: float, actual_kg: float):
    weight_ok = abs(theoretical_kg - actual_kg) / max(theoretical_kg, 0.001) <= 0.02
    conn = get_conn()
    conn.execute("""
        INSERT INTO manifests (order_id, manifest_json, weather_json,
                               theoretical_weight_kg, actual_weight_kg, weight_ok)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (order_id, json.dumps(manifest), json.dumps(weather),
          theoretical_kg, actual_kg, int(weight_ok)))
    conn.commit()
    conn.close()
    return weight_ok


def get_manifests_for_order(order_id: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM manifests WHERE order_id = ? ORDER BY packed_at DESC",
        (order_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["manifest"] = json.loads(d["manifest_json"])
        d["weather"]  = json.loads(d["weather_json"])
        result.append(d)
    return result


# ── Logs ────────────────────────────────────────────────────────────────────

def log(level: str, module: str, message: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO system_logs (level, module, message) VALUES (?, ?, ?)",
        (level.upper(), module, message)
    )
    conn.commit()
    conn.close()
    print(f"[{level.upper()}] [{module}] {message}")


def get_recent_logs(n: int = 50):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM system_logs ORDER BY logged_at DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── P2L Events ───────────────────────────────────────────────────────────────

def log_p2l_event(order_id: str, bin_id: str, item_name: str, flash_count: int):
    conn = get_conn()
    conn.execute("""
        INSERT INTO p2l_events (order_id, bin_id, item_name, flash_count)
        VALUES (?, ?, ?, ?)
    """, (order_id, bin_id, item_name, flash_count))
    conn.commit()
    conn.close()


def get_p2l_events(order_id: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM p2l_events WHERE order_id = ? ORDER BY triggered_at",
        (order_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
