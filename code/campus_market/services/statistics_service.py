"""Operational statistics for administrators and sellers."""

from __future__ import annotations

from datetime import date

from ..domain import Role
from .common import BaseService, ValidationError


class StatisticsService(BaseService):
    """Read-only aggregation queries kept separate from transaction writes."""

    @staticmethod
    def _date(value: str | date | None, field: str) -> str | None:
        if value is None or value == "":
            return None
        text = value.isoformat() if isinstance(value, date) else str(value)
        try:
            date.fromisoformat(text)
        except ValueError as exc:
            raise ValidationError(f"{field}必须是 YYYY-MM-DD") from exc
        return text

    def admin_summary(
        self,
        admin_id: str,
        *,
        start: str | date | None = None,
        end: str | date | None = None,
        category: str | None = None,
        status: str | None = None,
    ) -> dict[str, int | str | None]:
        self.require_role(admin_id, Role.ADMIN)
        start_text = self._date(start, "开始日期")
        end_text = self._date(end, "结束日期")
        if start_text and end_text and start_text > end_text:
            raise ValidationError("开始日期不能晚于结束日期")
        product_where, product_values = self._date_filter("created_at", start_text, end_text)
        product_clauses = list(product_where)
        values = list(product_values)
        if category:
            product_clauses.append("category = ?")
            values.append(category)
        if status:
            product_clauses.append("status = ?")
            values.append(status.upper())
        where_sql = " AND ".join(product_clauses) or "1 = 1"
        row = self.database.fetch_one(f"SELECT COUNT(*) AS total, SUM(CASE WHEN status IN ('PUBLISHED','RESERVED','IN_TRANSACTION','COMPLETED') THEN 1 ELSE 0 END) AS published, SUM(CASE WHEN status = 'VIOLATION' THEN 1 ELSE 0 END) AS violations FROM products WHERE {where_sql}", tuple(values))
        reservation_where, reservation_values = self._date_filter("created_at", start_text, end_text)
        reservation_count = self._count("reservations", reservation_where, reservation_values)
        transaction_where, transaction_values = self._date_filter("created_at", start_text, end_text)
        completed_count = self._count("transactions", [*transaction_where, "status = 'COMPLETED'"], transaction_values)
        return {"products": int(row["total"] or 0), "published_products": int(row["published"] or 0), "reservations": reservation_count, "completed_transactions": completed_count, "violations": int(row["violations"] or 0), "start": start_text, "end": end_text, "category": category, "status": status.upper() if status else None}

    def seller_summary(self, seller_id: str, *, start: str | date | None = None, end: str | date | None = None) -> dict[str, int | str | None]:
        self.require_role(seller_id, Role.SELLER)
        start_text = self._date(start, "开始日期")
        end_text = self._date(end, "结束日期")
        if start_text and end_text and start_text > end_text:
            raise ValidationError("开始日期不能晚于结束日期")
        clauses, values = self._date_filter("created_at", start_text, end_text)
        clauses.insert(0, "seller_id = ?")
        values.insert(0, seller_id)
        product_count = self._count("products", clauses, values)
        reservation_clauses, reservation_values = self._date_filter("r.created_at", start_text, end_text)
        reservation_clauses.insert(0, "p.seller_id = ?")
        reservation_values.insert(0, seller_id)
        reservation_count = self._count_join("reservations r JOIN products p ON p.product_id = r.product_id", reservation_clauses, reservation_values)
        transaction_clauses, transaction_values = self._date_filter("t.created_at", start_text, end_text)
        transaction_clauses.extend(["t.seller_id = ?", "t.status = 'COMPLETED'"])
        transaction_values.append(seller_id)
        completed_count = self._count_join("transactions t", transaction_clauses, transaction_values)
        return {"products": product_count, "reservations": reservation_count, "completed_transactions": completed_count, "start": start_text, "end": end_text}

    def daily_counts(self, admin_id: str, *, start: str | date, end: str | date) -> list[dict[str, str | int]]:
        self.require_role(admin_id, Role.ADMIN)
        start_text = self._date(start, "开始日期")
        end_text = self._date(end, "结束日期")
        if start_text is None or end_text is None or start_text > end_text:
            raise ValidationError("日期范围无效")
        rows = self.database.fetch_all("SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS total FROM products WHERE substr(created_at, 1, 10) BETWEEN ? AND ? GROUP BY day ORDER BY day", (start_text, end_text))
        values = {row["day"]: int(row["total"]) for row in rows}
        current = date.fromisoformat(start_text)
        last = date.fromisoformat(end_text)
        result: list[dict[str, str | int]] = []
        while current <= last:
            key = current.isoformat()
            result.append({"date": key, "products": values.get(key, 0)})
            current = current.fromordinal(current.toordinal() + 1)
        return result

    def _count(self, table: str, clauses: list[str], values: list) -> int:
        where_sql = " AND ".join(clauses) or "1 = 1"
        row = self.database.fetch_one(f"SELECT COUNT(*) AS total FROM {table} WHERE {where_sql}", tuple(values))
        return int(row["total"] if row else 0)

    def _count_join(self, table_sql: str, clauses: list[str], values: list) -> int:
        where_sql = " AND ".join(clauses) or "1 = 1"
        row = self.database.fetch_one(f"SELECT COUNT(*) AS total FROM {table_sql} WHERE {where_sql}", tuple(values))
        return int(row["total"] if row else 0)

    @staticmethod
    def _date_filter(column: str, start: str | None, end: str | None) -> tuple[list[str], list[str]]:
        clauses: list[str] = []
        values: list[str] = []
        if start:
            clauses.append(f"substr({column}, 1, 10) >= ?")
            values.append(start)
        if end:
            clauses.append(f"substr({column}, 1, 10) <= ?")
            values.append(end)
        return clauses, values
