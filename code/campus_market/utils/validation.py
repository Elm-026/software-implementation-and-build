"""输入格式验证，抛出可展示给用户的 ValueError。"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def require_non_empty(value: str, field_name: str, max_length: int = 200) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name}不能为空")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name}长度不能超过{max_length}个字符")
    return normalized


def validate_email(email: str) -> str:
    normalized = require_non_empty(email, "邮箱", 254).lower()
    if not EMAIL_PATTERN.match(normalized):
        raise ValueError("邮箱格式不正确")
    return normalized


def validate_password(password: str) -> str:
    if len(password or "") < 8:
        raise ValueError("密码至少需要 8 个字符")
    if len(password) > 128:
        raise ValueError("密码长度不能超过128个字符")
    return password


def parse_price(value: str | Decimal | int | float) -> Decimal:
    try:
        price = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError("价格必须是合法数字") from None
    if price < 0:
        raise ValueError("价格不能为负数")
    if price > Decimal("99999999.99"):
        raise ValueError("价格超出允许范围")
    return price


def validate_price_range(minimum: str | Decimal | None, maximum: str | Decimal | None) -> tuple[Decimal | None, Decimal | None]:
    low = parse_price(minimum) if minimum not in (None, "") else None
    high = parse_price(maximum) if maximum not in (None, "") else None
    if low is not None and high is not None and low > high:
        raise ValueError("最低价格不能高于最高价格")
    return low, high


def validate_product_fields(title: str, description: str, category: str, condition: str, city: str) -> dict[str, str]:
    return {
        "title": require_non_empty(title, "标题", 120),
        "description": require_non_empty(description, "描述", 5000),
        "category": require_non_empty(category, "分类", 60),
        "condition": require_non_empty(condition, "成色", 60),
        "city": require_non_empty(city, "城市", 80),
    }

