"""登录与注册窗口。"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..domain import Role
from ..services import AuthService, AuthenticationError, ServiceError
from .theme import LINE, NAVY, NAVY_LIGHT, PAPER, configure


class LoginView(ttk.Frame):
    """与实验二视觉稿一致的登录和注册窗口。"""

    def __init__(self, master: tk.Misc, auth: AuthService, on_login) -> None:
        super().__init__(master, style="App.TFrame", padding=32)
        self.auth = auth
        self.on_login = on_login
        self.email = tk.StringVar()
        self.password = tk.StringVar()
        self.display_name = tk.StringVar()
        self.phone = tk.StringVar()
        self.role = tk.StringVar(value=Role.BUYER.value)
        configure(master)
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=9)
        self.columnconfigure(1, weight=11)
        self.rowconfigure(0, weight=1)

        left = tk.Frame(self, bg=NAVY, highlightthickness=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(4, weight=1)
        tk.Label(left, text="拾光集市", bg=NAVY, fg=PAPER, font=("Microsoft YaHei UI", 28, "bold")).grid(row=0, column=0, sticky="w", padx=54, pady=(64, 4))
        tk.Label(left, text="校内可信二手交易平台", bg=NAVY, fg="#b7c9df", font=("Microsoft YaHei UI", 12)).grid(row=1, column=0, sticky="w", padx=56)
        promise = tk.Frame(left, bg=NAVY_LIGHT)
        promise.grid(row=2, column=0, sticky="ew", padx=54, pady=(46, 0))
        tk.Label(promise, text="一件闲置 · 一次循环 · 一份信任", bg=NAVY_LIGHT, fg=PAPER, font=("Microsoft YaHei UI", 12, "bold"), pady=19).pack(fill="x")
        features = tk.Frame(left, bg=NAVY)
        features.grid(row=3, column=0, sticky="ew", padx=56, pady=(40, 0))
        for text in ("实名角色分级", "审核后公开发布", "预约状态可追踪"):
            row = tk.Frame(features, bg=NAVY)
            row.pack(fill="x", pady=10)
            tk.Label(row, text="□", bg=NAVY, fg="#45d6ca", font=("Microsoft YaHei UI", 13, "bold")).pack(side="left")
            tk.Label(row, text=text, bg=NAVY, fg="#e0ebf7", font=("Microsoft YaHei UI", 11)).pack(side="left", padx=14)
        tk.Label(left, text="校园里的每一次交换，都值得被认真记录。", bg=NAVY, fg="#8fa9c5", font=("Microsoft YaHei UI", 10)).grid(row=5, column=0, sticky="sw", padx=56, pady=(0, 40))

        right = tk.Frame(self, bg=PAPER, highlightbackground=LINE, highlightthickness=1)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)
        form = ttk.Frame(right, style="Panel.TFrame", padding=(76, 58, 76, 46))
        form.grid(row=0, column=0, sticky="nsew")
        form.columnconfigure(0, weight=1)

        ttk.Label(form, text="欢迎回来", style="Heading.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(form, text="登录后进入你的专属工作区", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(5, 30))
        self._field(form, 2, "邮箱", ttk.Entry(form, textvariable=self.email, style="App.TEntry"))
        self._field(form, 4, "密码", ttk.Entry(form, textvariable=self.password, show="*", style="App.TEntry"))

        signup = ttk.LabelFrame(form, text="注册信息", padding=(12, 8), style="Panel.TFrame")
        signup.grid(row=6, column=0, sticky="ew", pady=(18, 0))
        signup.columnconfigure(1, weight=1)
        ttk.Label(signup, text="账号类型", style="Muted.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=5)
        ttk.Combobox(signup, textvariable=self.role, values=[Role.BUYER.value, Role.ADMIN.value], state="readonly", style="App.TCombobox").grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(signup, text="显示名称", style="Muted.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=5)
        ttk.Entry(signup, textvariable=self.display_name, style="App.TEntry").grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Label(signup, text="联系方式", style="Muted.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=5)
        ttk.Entry(signup, textvariable=self.phone, style="App.TEntry").grid(row=2, column=1, sticky="ew", pady=5)

        buttons = ttk.Frame(form, style="Panel.TFrame")
        buttons.grid(row=7, column=0, sticky="ew", pady=(26, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="登录", style="Primary.TButton", command=self._login).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="注册并登录", style="Secondary.TButton", command=self._register).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ttk.Label(form, text="普通账号可以同时买卖，管理员账号用于审核和系统管理。", style="Muted.TLabel").grid(row=8, column=0, sticky="w", pady=(20, 0))
        ttk.Label(form, text="登录即表示同意《用户协议》和《隐私说明》", style="Muted.TLabel").grid(row=9, column=0, sticky="w", pady=(26, 0))

    @staticmethod
    def _field(parent: ttk.Frame, row: int, label: str, widget: ttk.Widget) -> None:
        ttk.Label(parent, text=label, style="Muted.TLabel").grid(row=row, column=0, sticky="w", pady=(0, 6))
        widget.grid(row=row + 1, column=0, sticky="ew", pady=(0, 14))

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
