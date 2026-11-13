"""Shared service-layer primitives.

The service layer owns authorization and state-transition rules.  Repositories
remain deliberately small, so this module supplies common error types and a
single dependency container used by each business service.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from ..domain import Role, User
from ..infra import (
    AuditRepository,
    Database,
    IdempotencyRepository,
    ProductRepository,
    ReservationRepository,
    ReviewRepository,
    TransactionRepository,
    UserRepository,
)


class ServiceError(Exception):
    """Base class for expected business errors."""


class ValidationError(ServiceError, ValueError):
    """Input does not satisfy a business rule."""


class AuthenticationError(ServiceError):
    """Credentials or session state are invalid."""


class PermissionDenied(ServiceError):
    """The actor does not have permission for the requested operation."""


class NotFoundError(ServiceError):
    """A referenced business object does not exist."""


class ConflictError(ServiceError):
    """The requested state transition conflicts with current state."""


class IdempotencyConflict(ServiceError):
    """An idempotency key was reused with different request parameters."""


@dataclass(slots=True)
class ServiceContext:
    """Database and repositories shared by all services."""

    database: Database
    users: UserRepository
    products: ProductRepository
    reviews: ReviewRepository
    reservations: ReservationRepository
    transactions: TransactionRepository
    audits: AuditRepository
    idempotency: IdempotencyRepository

    @classmethod
    def create(cls, database: Database) -> "ServiceContext":
        return cls(
            database=database,
            users=UserRepository(database),
            products=ProductRepository(database),
            reviews=ReviewRepository(database),
            reservations=ReservationRepository(database),
            transactions=TransactionRepository(database),
            audits=AuditRepository(database),
            idempotency=IdempotencyRepository(database),
        )


def service_context(value: Database | ServiceContext) -> ServiceContext:
    return value if isinstance(value, ServiceContext) else ServiceContext.create(value)


class BaseService:
    """Common helpers for service implementations."""

    def __init__(self, database: Database | ServiceContext) -> None:
        self.context = service_context(database)
        self.database = self.context.database

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def user(self, user_id: str) -> User:
        result = self.context.users.get(user_id)
        if result is None or not result.is_active:
            raise NotFoundError("用户不存在或已停用")
        return result

    def require_role(self, user_id: str, *roles: Role) -> User:
        actor = self.user(user_id)
        requested = set(roles)
        is_trade_capability = bool(requested & {Role.BUYER, Role.SELLER}) and Role.ADMIN not in requested
        allowed = actor.role in requested or (is_trade_capability and actor.role in {Role.BUYER, Role.SELLER, Role.ADMIN})
        if not allowed:
            names = ", ".join(role.value for role in roles)
            raise PermissionDenied(f"需要角色 {names}")
        return actor

    @staticmethod
    def encode(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def decode(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            result = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return result if isinstance(result, dict) else {}

    @staticmethod
    def require_key(key: str | None) -> str:
        normalized = (key or "").strip()
        if not normalized:
            raise ValidationError("写操作必须提供幂等键")
        if len(normalized) > 128:
            raise ValidationError("幂等键长度不能超过128个字符")
        return normalized

    @staticmethod
    def ensure_any_role(actor: User, roles: Iterable[Role]) -> User:
        allowed = tuple(roles)
        if actor.role not in allowed:
            raise PermissionDenied("当前角色无权执行该操作")
        return actor
