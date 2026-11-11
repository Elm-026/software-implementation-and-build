import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""统计和审计查询测试。"""

from base import ServiceTestCase


class StatisticsTests(ServiceTestCase):
    def test_admin_summary_and_seller_summary(self) -> None:
        product = self.make_published_product("统计商品")
        reservation = self.trade.reserve(self.buyer.user_id, product.product_id, "stats-reserve")
        transaction = self.trade.confirm_reservation(self.seller.user_id, reservation.reservation_id, reservation.version, "stats-confirm")
        self.trade.confirm_receipt(self.buyer.user_id, transaction.transaction_id, transaction.version)
        admin_summary = self.statistics.admin_summary(self.admin.user_id)
        seller_summary = self.statistics.seller_summary(self.seller.user_id)
        self.assertGreaterEqual(admin_summary["products"], 1)
        self.assertGreaterEqual(admin_summary["completed_transactions"], 1)
        self.assertEqual(seller_summary["completed_transactions"], 1)

    def test_audit_is_written_for_key_operations(self) -> None:
        product = self.make_published_product("日志商品")
        logs = self.services_audit().search(self.admin.user_id, object_id=product.product_id)
        actions = {log.action for log in logs}
        self.assertIn("REVIEW_APPROVE", actions)

    def services_audit(self):
        from campus_market.services import AuditService
        return AuditService(self.database)

