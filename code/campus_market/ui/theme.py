"""Tkinter theme shared by the desktop login and workspace views."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


NAVY = "#102f55"
NAVY_DARK = "#0b2340"
NAVY_LIGHT = "#1c4778"
BLUE = "#2f66e8"
BLUE_DARK = "#2255c8"
MINT = "#2dd4c4"
PAPER = "#ffffff"
CANVAS = "#f4f7fb"
TEXT = "#1d2a3d"
MUTED = "#6f7f94"
LINE = "#dbe4ef"
SOFT_BLUE = "#edf3ff"
SOFT_MINT = "#e8faf7"
SOFT_CORAL = "#fff0ec"
CORAL = "#e86650"


def configure(root: tk.Misc) -> ttk.Style:
    """Configure the light navy and blue visual system used by the desktop app."""

    root.configure(background=CANVAS)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("App.TFrame", background=CANVAS)
    style.configure("Panel.TFrame", background=PAPER)
    style.configure("Sidebar.TFrame", background=NAVY)
    style.configure("Title.TLabel", background=CANVAS, foreground=TEXT, font=("Microsoft YaHei UI", 20, "bold"))
    style.configure("Heading.TLabel", background=PAPER, foreground=TEXT, font=("Microsoft YaHei UI", 18, "bold"))
    style.configure("Body.TLabel", background=PAPER, foreground=TEXT, font=("Microsoft YaHei UI", 10))
    style.configure("Muted.TLabel", background=PAPER, foreground=MUTED, font=("Microsoft YaHei UI", 9))
    style.configure("SidebarTitle.TLabel", background=NAVY, foreground=PAPER, font=("Microsoft YaHei UI", 22, "bold"))
    style.configure("SidebarSubtitle.TLabel", background=NAVY, foreground="#b7c9df", font=("Microsoft YaHei UI", 10))
    style.configure("SidebarSection.TLabel", background=NAVY, foreground="#84a5ca", font=("Microsoft YaHei UI", 9, "bold"))
    style.configure("SidebarUser.TLabel", background=NAVY_LIGHT, foreground=PAPER, font=("Microsoft YaHei UI", 10, "bold"), padding=(12, 9))
    style.configure("SidebarNav.TButton", background=NAVY, foreground="#d9e6f5", borderwidth=0, relief="flat", anchor="w", padding=(14, 10), font=("Microsoft YaHei UI", 10))
    style.map("SidebarNav.TButton", background=[("active", NAVY_LIGHT), ("pressed", BLUE_DARK)], foreground=[("active", PAPER), ("pressed", PAPER)])
    style.configure("SidebarNavActive.TButton", background=BLUE, foreground=PAPER, borderwidth=0, relief="flat", anchor="w", padding=(14, 10), font=("Microsoft YaHei UI", 10, "bold"))
    style.map("SidebarNavActive.TButton", background=[("active", BLUE_DARK), ("pressed", BLUE_DARK)])
    style.configure("Primary.TButton", background=BLUE, foreground=PAPER, borderwidth=0, relief="flat", padding=(16, 9), font=("Microsoft YaHei UI", 10, "bold"))
    style.map("Primary.TButton", background=[("active", BLUE_DARK), ("pressed", NAVY)])
    style.configure("Secondary.TButton", background=SOFT_BLUE, foreground=BLUE_DARK, borderwidth=1, bordercolor="#c9d9fa", relief="flat", padding=(13, 8), font=("Microsoft YaHei UI", 9, "bold"))
    style.map("Secondary.TButton", background=[("active", "#dbe7ff"), ("pressed", "#c6d8ff")])
    style.configure("Danger.TButton", background=SOFT_CORAL, foreground=CORAL, borderwidth=1, bordercolor="#ffd0c5", relief="flat", padding=(13, 8), font=("Microsoft YaHei UI", 9, "bold"))
    style.map("Danger.TButton", background=[("active", "#ffe1d9"), ("pressed", "#ffd2c8")])
    style.configure("App.TEntry", fieldbackground="#fbfcff", foreground=TEXT, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, padding=(9, 8), font=("Microsoft YaHei UI", 10))
    style.map("App.TEntry", bordercolor=[("focus", BLUE)], lightcolor=[("focus", BLUE)], darkcolor=[("focus", BLUE)])
    style.configure("App.TCombobox", fieldbackground="#fbfcff", foreground=TEXT, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, padding=(7, 5), font=("Microsoft YaHei UI", 10))
    style.configure("App.TNotebook", background=PAPER, borderwidth=0)
    style.configure("App.TNotebook.Tab", background=SOFT_BLUE, foreground=BLUE_DARK, padding=(13, 7), font=("Microsoft YaHei UI", 9, "bold"))
    style.map("App.TNotebook.Tab", background=[("selected", BLUE)], foreground=[("selected", PAPER)])
    style.configure("Hidden.TNotebook", background=PAPER, borderwidth=0, tabmargins=0)
    style.layout("Hidden.TNotebook.Tab", [])
    style.configure("App.Treeview", background=PAPER, fieldbackground=PAPER, foreground=TEXT, rowheight=31, bordercolor=LINE, font=("Microsoft YaHei UI", 9))
    style.configure("App.Treeview.Heading", background=SOFT_BLUE, foreground=NAVY, relief="flat", font=("Microsoft YaHei UI", 9, "bold"))
    style.map("App.Treeview", background=[("selected", "#dbe7ff")], foreground=[("selected", NAVY)])
    return style


def card(parent: tk.Misc, padding: int = 18) -> ttk.Frame:
    """Create a light card surface with a consistent border."""

    frame = ttk.Frame(parent, style="Panel.TFrame", padding=padding)
    return frame
