"""Administrator review workflow for products awaiting publication."""

from __future__ import annotations

from ..domain import ProductStatus, ReviewTask, Role
from .audit_service import AuditService
from .common import BaseService, ConflictError, NotFoundError, PermissionDenied, ValidationError


class ReviewService(BaseService):
    """Approve or reject a pending product exactly once."""

    def __init__(self, database) -> None:
        super().__init__(database)
        self.audit = AuditService(self.context)

    def pending(self, admin_id: str) -> list[ReviewTask]:
        self.require_role(admin_id, Role.ADMIN)
        return self.context.reviews.list_pending()

    def decide(
        self,
        admin_id: str,
        product_id: str,
        decision: str,
        *,
        reason: str = "",
        expected_version: int | None = None,
    ) -> ReviewTask:
        admin = self.require_role(admin_id, Role.ADMIN)
        normalized = (decision or "").strip().upper()
        if normalized not in {"APPROVE", "REJECT", "PASS", "ACCEPT"}:
            raise ValidationError("审核决定必须是 APPROVE 或 REJECT")
        approved = normalized in {"APPROVE", "PASS", "ACCEPT"}
        if not approved and not (reason or "").strip():
            raise ValidationError("驳回时必须填写原因")
        with self.database.transaction(immediate=True) as connection:
            product = connection.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
            if product is None:
                raise NotFoundError("商品不存在")
            if product["status"] != ProductStatus.PENDING_REVIEW.value:
                raise ConflictError("商品不在待审核状态")
            if expected_version is not None and product["version"] != expected_version:
                raise ConflictError("商品版本已更新，请刷新后重试")
            task = connection.execute("SELECT * FROM review_tasks WHERE product_id = ? AND status = 'PENDING'", (product_id,)).fetchone()
            if task is None:
                raise ConflictError("审核任务不存在或已处理")
            next_status = ProductStatus.PUBLISHED if approved else ProductStatus.REJECTED
            now = self.now()
            connection.execute("UPDATE review_tasks SET reviewer_id = ?, decision = ?, reason = ?, status = 'COMPLETED', reviewed_at = ? WHERE task_id = ? AND status = 'PENDING'", (admin_id, "APPROVE" if approved else "REJECT", (reason or "").strip(), now, task["task_id"]))
            connection.execute("UPDATE products SET status = ?, version = version + 1, updated_at = ?, published_at = CASE WHEN ? = 'PUBLISHED' THEN ? ELSE published_at END WHERE product_id = ? AND version = ?", (next_status.value, now, next_status.value, now, product_id, product["version"]))
            self.audit.record(actor_id=admin_id, role=admin.role, action="REVIEW_APPROVE" if approved else "REVIEW_REJECT", object_type="Product", object_id=product_id, before_state={"status": product["status"], "version": product["version"]}, after_state={"status": next_status.value, "reason": reason}, result="SUCCESS", connection=connection)
            refreshed = connection.execute("SELECT * FROM review_tasks WHERE task_id = ?", (task["task_id"],)).fetchone()
        return self.context.reviews._from_row(refreshed)

    def force_unlist(self, admin_id: str, product_id: str, reason: str, expected_version: int) -> None:
        admin = self.require_role(admin_id, Role.ADMIN)
        if not (reason or "").strip():
            raise ValidationError("违规下架必须填写原因")
        product = self.context.products.get(product_id)
        if product is None:
            raise NotFoundError("商品不存在")
        if product.status in (ProductStatus.COMPLETED, ProductStatus.VIOLATION):
            raise ConflictError("当前商品状态不能再次违规下架")
        changed = self.context.products.update_fields(product_id, {"status": ProductStatus.VIOLATION, "updated_at": self.now()}, expected_version)
        if not changed:
            raise ConflictError("商品版本已更新，请刷新后重试")
        self.audit.record(actor_id=admin_id, role=admin.role, action="FORCE_UNLIST", object_type="Product", object_id=product_id, before_state={"status": product.status.value}, after_state={"status": ProductStatus.VIOLATION.value, "reason": reason}, result="SUCCESS")
