import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""认证、权限和密码存储测试。"""

from campus_market.domain import Role
from campus_market.services import AuthenticationError, ConflictError, PermissionDenied
from base import ServiceTestCase


class AuthServiceTests(ServiceTestCase):
    def test_register_login_and_logout(self) -> None:
        session = self.auth.login("buyer@example.com", "buyerpass")
        self.assertEqual(session.user.role, Role.BUYER)
        self.assertEqual(self.auth.authenticate(session.token).user_id, self.buyer.user_id)
        self.auth.logout(session.token)
        with self.assertRaises(AuthenticationError):
            self.auth.authenticate(session.token)

    def test_password_is_hashed_and_duplicate_email_is_rejected(self) -> None:
        stored = self.database.fetch_one("SELECT password_hash FROM users WHERE user_id = ?", (self.buyer.user_id,))
        self.assertIsNotNone(stored)
        self.assertNotEqual(stored["password_hash"], "buyerpass")
        with self.assertRaises(ConflictError):
            self.auth.register("BUYER@example.com", "anotherpass", "BUYER")

    def test_regular_account_can_buy_and_sell(self) -> None:
        own_draft = self.products.save_draft(
            self.buyer.user_id,
            title="买卖一体测试",
            description="同一个账号可以发布商品",
            category="教材",
            price=1,
            condition="全新",
            city="南京",
        )
        self.assertEqual(own_draft.seller_id, self.buyer.user_id)
        published = self.make_published_product()
        reservation = self.trade.reserve(self.buyer.user_id, published.product_id, "buyer-seller-same-account")
        self.assertEqual(reservation.buyer_id, self.buyer.user_id)
        with self.assertRaises(PermissionDenied):
            self.reviews.pending(self.buyer.user_id)
    def test_admin_can_deactivate_user(self) -> None:
        result = self.auth.deactivate(self.admin.user_id, self.buyer.user_id)
        self.assertFalse(result.is_active)
        with self.assertRaises(AuthenticationError):
            self.auth.login("buyer@example.com", "buyerpass")

