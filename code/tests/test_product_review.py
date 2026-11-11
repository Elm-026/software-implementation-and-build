import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""商品草稿、审核和乐观版本控制测试。"""

from campus_market.domain import ProductStatus
from campus_market.services import ConflictError, ValidationError
from base import ServiceTestCase


class ProductReviewTests(ServiceTestCase):
    def test_draft_review_and_publish(self) -> None:
        product = self.products.save_draft(self.seller.user_id, title="数据结构", description="教材", category="教材", price="20", condition="九成新", city="南京", idempotency_key="draft-one")
        task = self.products.submit_for_review(self.seller.user_id, product.product_id, "submit-one")
        self.assertEqual(self.products.get(product.product_id).status, ProductStatus.PENDING_REVIEW)
        result = self.reviews.decide(self.admin.user_id, product.product_id, "APPROVE")
        self.assertEqual(result.task_id, task.task_id)
        self.assertEqual(self.products.get(product.product_id).status, ProductStatus.PUBLISHED)

    def test_rejection_requires_reason_and_allows_resubmission(self) -> None:
        product = self.products.save_draft(self.seller.user_id, title="旧手机", description="手机", category="数码", price=800, condition="八成新", city="南京")
        self.products.submit_for_review(self.seller.user_id, product.product_id, "submit-two")
        with self.assertRaises(ValidationError):
            self.reviews.decide(self.admin.user_id, product.product_id, "REJECT")
        self.reviews.decide(self.admin.user_id, product.product_id, "REJECT", reason="缺少成色照片")
        rejected = self.products.get(product.product_id)
        self.assertEqual(rejected.status, ProductStatus.REJECTED)
        draft = self.products.save_draft(self.seller.user_id, product_id=product.product_id, expected_version=rejected.version, title="旧手机", description="手机和照片", category="数码", price=800, condition="八成新", city="南京")
        self.assertEqual(draft.status, ProductStatus.DRAFT)

    def test_stale_version_is_rejected(self) -> None:
        product = self.products.save_draft(self.seller.user_id, title="耳机", description="蓝牙耳机", category="数码", price=100, condition="九成新", city="南京")
        current = self.products.save_draft(self.seller.user_id, product_id=product.product_id, expected_version=product.version, title="耳机2", description="蓝牙耳机", category="数码", price=90, condition="九成新", city="南京")
        with self.assertRaises(ConflictError):
            self.products.save_draft(self.seller.user_id, product_id=product.product_id, expected_version=product.version, title="过期修改", description="蓝牙耳机", category="数码", price=80, condition="九成新", city="南京")
        self.assertGreater(current.version, product.version)

