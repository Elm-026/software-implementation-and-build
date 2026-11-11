"""Audit trail writing and administrator-only querying."""

from __future__ import annotations

from ..domain import AuditLog, Role
from .common import BaseService, PermissionDenied


class AuditService(BaseService):
    """Persist security-relevant operations in an append-only table."""

    def record(
        self,
        *,
        actor_id: str | None,
        role: Role | None,
        action: str,
        object_type: str,
        object_id: str | None,
        before_state: dict | None,
        after_state: dict | None,
        result: str,
        request_id: str | None = None,
        connection=None,
    ) -> AuditLog:
        log = AuditLog(
            log_id=self.new_id(),
            actor_id=actor_id,
            role=role,
            action=action,
            object_type=object_type,
            object_id=object_id,
            before_state=before_state,
            after_state=after_state,
            result=result,
            request_id=request_id or self.new_id(),
            created_at=self.now(),
        )
        self.context.audits.create(log, connection=connection)
        return log

    def search(
        self,
        admin_id: str,
        *,
        actor_id: str | None = None,
        role: Role | str | None = None,
        object_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        self.require_role(admin_id, Role.ADMIN)
        actual_role = role
        if isinstance(role, str):
            actual_role = Role(role.upper())
        return self.context.audits.search(
            actor_id=actor_id,
            role=actual_role,
            object_id=object_id,
            limit=min(max(1, limit), 1000),
        )

    def count_for_actor(self, actor_id: str) -> int:
        row = self.database.fetch_one(
            "SELECT COUNT(*) AS total FROM audit_logs WHERE actor_id = ?",
            (actor_id,),
        )
        return int(row["total"] if row else 0)

