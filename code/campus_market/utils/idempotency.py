"""写操作幂等键的规范化和请求指纹。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


class IdempotencyConflict(ValueError):
    """同一幂等键被用于不同请求参数。"""


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def request_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def validate_key(key: str) -> str:
    normalized = (key or "").strip()
    if not normalized:
        raise ValueError("幂等键不能为空")
    if len(normalized) > 128:
        raise ValueError("幂等键长度不能超过128个字符")
    return normalized

