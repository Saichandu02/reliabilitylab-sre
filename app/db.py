"""SQLite persistence for orders.

A connection is opened per operation so the process never holds a write
lock across requests and a second app instance (e.g. after a restart)
can open the same file immediately. In the Docker Compose deployment the
same repository functions are the seam where the PostgreSQL DSN lives
(see docker-compose.yml / docs/decisions.md); the local, Docker-free
path uses SQLite so persistence-after-restart can be exercised here.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class OrderStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    item TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price_minor INTEGER NOT NULL,
                    total_minor INTEGER NOT NULL,
                    customer_ref TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def ping(self) -> bool:
        with self._conn() as conn:
            conn.execute("SELECT 1").fetchone()
        return True

    def create(self, order: dict) -> dict:
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT INTO orders (id,item,quantity,unit_price_minor,"
                "total_minor,customer_ref,status,created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    order["id"], order["item"], order["quantity"],
                    order["unit_price_minor"], order["total_minor"],
                    order["customer_ref"], order["status"], order["created_at"],
                ),
            )
        return order

    def get(self, order_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE id=?", (order_id,)
            ).fetchone()
        return dict(row) if row else None

    def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM orders ORDER BY created_at, id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()
        return int(row["c"])
