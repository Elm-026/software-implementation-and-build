"""SQLite 仓储，保持 SQL 细节集中在基础设施层。"""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from typing import Any

from ..domain.enums import ProductStatus, ReservationStatus, Role, TransactionStatus
from ..domain.models import (
    AuditLog,
    IdempotencyRecord,
    Product,
    ProductVersion,
    Reservation,
    ReviewTask,
    Transaction,
    User,
)
from .database import Database


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


class UserRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, user: User) -> None:
        self.database.execute(
            "INSERT INTO users(user_id,email,password_hash,role,display_name,phone,is_active,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (user.user_id, user.email, user.password_hash, user.role.value, user.display_name, user.phone, int(user.is_active), user.created_at),
        )

    def get(self, user_id: str) -> User | None:
        row = self.database.fetch_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return self._from_row(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        row = self.database.fetch_one("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,))
        return self._from_row(row) if row else None

    def list_by_role(self, role: Role) -> list[User]:
        rows = self.database.fetch_all("SELECT * FROM users WHERE role = ? ORDER BY created_at", (role.value,))
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> User:
        return User(row["user_id"], row["email"], row["password_hash"], Role(row["role"]), row["display_name"], row["phone"], bool(row["is_active"]), row["created_at"])


class ProductRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, product: Product) -> None:
        self.database.execute(
            "INSERT INTO products(product_id,seller_id,title,description,category,price,condition,city,contact,image_urls,status,version,created_at,updated_at,published_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (product.product_id, product.seller_id, product.title, product.description, product.category, str(product.price), product.condition, product.city, product.contact, _json(product.image_urls), product.status.value, product.version, product.created_at, product.updated_at, product.published_at),
        )

    def get(self, product_id: str) -> Product | None:
        row = self.database.fetch_one("SELECT * FROM products WHERE product_id = ?", (product_id,))
        return self._from_row(row) if row else None

    def list_visible(self, keyword: str = "", category: str = "", minimum: Decimal | None = None, maximum: Decimal | None = None, page: int = 1, page_size: int = 20, order_by: str = "updated_at") -> list[Product]:
        clauses = ["status IN ('PUBLISHED', 'RESERVED', 'IN_TRANSACTION')"]
        parameters: list[Any] = []
        if keyword:
            clauses.append("(title LIKE ? OR description LIKE ?)")
            pattern = f"%{keyword}%"
            parameters.extend([pattern, pattern])
        if category:
            clauses.append("category = ?")
            parameters.append(category)
        if minimum is not None:
            clauses.append("price >= ?")
            parameters.append(str(minimum))
        if maximum is not None:
            clauses.append("price <= ?")
            parameters.append(str(maximum))
        safe_order = "price" if order_by == "price" else "updated_at"
        safe_page = max(1, page)
        offset = (safe_page - 1) * max(1, page_size)
        parameters.extend([max(1, page_size), offset])
        sql = f"SELECT * FROM products WHERE {' AND '.join(clauses)} ORDER BY {safe_order}, product_id LIMIT ? OFFSET ?"
        return [self._from_row(row) for row in self.database.fetch_all(sql, tuple(parameters))]

    def update_fields(self, product_id: str, fields: dict[str, Any], expected_version: int) -> bool:
        allowed = {"title", "description", "category", "price", "condition", "city", "contact", "image_urls", "status", "version", "updated_at", "published_at"}
        clean = {key: value for key, value in fields.items() if key in allowed}
        if not clean:
            return False
        assignments: list[str] = []
        parameters: list[Any] = []
        for key, value in clean.items():
            if key == "image_urls":
                value = _json(value)
            elif isinstance(value, (ProductStatus,)):
                value = value.value
            assignments.append(f"{key} = ?")
            parameters.append(str(value) if key == "price" else value)
        assignments.append("version = version + 1")
        parameters.extend([product_id, expected_version])
        with self.database.transaction(immediate=True) as connection:
            cursor = connection.execute(f"UPDATE products SET {', '.join(assignments)} WHERE product_id = ? AND version = ?", tuple(parameters))
            return cursor.rowcount == 1

    def add_version(self, version: ProductVersion) -> None:
        self.database.execute(
            "INSERT INTO product_versions(version_id,product_id,version_no,snapshot,status,created_at) VALUES(?,?,?,?,?,?)",
            (version.version_id, version.product_id, version.version_no, _json(version.snapshot), version.status.value, version.created_at),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Product:
        return Product(row["product_id"], row["seller_id"], row["title"], row["description"], row["category"], Decimal(str(row["price"])), row["condition"], row["city"], row["contact"], json.loads(row["image_urls"]), ProductStatus(row["status"]), row["version"], row["created_at"], row["updated_at"], row["published_at"])


class ReviewRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, task: ReviewTask) -> None:
        self.database.execute(
            "INSERT INTO review_tasks(task_id,product_id,reviewer_id,decision,reason,status,created_at,reviewed_at) VALUES(?,?,?,?,?,?,?,?)",
            (task.task_id, task.product_id, task.reviewer_id, task.decision, task.reason, task.status, task.created_at, task.reviewed_at),
        )

    def get(self, task_id: str) -> ReviewTask | None:
        row = self.database.fetch_one("SELECT * FROM review_tasks WHERE task_id = ?", (task_id,))
        return self._from_row(row) if row else None

    def get_pending_for_product(self, product_id: str) -> ReviewTask | None:
        row = self.database.fetch_one("SELECT * FROM review_tasks WHERE product_id = ? AND status = 'PENDING'", (product_id,))
        return self._from_row(row) if row else None

    def list_pending(self) -> list[ReviewTask]:
        return [self._from_row(row) for row in self.database.fetch_all("SELECT * FROM review_tasks WHERE status = 'PENDING' ORDER BY created_at")]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ReviewTask:
        return ReviewTask(row["task_id"], row["product_id"], row["reviewer_id"], row["decision"], row["reason"], row["status"], row["created_at"], row["reviewed_at"])


class ReservationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, reservation: Reservation, connection: sqlite3.Connection | None = None) -> None:
        sql = "INSERT INTO reservations(reservation_id,product_id,buyer_id,status,created_at,updated_at,version,idempotency_key) VALUES(?,?,?,?,?,?,?,?)"
        values = (reservation.reservation_id, reservation.product_id, reservation.buyer_id, reservation.status.value, reservation.created_at, reservation.updated_at, reservation.version, reservation.idempotency_key)
        if connection is None:
            self.database.execute(sql, values)
        else:
            connection.execute(sql, values)

    def get(self, reservation_id: str) -> Reservation | None:
        row = self.database.fetch_one("SELECT * FROM reservations WHERE reservation_id = ?", (reservation_id,))
        return self._from_row(row) if row else None

    def get_active_for_product(self, product_id: str, connection: sqlite3.Connection | None = None) -> Reservation | None:
        if connection is None:
            row = self.database.fetch_one("SELECT * FROM reservations WHERE product_id = ? AND status = 'ACTIVE'", (product_id,))
        else:
            row = connection.execute("SELECT * FROM reservations WHERE product_id = ? AND status = 'ACTIVE'", (product_id,)).fetchone()
        return self._from_row(row) if row else None

    def list_for_buyer(self, buyer_id: str) -> list[Reservation]:
        return [self._from_row(row) for row in self.database.fetch_all("SELECT * FROM reservations WHERE buyer_id = ? ORDER BY created_at DESC", (buyer_id,))]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Reservation:
        return Reservation(row["reservation_id"], row["product_id"], row["buyer_id"], ReservationStatus(row["status"]), row["created_at"], row["updated_at"], row["version"], row["idempotency_key"])


class TransactionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, transaction: Transaction, connection: sqlite3.Connection | None = None) -> None:
        sql = "INSERT INTO transactions(transaction_id,reservation_id,product_id,buyer_id,seller_id,status,created_at,completed_at,version) VALUES(?,?,?,?,?,?,?,?,?)"
        values = (transaction.transaction_id, transaction.reservation_id, transaction.product_id, transaction.buyer_id, transaction.seller_id, transaction.status.value, transaction.created_at, transaction.completed_at, transaction.version)
        if connection is None:
            self.database.execute(sql, values)
        else:
            connection.execute(sql, values)

    def get(self, transaction_id: str) -> Transaction | None:
        row = self.database.fetch_one("SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,))
        return self._from_row(row) if row else None

    def get_by_reservation(self, reservation_id: str) -> Transaction | None:
        row = self.database.fetch_one("SELECT * FROM transactions WHERE reservation_id = ?", (reservation_id,))
        return self._from_row(row) if row else None

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Transaction:
        return Transaction(row["transaction_id"], row["reservation_id"], row["product_id"], row["buyer_id"], row["seller_id"], TransactionStatus(row["status"]), row["created_at"], row["completed_at"], row["version"])


class AuditRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, log: AuditLog, connection: sqlite3.Connection | None = None) -> None:
        sql = "INSERT INTO audit_logs(log_id,actor_id,role,action,object_type,object_id,before_state,after_state,result,request_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)"
        values = (log.log_id, log.actor_id, log.role.value if log.role else None, log.action, log.object_type, log.object_id, _json(log.before_state) if log.before_state else None, _json(log.after_state) if log.after_state else None, log.result, log.request_id, log.created_at)
        if connection is None:
            self.database.execute(sql, values)
        else:
            connection.execute(sql, values)

    def search(self, actor_id: str | None = None, role: Role | None = None, object_id: str | None = None, limit: int = 100) -> list[AuditLog]:
        clauses = ["1 = 1"]
        values: list[Any] = []
        if actor_id:
            clauses.append("actor_id = ?")
            values.append(actor_id)
        if role:
            clauses.append("role = ?")
            values.append(role.value)
        if object_id:
            clauses.append("object_id = ?")
            values.append(object_id)
        values.append(max(1, limit))
        rows = self.database.fetch_all(f"SELECT * FROM audit_logs WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT ?", tuple(values))
        return [AuditLog(row["log_id"], row["actor_id"], Role(row["role"]) if row["role"] else None, row["action"], row["object_type"], row["object_id"], json.loads(row["before_state"]) if row["before_state"] else None, json.loads(row["after_state"]) if row["after_state"] else None, row["result"], row["request_id"], row["created_at"]) for row in rows]


class IdempotencyRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, actor_id: str, operation: str, key: str, connection: sqlite3.Connection | None = None) -> IdempotencyRecord | None:
        sql = "SELECT * FROM idempotency_records WHERE actor_id = ? AND operation = ? AND key = ?"
        values = (actor_id, operation, key)
        row = (connection.execute(sql, values).fetchone() if connection is not None else self.database.fetch_one(sql, values))
        return IdempotencyRecord(row["key"], row["actor_id"], row["operation"], row["request_hash"], row["result_ref"], row["result_status"], row["response_json"], row["created_at"]) if row else None

    def create(self, record: IdempotencyRecord, connection: sqlite3.Connection | None = None) -> None:
        sql = "INSERT INTO idempotency_records(actor_id,operation,key,request_hash,result_ref,result_status,response_json,created_at) VALUES(?,?,?,?,?,?,?,?)"
        values = (record.actor_id, record.operation, record.key, record.request_hash, record.result_ref, record.result_status, record.response_json, record.created_at)
        if connection is None:
            self.database.execute(sql, values)
        else:
            connection.execute(sql, values)

