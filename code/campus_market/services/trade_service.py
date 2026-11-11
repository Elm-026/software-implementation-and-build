"""Reservation and transaction state machine with concurrency protection."""

from __future__ import annotations

import json
import sqlite3

from ..domain import ProductStatus, Reservation, ReservationStatus, Role, Transaction, TransactionStatus
from ..utils.idempotency import request_hash
from .audit_service import AuditService
from .common import BaseService, ConflictError, IdempotencyConflict, NotFoundError, PermissionDenied, ValidationError


class TradeService(BaseService):
    """Implements the UML reservation and offline-delivery workflow.

    ``BEGIN IMMEDIATE`` serializes competing writers.  The product update also
    includes ``status = PUBLISHED`` so an old page cannot reserve a product
    that has already moved to another state.
    """

    def __init__(self, database) -> None:
        super().__init__(database)
        self.audit = AuditService(self.context)

    def reserve(self, buyer_id: str, product_id: str, idempotency_key: str) -> Reservation:
        buyer = self.require_role(buyer_id, Role.BUYER)
        key = self.require_key(idempotency_key)
        payload = {"product_id": product_id}
        existing = self._existing(buyer_id, "reserve", key, payload)
        if existing:
            reservation = self.context.reservations.get(existing)
            if reservation is None:
                raise ConflictError("幂等记录指向了不存在的预约")
            return reservation
        reservation = Reservation(reservation_id=self.new_id(), product_id=product_id, buyer_id=buyer_id, idempotency_key=key, created_at=self.now(), updated_at=self.now())
        try:
            with self.database.transaction(immediate=True) as connection:
                product = connection.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
                if product is None:
                    raise NotFoundError("商品不存在")
                if product["seller_id"] == buyer_id:
                    raise PermissionDenied("不能预约自己的商品")
                if product["status"] != ProductStatus.PUBLISHED.value:
                    raise ConflictError("商品已被预约或不可见")
                updated = connection.execute("UPDATE products SET status = ?, version = version + 1, updated_at = ? WHERE product_id = ? AND status = 'PUBLISHED' AND version = ?", (ProductStatus.RESERVED.value, self.now(), product_id, product["version"]))
                if updated.rowcount != 1:
                    raise ConflictError("商品已被其他买家预约")
                self.context.reservations.create(reservation, connection=connection)
                self._save_idempotency(buyer_id, "reserve", key, payload, reservation.reservation_id, connection=connection)
                self.audit.record(actor_id=buyer_id, role=buyer.role, action="RESERVE", object_type="Reservation", object_id=reservation.reservation_id, before_state={"product_status": product["status"]}, after_state={"product_status": ProductStatus.RESERVED.value, "reservation_status": ReservationStatus.ACTIVE.value}, result="SUCCESS", connection=connection)
        except sqlite3.IntegrityError as exc:
            if "ux_active_reservation" in str(exc) or "UNIQUE" in str(exc).upper():
                raise ConflictError("商品已被其他买家预约") from exc
            raise
        return reservation

    def cancel(self, buyer_id: str, reservation_id: str, expected_version: int, idempotency_key: str) -> Reservation:
        buyer = self.require_role(buyer_id, Role.BUYER)
        key = self.require_key(idempotency_key)
        payload = {"reservation_id": reservation_id, "expected_version": expected_version}
        existing = self._existing(buyer_id, "cancel_reservation", key, payload)
        if existing:
            result = self.context.reservations.get(existing)
            if result:
                return result
        with self.database.transaction(immediate=True) as connection:
            row = connection.execute("SELECT * FROM reservations WHERE reservation_id = ?", (reservation_id,)).fetchone()
            if row is None:
                raise NotFoundError("预约不存在")
            if row["buyer_id"] != buyer_id:
                raise PermissionDenied("不能取消其他买家的预约")
            if row["status"] != ReservationStatus.ACTIVE.value:
                raise ConflictError("预约已确认或已取消")
            if row["version"] != expected_version:
                raise ConflictError("预约版本已更新，请刷新后重试")
            product = connection.execute("SELECT * FROM products WHERE product_id = ?", (row["product_id"],)).fetchone()
            if product is None:
                raise NotFoundError("商品不存在")
            updated = connection.execute("UPDATE reservations SET status = ?, version = version + 1, updated_at = ? WHERE reservation_id = ? AND status = 'ACTIVE' AND version = ?", (ReservationStatus.CANCELLED.value, self.now(), reservation_id, expected_version))
            if updated.rowcount != 1:
                raise ConflictError("预约状态已经发生变化")
            connection.execute("UPDATE products SET status = 'PUBLISHED', version = version + 1, updated_at = ? WHERE product_id = ? AND status = 'RESERVED'", (self.now(), row["product_id"]))
            self._save_idempotency(buyer_id, "cancel_reservation", key, payload, reservation_id, connection=connection)
            self.audit.record(actor_id=buyer_id, role=buyer.role, action="CANCEL_RESERVATION", object_type="Reservation", object_id=reservation_id, before_state={"status": row["status"]}, after_state={"status": ReservationStatus.CANCELLED.value}, result="SUCCESS", connection=connection)
        result = self.context.reservations.get(reservation_id)
        if result is None:
            raise NotFoundError("预约不存在")
        return result

    def confirm_reservation(self, seller_id: str, reservation_id: str, expected_version: int, idempotency_key: str) -> Transaction:
        seller = self.require_role(seller_id, Role.SELLER)
        key = self.require_key(idempotency_key)
        payload = {"reservation_id": reservation_id, "expected_version": expected_version}
        existing = self._existing(seller_id, "confirm_reservation", key, payload)
        if existing:
            transaction = self.context.transactions.get(existing)
            if transaction:
                return transaction
        transaction_id = self.new_id()
        with self.database.transaction(immediate=True) as connection:
            row = connection.execute("SELECT r.*, p.seller_id, p.status AS product_status FROM reservations r JOIN products p ON p.product_id = r.product_id WHERE r.reservation_id = ?", (reservation_id,)).fetchone()
            if row is None:
                raise NotFoundError("预约不存在")
            if row["seller_id"] != seller_id:
                raise PermissionDenied("不能确认其他卖家的预约")
            if row["status"] != ReservationStatus.ACTIVE.value or row["product_status"] != ProductStatus.RESERVED.value:
                raise ConflictError("预约已取消或商品状态不允许确认")
            if row["version"] != expected_version:
                raise ConflictError("预约版本已更新，请刷新后重试")
            now = self.now()
            updated = connection.execute("UPDATE reservations SET status = 'CONFIRMED', version = version + 1, updated_at = ? WHERE reservation_id = ? AND status = 'ACTIVE' AND version = ?", (now, reservation_id, expected_version))
            if updated.rowcount != 1:
                raise ConflictError("预约状态已经发生变化")
            connection.execute("UPDATE products SET status = 'IN_TRANSACTION', version = version + 1, updated_at = ? WHERE product_id = ? AND status = 'RESERVED'", (now, row["product_id"]))
            transaction = Transaction(transaction_id=transaction_id, reservation_id=reservation_id, product_id=row["product_id"], buyer_id=row["buyer_id"], seller_id=seller_id, created_at=now)
            self.context.transactions.create(transaction, connection=connection)
            self._save_idempotency(seller_id, "confirm_reservation", key, payload, transaction_id, connection=connection)
            self.audit.record(actor_id=seller_id, role=seller.role, action="CONFIRM_RESERVATION", object_type="Transaction", object_id=transaction_id, before_state={"reservation_status": row["status"]}, after_state={"reservation_status": ReservationStatus.CONFIRMED.value, "transaction_status": TransactionStatus.IN_PROGRESS.value}, result="SUCCESS", connection=connection)
        return transaction

    def confirm_receipt(self, buyer_id: str, transaction_id: str, expected_version: int) -> Transaction:
        buyer = self.require_role(buyer_id, Role.BUYER)
        with self.database.transaction(immediate=True) as connection:
            row = connection.execute("SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)).fetchone()
            if row is None:
                raise NotFoundError("交易不存在")
            if row["buyer_id"] != buyer_id:
                raise PermissionDenied("不能确认其他买家的交易")
            if row["status"] != TransactionStatus.IN_PROGRESS.value:
                raise ConflictError("交易已经完成")
            if row["version"] != expected_version:
                raise ConflictError("交易版本已更新，请刷新后重试")
            now = self.now()
            updated = connection.execute("UPDATE transactions SET status = 'COMPLETED', completed_at = ?, version = version + 1 WHERE transaction_id = ? AND status = 'IN_PROGRESS' AND version = ?", (now, transaction_id, expected_version))
            if updated.rowcount != 1:
                raise ConflictError("交易状态已经发生变化")
            connection.execute("UPDATE reservations SET status = 'COMPLETED', updated_at = ?, version = version + 1 WHERE reservation_id = ? AND status = 'CONFIRMED'", (now, row["reservation_id"]))
            connection.execute("UPDATE products SET status = 'COMPLETED', version = version + 1, updated_at = ? WHERE product_id = ? AND status = 'IN_TRANSACTION'", (now, row["product_id"]))
            self.audit.record(actor_id=buyer_id, role=buyer.role, action="CONFIRM_RECEIPT", object_type="Transaction", object_id=transaction_id, before_state={"status": row["status"]}, after_state={"status": TransactionStatus.COMPLETED.value}, result="SUCCESS", connection=connection)
        result = self.context.transactions.get(transaction_id)
        if result is None:
            raise NotFoundError("交易不存在")
        return result

    def reservations_for_buyer(self, buyer_id: str) -> list[Reservation]:
        self.require_role(buyer_id, Role.BUYER)
        return self.context.reservations.list_for_buyer(buyer_id)

    def _existing(self, actor_id: str, operation: str, key: str, payload: dict) -> str | None:
        record = self.context.idempotency.get(actor_id, operation, key)
        if record is None:
            return None
        if record.request_hash != request_hash(payload):
            raise IdempotencyConflict("相同幂等键不能用于不同请求")
        return record.result_ref

    def _save_idempotency(self, actor_id: str, operation: str, key: str, payload: dict, result_ref: str, connection=None) -> None:
        from ..domain import IdempotencyRecord

        self.context.idempotency.create(IdempotencyRecord(key=key, actor_id=actor_id, operation=operation, request_hash=request_hash(payload), result_ref=result_ref, result_status="SUCCESS", response_json=json.dumps({"result_ref": result_ref}, ensure_ascii=False), created_at=self.now()), connection=connection)
