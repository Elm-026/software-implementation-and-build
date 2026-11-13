"""Product lifecycle, versioned editing and buyer-facing search."""

from __future__ import annotations

import json
from decimal import Decimal

from ..domain import Product, ProductStatus, ProductVersion, ReservationStatus, ReviewTask, Role
from ..utils.idempotency import request_hash
from ..utils.validation import parse_price, validate_price_range, validate_product_fields
from .audit_service import AuditService
from .common import BaseService, ConflictError, IdempotencyConflict, NotFoundError, PermissionDenied, ValidationError


class ProductService(BaseService):
    """Seller and buyer product operations."""

    def __init__(self, database) -> None:
        super().__init__(database)
        self.audit = AuditService(self.context)

    def get(self, product_id: str) -> Product:
        product = self.context.products.get(product_id)
        if product is None:
            raise NotFoundError("商品不存在")
        return product

    def save_draft(
        self,
        seller_id: str,
        *,
        title: str,
        description: str,
        category: str,
        price: str | Decimal | int | float,
        condition: str,
        city: str,
        contact: str = "",
        image_urls: list[str] | None = None,
        product_id: str | None = None,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
    ) -> Product:
        seller = self.require_role(seller_id, Role.SELLER)
        fields = validate_product_fields(title, description, category, condition, city)
        fields["price"] = parse_price(price)
        clean_images = list(image_urls or [])
        if len(clean_images) > 12:
            raise ValidationError("商品图片不能超过12张")
        if any(len(url) > 500 for url in clean_images):
            raise ValidationError("图片地址过长")
        payload = {
            "title": fields["title"],
            "description": fields["description"],
            "category": fields["category"],
            "price": str(fields["price"]),
            "condition": fields["condition"],
            "city": fields["city"],
            "contact": (contact or "").strip(),
            "image_urls": clean_images,
            "product_id": product_id,
            "expected_version": expected_version,
        }
        if idempotency_key:
            existing = self._existing_idempotency(seller_id, "save_draft", idempotency_key, payload)
            if existing:
                return self.get(existing)
        if product_id:
            product = self.get(product_id)
            if product.seller_id != seller.user_id:
                raise PermissionDenied("不能修改其他卖家的商品")
            if product.status not in (ProductStatus.DRAFT, ProductStatus.REJECTED):
                raise ConflictError("当前状态不能保存为草稿")
            version = expected_version if expected_version is not None else product.version
            changed = self.context.products.update_fields(
                product_id,
                {**fields, "contact": payload["contact"], "image_urls": clean_images, "status": ProductStatus.DRAFT, "updated_at": self.now()},
                version,
            )
            if not changed:
                raise ConflictError("商品版本已更新，请刷新后重试")
            result = self.get(product_id)
            self._save_idempotency(seller_id, "save_draft", idempotency_key, payload, result.product_id)
            self.audit.record(actor_id=seller_id, role=seller.role, action="SAVE_DRAFT", object_type="Product", object_id=result.product_id, before_state={"version": version}, after_state=self._snapshot(result), result="SUCCESS")
            return result
        product = Product(
            product_id=self.new_id(),
            seller_id=seller_id,
            title=fields["title"],
            description=fields["description"],
            category=fields["category"],
            price=fields["price"],
            condition=fields["condition"],
            city=fields["city"],
            contact=payload["contact"],
            image_urls=clean_images,
        )
        self.context.products.create(product)
        self._save_idempotency(seller_id, "save_draft", idempotency_key, payload, product.product_id)
        self.audit.record(actor_id=seller_id, role=seller.role, action="SAVE_DRAFT", object_type="Product", object_id=product.product_id, before_state=None, after_state=self._snapshot(product), result="SUCCESS")
        return product

    def submit_for_review(self, seller_id: str, product_id: str, idempotency_key: str) -> ReviewTask:
        seller = self.require_role(seller_id, Role.SELLER)
        key = self.require_key(idempotency_key)
        payload = {"product_id": product_id}
        existing = self._existing_idempotency(seller_id, "submit_review", key, payload)
        if existing:
            task = self.context.reviews.get(existing)
            if task is None:
                raise ConflictError("幂等记录指向了不存在的审核任务")
            return task
        product = self.get(product_id)
        if product.seller_id != seller_id:
            raise PermissionDenied("不能提交其他卖家的商品")
        if product.status not in (ProductStatus.DRAFT, ProductStatus.REJECTED):
            raise ConflictError("当前商品状态不能提交审核")
        task = ReviewTask(task_id=self.new_id(), product_id=product_id)
        try:
            with self.database.transaction(immediate=True) as connection:
                current = connection.execute("SELECT status, version FROM products WHERE product_id = ?", (product_id,)).fetchone()
                if current is None or current["status"] not in (ProductStatus.DRAFT.value, ProductStatus.REJECTED.value):
                    raise ConflictError("商品状态已发生变化")
                connection.execute("UPDATE products SET status = ?, version = version + 1, updated_at = ? WHERE product_id = ? AND version = ?", (ProductStatus.PENDING_REVIEW.value, self.now(), product_id, current["version"]))
                self.context.reviews.create(task, connection=connection)
                self._save_idempotency(seller_id, "submit_review", key, payload, task.task_id, connection=connection)
                self.audit.record(actor_id=seller_id, role=seller.role, action="SUBMIT_REVIEW", object_type="Product", object_id=product_id, before_state={"status": current["status"]}, after_state={"status": ProductStatus.PENDING_REVIEW.value}, result="SUCCESS", connection=connection)
        except ConflictError:
            raise
        return task

    def edit_published(self, seller_id: str, product_id: str, expected_version: int, **changes) -> Product:
        seller = self.require_role(seller_id, Role.SELLER)
        product = self.get(product_id)
        if product.seller_id != seller_id:
            raise PermissionDenied("不能修改其他卖家的商品")
        if product.status != ProductStatus.PUBLISHED:
            raise ConflictError("只有已发布商品可以发起修改")
        allowed = {"title", "description", "category", "price", "condition", "city", "contact", "image_urls"}
        update = {key: value for key, value in changes.items() if key in allowed}
        if not update:
            raise ValidationError("至少提供一项修改内容")
        if "price" in update:
            update["price"] = parse_price(update["price"])
        if "title" in update or "description" in update or "category" in update or "condition" in update or "city" in update:
            merged = self._snapshot(product)
            merged.update(update)
            validate_product_fields(merged["title"], merged["description"], merged["category"], merged["condition"], merged["city"])
        changed = self.context.products.update_fields(product_id, {**update, "status": ProductStatus.PENDING_REVIEW, "updated_at": self.now()}, expected_version)
        if not changed:
            raise ConflictError("商品版本已更新，请刷新后重试")
        updated = self.get(product_id)
        self.audit.record(actor_id=seller_id, role=seller.role, action="EDIT_PUBLISHED", object_type="Product", object_id=product_id, before_state={"version": expected_version, "status": ProductStatus.PUBLISHED.value}, after_state=self._snapshot(updated), result="SUCCESS")
        return updated

    def unlist(self, actor_id: str, product_id: str, expected_version: int, reason: str = "") -> Product:
        actor = self.user(actor_id)
        product = self.get(product_id)
        if actor.role != Role.ADMIN and product.seller_id != actor_id:
            raise PermissionDenied("不能下架其他卖家的商品")
        if actor.role not in (Role.BUYER, Role.SELLER, Role.ADMIN):
            raise PermissionDenied("当前角色不能下架商品")
        if product.status not in (ProductStatus.PUBLISHED, ProductStatus.REJECTED):
            raise ConflictError("当前商品状态不能下架")
        active = self.database.fetch_one("SELECT reservation_id FROM reservations WHERE product_id = ? AND status = ?", (product_id, ReservationStatus.ACTIVE.value))
        if active and actor.role == Role.SELLER:
            raise ConflictError("已有有效预约，卖家不能直接下架")
        status = ProductStatus.VIOLATION if actor.role == Role.ADMIN else ProductStatus.UNLISTED
        changed = self.context.products.update_fields(product_id, {"status": status, "updated_at": self.now()}, expected_version)
        if not changed:
            raise ConflictError("商品版本已更新，请刷新后重试")
        updated = self.get(product_id)
        self.audit.record(actor_id=actor_id, role=actor.role, action="FORCE_UNLIST" if actor.role == Role.ADMIN else "UNLIST", object_type="Product", object_id=product_id, before_state={"status": product.status.value}, after_state={"status": status.value, "reason": reason}, result="SUCCESS")
        return updated

    def search(self, buyer_id: str, *, keyword: str = "", category: str = "", minimum=None, maximum=None, page: int = 1, page_size: int = 20, order_by: str = "updated_at") -> list[Product]:
        self.require_role(buyer_id, Role.BUYER)
        low, high = validate_price_range(minimum, maximum)
        if page_size < 1 or page_size > 100:
            raise ValidationError("每页数量必须在1到100之间")
        return self.context.products.list_visible(keyword=(keyword or "").strip(), category=(category or "").strip(), minimum=low, maximum=high, page=page, page_size=page_size, order_by=order_by)

    def _existing_idempotency(self, actor_id: str, operation: str, key: str | None, payload: dict) -> str | None:
        if not key:
            return None
        record = self.context.idempotency.get(actor_id, operation, key)
        if record is None:
            return None
        if record.request_hash != request_hash(payload):
            raise IdempotencyConflict("相同幂等键不能用于不同请求")
        return record.result_ref

    def _save_idempotency(self, actor_id: str, operation: str, key: str | None, payload: dict, result_ref: str, connection=None) -> None:
        if not key:
            return
        from ..domain import IdempotencyRecord

        try:
            self.context.idempotency.create(IdempotencyRecord(key=key, actor_id=actor_id, operation=operation, request_hash=request_hash(payload), result_ref=result_ref, result_status="SUCCESS", response_json=json.dumps({"result_ref": result_ref}, ensure_ascii=False), created_at=self.now()), connection=connection)
        except Exception as exc:
            if "UNIQUE" not in str(exc).upper():
                raise

    @staticmethod
    def _snapshot(product: Product) -> dict:
        return {"title": product.title, "description": product.description, "category": product.category, "price": str(product.price), "condition": product.condition, "city": product.city, "contact": product.contact, "image_urls": product.image_urls, "status": product.status.value, "version": product.version}
