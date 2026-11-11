"""SQLite 数据库连接、迁移和事务边界。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('BUYER', 'SELLER', 'ADMIN')),
    display_name TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    seller_id TEXT NOT NULL REFERENCES users(user_id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    price NUMERIC NOT NULL CHECK (price >= 0),
    condition TEXT NOT NULL,
    city TEXT NOT NULL,
    contact TEXT NOT NULL DEFAULT '',
    image_urls TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    published_at TEXT
);

CREATE TABLE IF NOT EXISTS product_versions (
    version_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(product_id),
    version_no INTEGER NOT NULL,
    snapshot TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(product_id, version_no)
);

CREATE TABLE IF NOT EXISTS review_tasks (
    task_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(product_id),
    reviewer_id TEXT REFERENCES users(user_id),
    decision TEXT NOT NULL DEFAULT 'PENDING',
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS reservations (
    reservation_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(product_id),
    buyer_id TEXT NOT NULL REFERENCES users(user_id),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    idempotency_key TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    reservation_id TEXT NOT NULL UNIQUE REFERENCES reservations(reservation_id),
    product_id TEXT NOT NULL REFERENCES products(product_id),
    buyer_id TEXT NOT NULL REFERENCES users(user_id),
    seller_id TEXT NOT NULL REFERENCES users(user_id),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    log_id TEXT PRIMARY KEY,
    actor_id TEXT REFERENCES users(user_id),
    role TEXT,
    action TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT,
    before_state TEXT,
    after_state TEXT,
    result TEXT NOT NULL,
    request_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    actor_id TEXT NOT NULL REFERENCES users(user_id),
    operation TEXT NOT NULL,
    key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_ref TEXT,
    result_status TEXT NOT NULL,
    response_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    PRIMARY KEY(actor_id, operation, key)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_active_reservation_per_product
    ON reservations(product_id) WHERE status = 'ACTIVE';
CREATE UNIQUE INDEX IF NOT EXISTS ux_pending_review_per_product
    ON review_tasks(product_id) WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS ix_products_search
    ON products(status, category, price, updated_at);
CREATE INDEX IF NOT EXISTS ix_audit_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS ix_audit_actor ON audit_logs(actor_id, created_at);
CREATE INDEX IF NOT EXISTS ix_reservations_buyer ON reservations(buyer_id, created_at);
"""


class Database:
    """管理 SQLite 文件并提供显式事务上下文。"""

    def __init__(self, path: str | Path = "campus_market.sqlite3") -> None:
        self.path = Path(path)
        self._memory_uri: str | None = None
        self._memory_anchor: sqlite3.Connection | None = None
        if str(self.path) == ":memory:":
            self._memory_uri = f"file:campus_market_{id(self)}?mode=memory&cache=shared"
            self._memory_anchor = sqlite3.connect(self._memory_uri, uri=True, check_same_thread=False)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        target = self._memory_uri or str(self.path)
        connection = sqlite3.connect(
            target,
            uri=self._memory_uri is not None,
            timeout=10,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        if str(self.path) != ":memory:":
            connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def close(self) -> None:
        """释放共享内存数据库的锚点连接。文件数据库无需额外清理。"""
        if self._memory_anchor is not None:
            self._memory_anchor.close()
            self._memory_anchor = None

    def initialize(self) -> None:
        connection = self.connect()
        try:
            connection.executescript(SCHEMA)
        finally:
            connection.close()

    @contextmanager
    def transaction(self, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def execute(self, sql: str, parameters: tuple = ()) -> int:
        with self.transaction(immediate=True) as connection:
            cursor = connection.execute(sql, parameters)
            return cursor.rowcount

    def fetch_one(self, sql: str, parameters: tuple = ()) -> sqlite3.Row | None:
        connection = self.connect()
        try:
            return connection.execute(sql, parameters).fetchone()
        finally:
            connection.close()

    def fetch_all(self, sql: str, parameters: tuple = ()) -> list[sqlite3.Row]:
        connection = self.connect()
        try:
            return list(connection.execute(sql, parameters).fetchall())
        finally:
            connection.close()

