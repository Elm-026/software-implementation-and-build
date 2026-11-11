"""Registration, login and role-aware session handling."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import Role, User
from ..utils.security import create_session_token, hash_password, verify_password
from ..utils.validation import validate_email, validate_password, require_non_empty
from .common import AuthenticationError, BaseService, ConflictError, ValidationError


@dataclass(slots=True, frozen=True)
class Session:
    """Short-lived application session returned after a successful login."""

    token: str
    user: User


class AuthService(BaseService):
    """Account lifecycle service.

    Sessions are intentionally held in memory.  The database stores only
    account state and password hashes, while a desktop process owns its active
    tokens.  A later web adapter can replace the dictionary with a session
    store without changing the business API.
    """

    def __init__(self, database) -> None:
        super().__init__(database)
        self._sessions: dict[str, str] = {}

    def register(
        self,
        email: str,
        password: str,
        role: Role | str,
        *,
        display_name: str = "",
        phone: str = "",
    ) -> User:
        normalized_email = validate_email(email)
        validate_password(password)
        try:
            actual_role = role if isinstance(role, Role) else Role(str(role).upper())
        except ValueError as exc:
            raise ValidationError("角色必须是 BUYER、SELLER 或 ADMIN") from exc
        if self.context.users.get_by_email(normalized_email) is not None:
            raise ConflictError("该邮箱已注册")
        user = User(
            user_id=self.new_id(),
            email=normalized_email,
            password_hash=hash_password(password),
            role=actual_role,
            display_name=(display_name or "").strip(),
            phone=(phone or "").strip(),
        )
        self.context.users.create(user)
        return user

    def login(self, email: str, password: str) -> Session:
        normalized_email = validate_email(email)
        user = self.context.users.get_by_email(normalized_email)
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise AuthenticationError("邮箱或密码错误")
        token = create_session_token()
        self._sessions[token] = user.user_id
        return Session(token, user)

    def authenticate(self, token: str) -> User:
        user_id = self._sessions.get((token or "").strip())
        if not user_id:
            raise AuthenticationError("登录会话不存在或已过期")
        return self.user(user_id)

    def logout(self, token: str) -> None:
        self._sessions.pop((token or "").strip(), None)

    def deactivate(self, admin_id: str, user_id: str) -> User:
        self.require_role(admin_id, Role.ADMIN)
        user = self.user(user_id)
        if user.user_id == admin_id:
            raise ValidationError("管理员不能停用自己的账户")
        changed = self.database.execute(
            "UPDATE users SET is_active = 0 WHERE user_id = ? AND is_active = 1",
            (user_id,),
        )
        if changed != 1:
            raise ConflictError("用户状态已经发生变化")
        for token, active_user_id in tuple(self._sessions.items()):
            if active_user_id == user_id:
                self._sessions.pop(token, None)
        return self.user(user_id)

    def list_users(self, admin_id: str, role: Role | str | None = None) -> list[User]:
        self.require_role(admin_id, Role.ADMIN)
        if role is None:
            rows = self.database.fetch_all("SELECT * FROM users ORDER BY created_at")
            return [self.context.users._from_row(row) for row in rows]
        actual_role = role if isinstance(role, Role) else Role(str(role).upper())
        return self.context.users.list_by_role(actual_role)
