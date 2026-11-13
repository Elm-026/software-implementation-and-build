"""角色工作区。"""

from __future__ import annotations

import tkinter as tk
from decimal import Decimal
from tkinter import messagebox, ttk

from ..domain import ProductStatus, Role
from ..services import ConflictError, PermissionDenied, ServiceError
from .theme import BLUE, CANVAS, LINE, MUTED, NAVY, PAPER, SOFT_BLUE, SOFT_MINT, TEXT, card


class Workspace(ttk.Frame):
    """按登录角色组合买家、卖家和管理员操作。"""

    def __init__(self, master: tk.Misc, session, services: dict[str, object], on_logout) -> None:
        super().__init__(master, style="App.TFrame", padding=0)
        self.session = session
        self.services = services
        self.on_logout = on_logout
        self.user = session.user
        self.status = tk.StringVar(value=f"{self.user.display_name or self.user.email} · {self.user.role.value}")
        self._build()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        sidebar = ttk.Frame(self, style="Sidebar.TFrame", padding=(20, 24, 18, 18))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(4, weight=1)
        ttk.Label(sidebar, text="拾光集市", style="SidebarTitle.TLabel").grid(row=0, column=0, sticky="w", padx=8)
        ttk.Label(sidebar, text="校园二手交易工作台", style="SidebarSubtitle.TLabel").grid(row=1, column=0, sticky="w", padx=8, pady=(3, 24))
        user_text = f"{self.user.display_name or self.user.email}\n{('管理员' if self.user.role == Role.ADMIN else '普通用户')} · 可买可卖"
        ttk.Label(sidebar, text=user_text, style="SidebarUser.TLabel", justify="left").grid(row=2, column=0, sticky="ew", padx=2, pady=(0, 24))
        ttk.Label(sidebar, text="工作区", style="SidebarSection.TLabel").grid(row=3, column=0, sticky="w", padx=8, pady=(0, 8))
        self.nav_frame = ttk.Frame(sidebar, style="Sidebar.TFrame")
        self.nav_frame.grid(row=4, column=0, sticky="new")
        ttk.Button(sidebar, text="退出登录", style="SidebarNav.TButton", command=self.on_logout).grid(row=5, column=0, sticky="ew", padx=2, pady=(18, 0))

        content = ttk.Frame(self, style="App.TFrame", padding=(28, 24, 28, 24))
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)
        header = ttk.Frame(content, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        ttk.Label(header, text="校园交易工作台", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=self.status.get(), style="Muted.TLabel").pack(side="right", pady=8)
        self.notebook = ttk.Notebook(content, style="Hidden.TNotebook")
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.tabs = {}
        self._build_buyer()
        self._build_seller()
        if self.user.role == Role.ADMIN:
            self._build_admin()
        if self.tabs:
            self.notebook.select(next(iter(self.tabs.values())))

    def _register_tab(self, key: str, title: str, tab: ttk.Frame) -> None:
        self.tabs[key] = tab
        ttk.Button(self.nav_frame, text=title, style="SidebarNav.TButton", command=lambda: self.notebook.select(tab)).pack(fill="x", pady=2)

    @staticmethod
    def _listbox(parent: tk.Misc, height: int) -> tk.Listbox:
        return tk.Listbox(parent, height=height, bg=PAPER, fg=TEXT, selectbackground="#dbe7ff", selectforeground=NAVY, highlightbackground=LINE, highlightcolor=BLUE, highlightthickness=1, relief="flat", activestyle="none", font=("Microsoft YaHei UI", 10), borderwidth=0)

    def _build_buyer(self) -> None:
        tab = ttk.Frame(self.notebook, style="Panel.TFrame", padding=22)
        self.notebook.add(tab, text="浏览商品")
        self._register_tab("browse", "⌂  浏览商品", tab)
        self.selected_product_id = None
        self.selected_card = None
        ttk.Label(tab, text="发现校园里的好物", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(tab, text="搜索商品、比较价格，找到下一件刚刚好。", style="Muted.TLabel").pack(anchor="w", pady=(4, 16))
        query = card(tab, 14)
        query.pack(fill="x", pady=(0, 14))
        keyword = tk.StringVar()
        category = tk.StringVar()
        minimum = tk.StringVar()
        maximum = tk.StringVar()
        ttk.Label(query, text="关键词", style="Muted.TLabel").pack(side="left", padx=(0, 4))
        ttk.Entry(query, textvariable=keyword, width=15, style="App.TEntry").pack(side="left", padx=(0, 10))
        ttk.Label(query, text="分类", style="Muted.TLabel").pack(side="left", padx=(0, 4))
        ttk.Combobox(query, textvariable=category, values=["", "教材", "数码", "生活", "兴趣", "服饰"], width=10, style="App.TCombobox").pack(side="left", padx=(0, 10))
        for label, variable in (("最低价", minimum), ("最高价", maximum)):
            ttk.Label(query, text=label, style="Muted.TLabel").pack(side="left", padx=(0, 4))
            ttk.Entry(query, textvariable=variable, width=9, style="App.TEntry").pack(side="left", padx=(0, 10))
        ttk.Button(query, text="查询商品", style="Primary.TButton", command=lambda: self._search_buyer(keyword.get(), category.get(), minimum.get(), maximum.get())).pack(side="left", padx=(8, 0))
        self.buyer_count_label = ttk.Label(tab, text="", style="Muted.TLabel")
        self.buyer_count_label.pack(anchor="e", pady=(0, 3))
        self.buyer_grid = tk.Frame(tab, bg=PAPER)
        self.buyer_grid.pack(fill="both", expand=True, pady=(0, 12))
        for column in range(3):
            self.buyer_grid.grid_columnconfigure(column, weight=1, uniform="product-card")
        for row in range(2):
            self.buyer_grid.grid_rowconfigure(row, weight=1)
        actions = ttk.Frame(tab, style="Panel.TFrame")
        actions.pack(fill="x")
        ttk.Button(actions, text="预约选中商品", style="Primary.TButton", command=self._reserve_selected).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="刷新我的预约", style="Secondary.TButton", command=self._refresh_reservations).pack(side="left")
        self._search_buyer("", "", "", "")

    def _search_buyer(self, keyword: str, category: str, minimum: str, maximum: str) -> None:
        try:
            products = self.services["products"].search(self.user.user_id, keyword=keyword, category=category, minimum=minimum, maximum=maximum)
        except ServiceError as exc:
            messagebox.showerror("查询失败", str(exc), parent=self)
            return
        self._render_product_cards(products)

    def _clear_buyer_cards(self) -> None:
        for child in self.buyer_grid.winfo_children():
            child.destroy()
        self.selected_product_id = None
        self.selected_card = None

    def _render_product_cards(self, products) -> None:
        self._clear_buyer_cards()
        self.buyer_count_label.configure(text=f"共 {len(products)} 件商品")
        colors = ("#dfeaff", "#ffecd4", "#e2f7f1", "#f0e7ff", "#e5f0ff", "#fff1d6")
        for index, product in enumerate(products):
            row, column = divmod(index, 3)
            panel = tk.Frame(self.buyer_grid, bg=PAPER, highlightbackground=LINE, highlightthickness=1, bd=0, cursor="hand2")
            panel.grid(row=row, column=column, sticky="nsew", padx=7, pady=7)
            art = tk.Frame(panel, bg=colors[index % len(colors)], height=64)
            art.pack(fill="x", padx=12, pady=(12, 7))
            art.pack_propagate(False)
            tk.Label(art, text=product.category or "校园好物", bg=colors[index % len(colors)], fg=NAVY, font=("Microsoft YaHei UI", 13, "bold")).pack(expand=True)
            tk.Label(panel, text=product.title, bg=PAPER, fg=TEXT, anchor="w", font=("Microsoft YaHei UI", 11, "bold")).pack(fill="x", padx=14, pady=(3, 2))
            info = tk.Frame(panel, bg=PAPER)
            info.pack(fill="x", padx=14, pady=(0, 12))
            tk.Label(info, text=f"¥ {product.price}", bg=PAPER, fg=BLUE, font=("Microsoft YaHei UI", 13, "bold")).pack(side="left")
            tk.Label(info, text=f"{product.condition} · {product.status.value}", bg=PAPER, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(side="right")
            self._bind_product_card(panel, product)

    def _bind_product_card(self, widget: tk.Misc, product) -> None:
        widget.bind("<Button-1>", lambda _event, item=product, panel=widget: self._select_product(item, panel))
        for child in widget.winfo_children():
            self._bind_product_card(child, product)

    def _select_product(self, product, panel: tk.Misc) -> None:
        if self.selected_card is not None:
            self.selected_card.configure(highlightbackground=LINE, highlightthickness=1)
        self.selected_product_id = product.product_id
        self.selected_card = panel
        panel.configure(highlightbackground=BLUE, highlightthickness=2)

    def _reserve_selected(self) -> None:
        if not self.selected_product_id:
            messagebox.showinfo("提示", "请先选择商品", parent=self)
            return
        product_id = self.selected_product_id
        try:
            reservation = self.services["trade"].reserve(self.user.user_id, product_id, f"ui-reserve-{product_id}-{self.user.user_id}")
        except ServiceError as exc:
            messagebox.showerror("预约失败", str(exc), parent=self)
            return
        messagebox.showinfo("预约成功", f"预约编号 {reservation.reservation_id}", parent=self)

    def _refresh_reservations(self) -> None:
        try:
            reservations = self.services["trade"].reservations_for_buyer(self.user.user_id)
        except ServiceError as exc:
            messagebox.showerror("读取失败", str(exc), parent=self)
            return
        self._clear_buyer_cards()
        self.buyer_count_label.configure(text=f"共 {len(reservations)} 条预约")
        for index, item in enumerate(reservations):
            row, column = divmod(index, 3)
            panel = tk.Frame(self.buyer_grid, bg=PAPER, highlightbackground=LINE, highlightthickness=1, bd=0)
            panel.grid(row=row, column=column, sticky="nsew", padx=7, pady=7)
            tk.Label(panel, text="我的预约", bg=SOFT_BLUE, fg=BLUE, font=("Microsoft YaHei UI", 10, "bold"), padx=10, pady=8).pack(fill="x", padx=12, pady=(12, 10))
            tk.Label(panel, text=f"商品 {item.product_id[:12]}", bg=PAPER, fg=TEXT, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", padx=14)
            tk.Label(panel, text=f"预约状态 · {item.status.value}", bg=PAPER, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=14, pady=(5, 14))

    def _build_seller(self) -> None:
        tab = ttk.Frame(self.notebook, style="Panel.TFrame", padding=22)
        self.notebook.add(tab, text="商品管理")
        self._register_tab("seller", "▣  商品管理", tab)
        ttk.Label(tab, text="发布和管理闲置", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(tab, text="写清楚商品信息，审核通过后会出现在集市中。", style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 18))
        fields = {}
        labels = [("标题", "title"), ("描述", "description"), ("分类", "category"), ("价格", "price"), ("成色", "condition"), ("城市", "city"), ("联系方式", "contact")]
        for row, (label, key) in enumerate(labels):
            ttk.Label(tab, text=label, style="Muted.TLabel").grid(row=row + 2, column=0, sticky="nw", pady=5)
            if key == "description":
                widget = tk.Text(tab, height=4, width=50, bg="#fbfcff", fg=TEXT, insertbackground=TEXT, highlightbackground=LINE, highlightcolor=BLUE, highlightthickness=1, relief="flat", font=("Microsoft YaHei UI", 10))
                widget.grid(row=row + 2, column=1, sticky="ew", pady=5)
            else:
                widget = ttk.Entry(tab, width=50, style="App.TEntry")
                widget.grid(row=row + 2, column=1, sticky="ew", pady=5)
            fields[key] = widget
        tab.columnconfigure(1, weight=1)
        actions = ttk.Frame(tab)
        actions.grid(row=len(labels) + 2, column=0, columnspan=2, pady=14)
        ttk.Button(actions, text="保存草稿", style="Primary.TButton", command=lambda: self._save_draft(fields)).pack(side="left", padx=5)
        ttk.Button(actions, text="刷新我的商品", style="Secondary.TButton", command=self._refresh_seller_products).pack(side="left", padx=5)
        self.seller_list = self._listbox(tab, 10)
        self.seller_list.grid(row=len(labels) + 3, column=0, columnspan=2, sticky="nsew", pady=8)
        self.seller_fields = fields
        self._refresh_seller_products()

    @staticmethod
    def _field_value(widget) -> str:
        if isinstance(widget, tk.Text):
            return widget.get("1.0", tk.END).strip()
        return widget.get().strip()

    def _save_draft(self, fields: dict) -> None:
        values = {key: self._field_value(widget) for key, widget in fields.items()}
        try:
            product = self.services["products"].save_draft(self.user.user_id, **values, idempotency_key=f"ui-draft-{values['title']}")
        except ServiceError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)
            return
        messagebox.showinfo("保存成功", f"草稿编号 {product.product_id}", parent=self)
        self._refresh_seller_products()

    def _refresh_seller_products(self) -> None:
        rows = self.services["database"].fetch_all("SELECT product_id, title, status, version FROM products WHERE seller_id = ? ORDER BY updated_at DESC", (self.user.user_id,))
        self.seller_list.delete(0, tk.END)
        for row in rows:
            self.seller_list.insert(tk.END, f"{row['product_id']} | {row['title']} | {row['status']} | v{row['version']}")

    def _build_admin(self) -> None:
        tab = ttk.Frame(self.notebook, style="Panel.TFrame", padding=22)
        self.notebook.add(tab, text="审核与统计")
        self._register_tab("admin", "◇  审核与统计", tab)
        ttk.Label(tab, text="管理员控制台", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(tab, text="审核商品并查看集市运营数据。", style="Muted.TLabel").pack(anchor="w", pady=(4, 16))
        ttk.Button(tab, text="刷新待审核", style="Secondary.TButton", command=self._refresh_reviews).pack(anchor="w")
        self.admin_list = self._listbox(tab, 14)
        self.admin_list.pack(fill="both", expand=True, pady=10)
        actions = ttk.Frame(tab, style="Panel.TFrame")
        actions.pack(fill="x")
        ttk.Button(actions, text="通过", style="Primary.TButton", command=lambda: self._decide_review("APPROVE")).pack(side="left", padx=4)
        ttk.Button(actions, text="驳回", style="Danger.TButton", command=lambda: self._decide_review("REJECT")).pack(side="left", padx=4)
        ttk.Button(actions, text="显示统计", style="Secondary.TButton", command=self._show_statistics).pack(side="left", padx=4)
        self._refresh_reviews()

    def _refresh_reviews(self) -> None:
        try:
            tasks = self.services["reviews"].pending(self.user.user_id)
        except ServiceError as exc:
            messagebox.showerror("读取失败", str(exc), parent=self)
            return
        self.admin_list.delete(0, tk.END)
        for task in tasks:
            self.admin_list.insert(tk.END, f"{task.product_id} | 任务 {task.task_id} | {task.status}")

    def _decide_review(self, decision: str) -> None:
        selection = self.admin_list.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择审核任务", parent=self)
            return
        product_id = self.admin_list.get(selection[0]).split(" | ", 1)[0]
        reason = "" if decision == "APPROVE" else "请补充商品描述和联系方式"
        try:
            self.services["reviews"].decide(self.user.user_id, product_id, decision, reason=reason)
        except ServiceError as exc:
            messagebox.showerror("审核失败", str(exc), parent=self)
            return
        self._refresh_reviews()

    def _show_statistics(self) -> None:
        try:
            summary = self.services["statistics"].admin_summary(self.user.user_id)
        except ServiceError as exc:
            messagebox.showerror("统计失败", str(exc), parent=self)
            return
        messagebox.showinfo("统计", "\n".join(f"{key}: {value}" for key, value in summary.items()), parent=self)
