"""
Lightweight historical storage for the ISFCR Mining Console.

Uses SQLite (stdlib, zero extra deps) so the dashboard's history/analytics
pages have real trend data to chart, and so a detected block stays recorded
even across backend restarts.

Two tables:
  snapshots    -- one row per periodic sample (hashrate, temps, power, shares...)
  blocks_found -- one row every time we detect our address found a block
"""
import sqlite3
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).resolve().parent.parent.parent / "logs" / "history.sqlite3"
DB_PATH.parent.mkdir(exist_ok=True)

_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock, _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                coin TEXT,
                hashrate_1m REAL,
                accepted_shares INTEGER,
                rejected_shares INTEGER,
                pool_connected INTEGER,
                gpu_temp REAL,
                gpu_hotspot_temp REAL,
                gpu_power_draw REAL,
                cpu_temp REAL,
                cpu_usage_percent REAL,
                price_usd REAL,
                revenue_usd_per_day REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS blocks_found (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                coin TEXT,
                pool_name TEXT,
                block_height INTEGER,
                reward_estimate REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_blocks_ts ON blocks_found(ts)")
        conn.commit()


def insert_snapshot(coin: str, hashrate_1m: float, accepted: int, rejected: int,
                     pool_connected: bool, gpu_temp: float, gpu_hotspot_temp: float,
                     gpu_power_draw: float, cpu_temp: float, cpu_usage_percent: float,
                     price_usd: float | None, revenue_usd_per_day: float | None):
    with _lock, _connect() as conn:
        conn.execute(
            """INSERT INTO snapshots
               (ts, coin, hashrate_1m, accepted_shares, rejected_shares, pool_connected,
                gpu_temp, gpu_hotspot_temp, gpu_power_draw, cpu_temp, cpu_usage_percent,
                price_usd, revenue_usd_per_day)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (int(time.time()), coin, hashrate_1m, accepted, rejected, int(pool_connected),
             gpu_temp, gpu_hotspot_temp, gpu_power_draw, cpu_temp, cpu_usage_percent,
             price_usd, revenue_usd_per_day),
        )
        conn.commit()


def get_snapshots_since(hours: float = 24.0, limit: int = 2000) -> list[dict]:
    cutoff = int(time.time() - hours * 3600)
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM snapshots WHERE ts >= ? ORDER BY ts ASC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def insert_block_found(coin: str, pool_name: str, block_height: int | None, reward_estimate: float | None):
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO blocks_found (ts, coin, pool_name, block_height, reward_estimate) VALUES (?,?,?,?,?)",
            (int(time.time()), coin, pool_name, block_height, reward_estimate),
        )
        conn.commit()


def get_blocks_found(limit: int = 50) -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM blocks_found ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def prune_old_snapshots(days: int = 30):
    """Keep the DB from growing unbounded; called occasionally by the periodic task."""
    cutoff = int(time.time() - days * 86400)
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM snapshots WHERE ts < ?", (cutoff,))
        conn.commit()


init_db()
