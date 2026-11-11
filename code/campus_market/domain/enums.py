"""系统中稳定的角色和业务状态。"""

from enum import StrEnum


class Role(StrEnum):
    BUYER = "BUYER"
    SELLER = "SELLER"
    ADMIN = "ADMIN"


class ProductStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    PUBLISHED = "PUBLISHED"
    RESERVED = "RESERVED"
    IN_TRANSACTION = "IN_TRANSACTION"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    UNLISTED = "UNLISTED"
    VIOLATION = "VIOLATION"


class ReservationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"


class TransactionStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class ReviewDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"

