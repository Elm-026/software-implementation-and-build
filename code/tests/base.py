import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""Shared service fixtures for unit tests."""

import tempfile
import unittest
from pathlib import Path

from campus_market.infra import Database
from campus_market.services import AuthService, ProductService, ReviewService, StatisticsService, TradeService


class ServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.sqlite3")
        self.auth = AuthService(self.database)
        self.products = ProductService(self.database)
        self.reviews = ReviewService(self.database)
        self.trade = TradeService(self.database)
        self.statistics = StatisticsService(self.database)
        self.seller = self.auth.register("seller@example.com", "sellerpass", "SELLER", display_name="卖家")
        self.admin = self.auth.register("admin@example.com", "adminpass", "ADMIN", display_name="管理员")
        self.buyer = self.auth.register("buyer@example.com", "buyerpass", "BUYER", display_name="买家")

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def make_published_product(self, title: str = "二手书"):
        product = self.products.save_draft(
            self.seller.user_id,
            title=title,
            description="保存完好的教材",
            category="教材",
            price="12.50",
            condition="九成新",
            city="南京",
            contact="13800000000",
            idempotency_key=f"draft-{title}",
        )
        self.reviews_task = self.products.submit_for_review(self.seller.user_id, product.product_id, f"review-{product.product_id}")
        self.reviews.decide(self.admin.user_id, product.product_id, "APPROVE")
        return self.products.get(product.product_id)


