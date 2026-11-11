"""桌面应用入口。"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from campus_market.infra import Database
from campus_market.services import AuthService, AuditService, ProductService, ReviewService, StatisticsService, TradeService
from campus_market.ui import LoginView, Workspace


class CampusMarketApp(tk.Tk):
    """组装数据库、应用服务和 Tkinter 页面。"""

    def __init__(self) -> None:
        super().__init__()
        self.title("校园二手交易系统")
        self.geometry("900x620")
        self.minsize(760, 520)
        database_path = Path(__file__).resolve().parent.parent / "campus_market.sqlite3"
        self.database = Database(database_path)
        self.services = {
            "database": self.database,
            "auth": AuthService(self.database),
            "products": ProductService(self.database),
            "reviews": ReviewService(self.database),
            "trade": TradeService(self.database),
            "statistics": StatisticsService(self.database),
            "audit": AuditService(self.database),
        }
        self.current_view = None
        self.show_login()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def clear_view(self) -> None:
        if self.current_view is not None:
            self.current_view.destroy()
            self.current_view = None

    def show_login(self) -> None:
        self.clear_view()
        self.current_view = LoginView(self, self.services["auth"], self.show_workspace)
        self.current_view.pack(fill="both", expand=True)

    def show_workspace(self, session) -> None:
        self.clear_view()
        self.current_view = Workspace(self, session, self.services, self.show_login)
        self.current_view.pack(fill="both", expand=True)

    def close(self) -> None:
        self.database.close()
        self.destroy()


if __name__ == "__main__":
    CampusMarketApp().mainloop()
