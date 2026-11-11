"""与 UML 对应的不可变领域数据对象。

服务层负责状态迁移和权限判断，模型只承载已经校验过的数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .enums import ProductStatus, ReservationStatus, Role, TransactionStatus


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class User:
    user_id: str
    email: str
    password_hash: str
    role: Role
    display_name: str = ""
    phone: str = ""
    is_active: bool = True
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class Product:
    product_id: str
    seller_id: str
    title: str
    description: str
    category: str
    price: Decimal
    condition: str
    city: str
    contact: str = ""
    image_urls: list[str] = field(default_factory=list)
    status: ProductStatus = ProductStatus.DRAFT
    version: int = 1
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    published_at: str | None = None


@dataclass(slots=True)
class ProductVersion:
    version_id: str
    product_id: str
    version_no: int
    snapshot: dict[str, Any]
    status: ProductStatus
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ReviewTask:
    task_id: str
    product_id: str
    reviewer_id: str | None = None
    decision: str = "PENDING"
    reason: str = ""
    status: str = "PENDING"
    created_at: str = field(default_factory=utc_now)
    reviewed_at: str | None = None


@dataclass(slots=True)
class Reservation:
    reservation_id: str
    product_id: str
    buyer_id: str
    status: ReservationStatus = ReservationStatus.ACTIVE
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    version: int = 1
    idempotency_key: str = ""


@dataclass(slots=True)
class Transaction:
    transaction_id: str
    reservation_id: str
    product_id: str
    buyer_id: str
    seller_id: str
    status: TransactionStatus = TransactionStatus.IN_PROGRESS
    created_at: str = field(default_factory=utc_now)
    completed_at: str | None = None
    version: int = 1


@dataclass(slots=True)
class AuditLog:
    log_id: str
    actor_id: str | None
    role: Role | None
    action: str
    object_type: str
    object_id: str | None
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    result: str
    request_id: str
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class IdempotencyRecord:
    key: str
    actor_id: str
    operation: str
    request_hash: str
    result_ref: str | None
    result_status: str
    response_json: str = "{}"
    created_at: str = field(default_factory=utc_now)
