"""Local web entry point for the campus resale system.

The server intentionally uses only the Python standard library so the project
can be started on a clean course workstation.  Read-only catalog routes are
available to guests.  Mutating routes require a bearer token created by the
login endpoint.
"""

from __future__ import annotations

import json
import mimetypes
import threading
import uuid
from dataclasses import asdict
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from typing import Any
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent
CODE_ROOT = PROJECT_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from campus_market.domain import Role
from campus_market.infra import Database
from campus_market.services import (
    AuditService,
    AuthService,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDenied,
    ProductService,
    ReviewService,
    ServiceContext,
    ServiceError,
    StatisticsService,
    TradeService,
    ValidationError,
)
from campus_market.utils.validation import parse_price, validate_price_range


WEB_ROOT = PROJECT_ROOT / "web"
# Keep the Web and desktop entry points on the same project database.
DATABASE_PATH = PROJECT_ROOT / "campus_market.sqlite3"


class AppServices:
    """Shared service objects used by each request handler."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.context = ServiceContext.create(database)
        self.auth = AuthService(self.context)
        self.products = ProductService(self.context)
        self.reviews = ReviewService(self.context)
        self.trade = TradeService(self.context)
        self.statistics = StatisticsService(self.context)
        self.audit = AuditService(self.context)


def _user_json(user) -> dict[str, Any]:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role.value,
        "display_name": user.display_name,
        "phone": user.phone,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }


def _product_json(product) -> dict[str, Any]:
    return {
        "product_id": product.product_id,
        "seller_id": product.seller_id,
        "title": product.title,
        "description": product.description,
        "category": product.category,
        "price": str(product.price),
        "condition": product.condition,
        "city": product.city,
        "contact": product.contact,
        "image_urls": product.image_urls,
        "status": product.status.value,
        "version": product.version,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
        "published_at": product.published_at,
    }


def _reservation_json(item) -> dict[str, Any]:
    return {
        "reservation_id": item.reservation_id,
        "product_id": item.product_id,
        "buyer_id": item.buyer_id,
        "status": item.status.value,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "version": item.version,
    }


def _task_json(item) -> dict[str, Any]:
    return {
        "task_id": item.task_id,
        "product_id": item.product_id,
        "reviewer_id": item.reviewer_id,
        "decision": item.decision,
        "reason": item.reason,
        "status": item.status,
        "created_at": item.created_at,
        "reviewed_at": item.reviewed_at,
    }


def _ensure_demo_data(services: AppServices) -> None:
    """Create a small catalog on a new checkout so the guest page is useful."""

    demo_accounts = [
        ("demo-buyer@campus.test", "CampusBuyer123", Role.BUYER, "演示买家"),
        ("demo-seller@campus.test", "CampusSeller123", Role.SELLER, "演示卖家"),
        ("demo-admin@campus.test", "CampusAdmin123", Role.ADMIN, "演示管理员"),
    ]
    users = {}
    for email, password, role, display_name in demo_accounts:
        user = services.context.users.get_by_email(email)
        if user is None:
            user = services.auth.register(email, password, role, display_name=display_name)
        users[role] = user

    count_row = services.database.fetch_one("SELECT COUNT(*) AS total FROM products")
    if not count_row or count_row["total"]:
        return

    samples = [
        ("高等数学教材", "考研复习和课程学习都适用，页面整洁，少量笔记。", "教材", "九成新", "南京", "38.00"),
        ("机械键盘", "87 键热插拔机械键盘，适合宿舍和办公使用。", "数码", "九成新", "南京", "168.00"),
        ("宿舍收纳推车", "三层收纳推车，毕业清理，取货方便。", "生活", "八成新", "南京", "25.00"),
        ("摄影入门套装", "入门相机、肩带和备用电池一起出售。", "兴趣", "八成新", "南京", "699.00"),
        ("英语四级资料包", "真题、词汇书和听力资料打包出售。", "教材", "九成新", "南京", "19.90"),
        ("宿舍台灯", "三档亮度，可折叠，适合书桌阅读。", "生活", "全新", "南京", "42.00"),
    ]
    for index, (title, description, category, condition, city, price) in enumerate(samples):
        product = services.products.save_draft(
            users[Role.SELLER].user_id,
            title=title,
            description=description,
            category=category,
            price=price,
            condition=condition,
            city=city,
            contact="demo-seller@campus.test",
            idempotency_key=f"demo-draft-{index}",
        )
        services.products.submit_for_review(users[Role.SELLER].user_id, product.product_id, f"demo-review-{index}")
        services.reviews.decide(users[Role.ADMIN].user_id, product.product_id, "APPROVE", reason="演示商品审核通过")


class CampusRequestHandler(BaseHTTPRequestHandler):
    """HTTP adapter for the service layer."""

    server_version = "CampusMarket/1.0"

    @property
    def services(self) -> AppServices:
        return self.server.services  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/health":
                self._json(HTTPStatus.OK, {"status": "ok", "service": "campus-market"})
                return
            if path == "/api/products":
                self._list_products()
                return
            if path.startswith("/api/products/"):
                self._get_product(path.rsplit("/", 1)[-1])
                return
            if path == "/api/me":
                self._json(HTTPStatus.OK, {"user": _user_json(self._require_user())})
                return
            if path == "/api/my/reservations":
                user = self._require_user(Role.BUYER)
                items = self.services.trade.reservations_for_buyer(user.user_id)
                self._json(HTTPStatus.OK, {"items": [_reservation_json(item) for item in items]})
                return
            if path == "/api/seller/products":
                user = self._require_user(Role.SELLER)
                rows = self.services.database.fetch_all(
                    "SELECT * FROM products WHERE seller_id = ? ORDER BY updated_at DESC",
                    (user.user_id,),
                )
                products = [self.services.context.products._from_row(row) for row in rows]
                self._json(HTTPStatus.OK, {"items": [_product_json(item) for item in products]})
                return
            if path == "/api/admin/reviews":
                user = self._require_user(Role.ADMIN)
                tasks = self.services.reviews.pending(user.user_id)
                self._json(HTTPStatus.OK, {"items": [_task_json(item) for item in tasks]})
                return
            if path == "/api/admin/stats":
                user = self._require_user(Role.ADMIN)
                self._json(HTTPStatus.OK, self.services.statistics.admin_summary(user.user_id))
                return
            self._static(path)
        except Exception as exc:
            self._handle_error(exc)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self._body()
            if path == "/api/auth/register":
                self._register(body)
                return
            if path == "/api/auth/login":
                self._login(body)
                return
            if path == "/api/auth/logout":
                token = self._token()
                self.services.auth.logout(token)
                self._json(HTTPStatus.OK, {"ok": True})
                return
            if path == "/api/reservations":
                self._reserve(body)
                return
            if path == "/api/products":
                self._save_product(body)
                return
            if path.startswith("/api/products/") and path.endswith("/submit"):
                self._submit_product(path.split("/")[3])
                return
            if path.startswith("/api/reservations/") and path.endswith("/cancel"):
                self._cancel_reservation(path.split("/")[3], body)
                return
            if path.startswith("/api/reservations/") and path.endswith("/confirm"):
                self._confirm_reservation(path.split("/")[3], body)
                return
            if path.startswith("/api/transactions/") and path.endswith("/complete"):
                self._complete_transaction(path.split("/")[3], body)
                return
            if path.startswith("/api/reviews/") and path.endswith("/decision"):
                self._decide_review(path.split("/")[3], body)
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
        except Exception as exc:
            self._handle_error(exc)

    def _list_products(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        keyword = query.get("keyword", [""])[0].strip()
        category = query.get("category", [""])[0].strip()
        minimum, maximum = validate_price_range(query.get("min", [""])[0], query.get("max", [""])[0])
        page = max(1, int(query.get("page", ["1"])[0]))
        page_size = min(48, max(1, int(query.get("page_size", ["12"])[0])))
        order_by = query.get("sort", ["updated_at"])[0]
        products = self.services.context.products.list_visible(
            keyword=keyword,
            category=category,
            minimum=minimum,
            maximum=maximum,
            page=page,
            page_size=page_size,
            order_by=order_by,
        )
        self._json(HTTPStatus.OK, {"items": [_product_json(item) for item in products], "page": page, "page_size": page_size})

    def _get_product(self, product_id: str) -> None:
        product = self.services.products.get(product_id)
        self._json(HTTPStatus.OK, {"item": _product_json(product)})

    def _register(self, body: dict[str, Any]) -> None:
        user = self.services.auth.register(
            body.get("email", ""),
            body.get("password", ""),
            body.get("role", Role.BUYER.value),
            display_name=body.get("display_name", ""),
            phone=body.get("phone", ""),
        )
        session = self.services.auth.login(user.email, body.get("password", ""))
        self._json(HTTPStatus.CREATED, {"token": session.token, "user": _user_json(session.user)})

    def _login(self, body: dict[str, Any]) -> None:
        session = self.services.auth.login(body.get("email", ""), body.get("password", ""))
        self._json(HTTPStatus.OK, {"token": session.token, "user": _user_json(session.user)})

    def _reserve(self, body: dict[str, Any]) -> None:
        user = self._require_user(Role.BUYER)
        key = body.get("idempotency_key") or f"web-reserve-{uuid.uuid4()}"
        item = self.services.trade.reserve(user.user_id, body.get("product_id", ""), key)
        self._json(HTTPStatus.CREATED, {"item": _reservation_json(item)})

    def _save_product(self, body: dict[str, Any]) -> None:
        user = self._require_user(Role.SELLER)
        product = self.services.products.save_draft(
            user.user_id,
            title=body.get("title", ""),
            description=body.get("description", ""),
            category=body.get("category", ""),
            price=body.get("price", ""),
            condition=body.get("condition", ""),
            city=body.get("city", ""),
            contact=body.get("contact", ""),
            image_urls=body.get("image_urls", []),
            product_id=body.get("product_id"),
            expected_version=body.get("expected_version"),
            idempotency_key=body.get("idempotency_key") or f"web-draft-{uuid.uuid4()}",
        )
        self._json(HTTPStatus.CREATED, {"item": _product_json(product)})

    def _submit_product(self, product_id: str) -> None:
        user = self._require_user(Role.SELLER)
        task = self.services.products.submit_for_review(user.user_id, product_id, f"web-submit-{uuid.uuid4()}")
        self._json(HTTPStatus.OK, {"item": _task_json(task)})

    def _cancel_reservation(self, reservation_id: str, body: dict[str, Any]) -> None:
        user = self._require_user(Role.BUYER)
        item = self.services.trade.cancel(user.user_id, reservation_id, int(body.get("expected_version", 1)), body.get("idempotency_key") or f"web-cancel-{uuid.uuid4()}")
        self._json(HTTPStatus.OK, {"item": _reservation_json(item)})

    def _confirm_reservation(self, reservation_id: str, body: dict[str, Any]) -> None:
        user = self._require_user(Role.SELLER)
        transaction = self.services.trade.confirm_reservation(user.user_id, reservation_id, int(body.get("expected_version", 1)), body.get("idempotency_key") or f"web-confirm-{uuid.uuid4()}")
        self._json(HTTPStatus.OK, {"item": asdict(transaction)})

    def _complete_transaction(self, transaction_id: str, body: dict[str, Any]) -> None:
        user = self._require_user(Role.BUYER)
        transaction = self.services.trade.confirm_receipt(user.user_id, transaction_id, int(body.get("expected_version", 1)))
        self._json(HTTPStatus.OK, {"item": asdict(transaction)})

    def _decide_review(self, product_id: str, body: dict[str, Any]) -> None:
        user = self._require_user(Role.ADMIN)
        task = self.services.reviews.decide(user.user_id, product_id, body.get("decision", ""), reason=body.get("reason", ""), expected_version=body.get("expected_version"))
        self._json(HTTPStatus.OK, {"item": _task_json(task)})

    def _require_user(self, *roles: Role):
        token = self._token()
        user = self.services.auth.authenticate(token)
        if roles:
            requested = set(roles)
            is_trade_capability = bool(requested & {Role.BUYER, Role.SELLER}) and Role.ADMIN not in requested
            allowed = user.role in requested or (is_trade_capability and user.role in {Role.BUYER, Role.SELLER, Role.ADMIN})
            if not allowed:
                raise PermissionDenied("当前账号无权执行该操作")
        return user

    def _token(self) -> str:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise AuthenticationError("请先登录")
        return header[7:].strip()

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValidationError("请求体过大")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("请求必须是合法 JSON") from exc
        if not isinstance(value, dict):
            raise ValidationError("请求体必须是 JSON 对象")
        return value

    def _static(self, path: str) -> None:
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        candidate = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in candidate.parents and candidate != WEB_ROOT.resolve():
            self._json(HTTPStatus.NOT_FOUND, {"error": "资源不存在"})
            return
        if not candidate.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "资源不存在"})
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        data = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._cors_headers()
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int | HTTPStatus, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _handle_error(self, exc: Exception) -> None:
        if isinstance(exc, AuthenticationError):
            self._json(HTTPStatus.UNAUTHORIZED, {"error": str(exc)})
        elif isinstance(exc, PermissionDenied):
            self._json(HTTPStatus.FORBIDDEN, {"error": str(exc)})
        elif isinstance(exc, NotFoundError):
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
        elif isinstance(exc, ConflictError):
            self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
        elif isinstance(exc, (ValidationError, ValueError)):
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        elif isinstance(exc, ServiceError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        else:
            print(f"Unhandled request error: {exc!r}")
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "服务器内部错误"})


class CampusMarketServer(ThreadingHTTPServer):
    """HTTP server carrying the shared service container."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], services: AppServices) -> None:
        super().__init__(address, CampusRequestHandler)
        self.services = services


def create_server(host: str = "127.0.0.1", port: int = 8080, database_path: str | Path = DATABASE_PATH) -> CampusMarketServer:
    database = Database(database_path)
    services = AppServices(database)
    _ensure_demo_data(services)
    return CampusMarketServer((host, port), services)


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = create_server(host, port)
    print(f"校园二手交易系统已启动 http://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("正在关闭服务器")
    finally:
        server.shutdown()
        server.server_close()
        server.services.database.close()


if __name__ == "__main__":
    serve()
