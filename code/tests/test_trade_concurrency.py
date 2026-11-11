import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""预约并发、幂等和交易状态机测试。"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from campus_market.domain import ProductStatus, ReservationStatus, TransactionStatus
from campus_market.services import ConflictError, IdempotencyConflict
from base import ServiceTestCase


class TradeConcurrencyTests(ServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.product = self.make_published_product("并发商品")
        self.buyers = [self.auth.register(f"buyer{i}@example.com", "buyerpass", "BUYER") for i in range(20)]

    def test_only_one_buyer_wins(self) -> None:
        def reserve(user):
            try:
                return self.trade.reserve(user.user_id, self.product.product_id, f"reserve-{user.user_id}")
            except ConflictError:
                return None

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(reserve, self.buyers))
        successes = [item for item in results if item is not None]
        self.assertEqual(len(successes), 1)
        row = self.database.fetch_one("SELECT COUNT(*) AS total FROM reservations WHERE product_id = ? AND status = 'ACTIVE'", (self.product.product_id,))
        self.assertEqual(row["total"], 1)
        self.assertEqual(self.products.get(self.product.product_id).status, ProductStatus.RESERVED)

    def test_retry_with_same_key_returns_same_reservation(self) -> None:
        first = self.trade.reserve(self.buyer.user_id, self.product.product_id, "same-key")
        second = self.trade.reserve(self.buyer.user_id, self.product.product_id, "same-key")
        self.assertEqual(first.reservation_id, second.reservation_id)
        with self.assertRaises(IdempotencyConflict):
            self.trade.reserve(self.buyer.user_id, "another-product", "same-key")

    def test_full_transaction_lifecycle(self) -> None:
        reservation = self.trade.reserve(self.buyer.user_id, self.product.product_id, "lifecycle-reserve")
        transaction = self.trade.confirm_reservation(self.seller.user_id, reservation.reservation_id, reservation.version, "lifecycle-confirm")
        self.assertEqual(transaction.status, TransactionStatus.IN_PROGRESS)
        completed = self.trade.confirm_receipt(self.buyer.user_id, transaction.transaction_id, transaction.version)
        self.assertEqual(completed.status, TransactionStatus.COMPLETED)
        self.assertEqual(self.products.get(self.product.product_id).status, ProductStatus.COMPLETED)
        stored = self.database.fetch_one("SELECT status FROM reservations WHERE reservation_id = ?", (reservation.reservation_id,))
        self.assertEqual(stored["status"], ReservationStatus.COMPLETED.value)

