"""登录与注册窗口。"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..domain import Role
from ..services import AuthService, AuthenticationError, ServiceError


class LoginView(ttk.Frame):
    """让用户登录或创建一个带角色的本地账户。"""

    def __init__(self, master: tk.Misc, auth: AuthService, on_login) -> None:
        super().__init__(master, padding=24)
        self.auth = auth
        self.on_login = on_login
        self.email = tk.StringVar()
        self.password = tk.StringVar()
        self.display_name = tk.StringVar()
        self.phone = tk.StringVar()
        self.role = tk.StringVar(value=Role.BUYER.value)
        self._build()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text="校园二手交易系统", font=("Microsoft YaHei UI", 20, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20))
        ttk.Label(self, text="邮箱").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(self, textvariable=self.email, width=34).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Label(self, text="密码").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(self, textvariable=self.password, show="*", width=34).grid(row=2, column=1, sticky="ew", pady=5)
        ttk.Label(self, text="账号类型").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Combobox(self, textvariable=self.role, values=[Role.BUYER.value, Role.ADMIN.value], state="readonly", width=31).grid(row=3, column=1, sticky="ew", pady=5)
        ttk.Label(self, text="显示名称").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(self, textvariable=self.display_name, width=34).grid(row=4, column=1, sticky="ew", pady=5)
        ttk.Label(self, text="联系方式").grid(row=5, column=0, sticky="w", pady=5)
        ttk.Entry(self, textvariable=self.phone, width=34).grid(row=5, column=1, sticky="ew", pady=5)
        buttons = ttk.Frame(self)
        buttons.grid(row=6, column=0, columnspan=2, pady=(18, 0))
        ttk.Button(buttons, text="登录", command=self._login).pack(side="left", padx=5)
        ttk.Button(buttons, text="注册并登录", command=self._register).pack(side="left", padx=5)
        ttk.Label(self, text="普通账号可同时买卖，管理员账号用于审核和系统管理。", foreground="#666666").grid(row=7, column=0, columnspan=2, pady=(18, 0))

    def _login(self) -> None:
        try:
            session = self.auth.login(self.email.get(), self.password.get())
        except (AuthenticationError, ServiceError, ValueError) as exc:
            messagebox.showerror("登录失败", str(exc), parent=self)
            return
        self.on_login(session)

    def _register(self) -> None:
        try:
            user = self.auth.register(self.email.get(), self.password.get(), self.role.get(), display_name=self.display_name.get(), phone=self.phone.get())
            session = self.auth.login(user.email, self.password.get())
        except (ServiceError, ValueError) as exc:
            messagebox.showerror("注册失败", str(exc), parent=self)
            return
        self.on_login(session)

