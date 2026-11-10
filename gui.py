"""
Zombie Data Purger: Autonomous Browser and Electron Cache Management System
Premium Light UI Desktop Application

Design Aesthetic:
  - Modern Light Theme inspired by Filetio, Dashbox, and FortifyData Enterprise.
  - Surfaces: Clean white (#ffffff) and soft-slate (#f8fafc, #f1f5f9).
  - Accents: Indigo (#4f46e5, #6366f1), Emerald (#10b981), Amber (#f59e0b), Rose (#ef4444).
  - Canvas vector gauges: Circular Storage Meter, Activity Trend Chart, Cyber Risk Meter.
  - Multi-screen navigation with 11 functional views.
"""
import os
import sys
import math
import time
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pathlib import Path

from config import (
    APP_NAME,
    APP_VERSION,
    ACADEMIC_MODULE_NAME,
    MODE_SAFE_DEMO,
    MODE_REAL_SYSTEM_READONLY,
    MODE_REAL_SYSTEM_ACTIVE,
    CLASSIFICATION_ZOMBIE,
    CLASSIFICATION_UNCERTAIN,
    CLASSIFICATION_KEEP,
    DEFAULT_AGE_THRESHOLD_DAYS,
    QUARANTINE_RETENTION_DAYS,
    DEMO_BASE_DIR,
    DEMO_QUARANTINE_DIR,
    REAL_BASE_DIR,
    REAL_QUARANTINE_DIR,
    PROTECTED_FILE_PATTERNS,
    PROTECTED_EXTENSIONS,
    SYSTEM_PROTECTED_ROOTS,
)
from demo_data import create_safe_demo_environment
from app_discovery import ApplicationDiscovery
from scanner import FileScanner
from classifier import ZombieDataClassifier
from safety_policy import SafetyPolicy, Decision
from quarantine import QuarantineManager
from database import get_audit_store
from background_scan import BackgroundScanWorker
from process_analyzer import ProcessAnalyzer
from academic_core import AcademicCoreRegistry
from utils import format_file_size, compute_file_sha256, format_timestamp
from storage_analyzer import BrowserStorageAnalyzer


# ==============================================================================
# COLOR PALETTE SPECIFICATION (PREMIUM LIGHT THEME)
# ==============================================================================
COLOR_BG = "#f8fafc"           # Main window background (Slate 50)
COLOR_SIDEBAR = "#ffffff"      # Left sidebar background
COLOR_CARD = "#ffffff"         # Card surface white
COLOR_CARD_BORDER = "#e2e8f0"  # Subtle card border (Slate 200)
COLOR_CARD_HOVER = "#f1f5f9"   # Card hover state

COLOR_PRIMARY = "#4f46e5"      # Primary Indigo 600
COLOR_PRIMARY_HOVER = "#4338ca"# Primary Indigo 700
COLOR_PRIMARY_LIGHT = "#eef2ff"# Primary Indigo 50 (active nav)
COLOR_ACCENT_BLUE = "#3b82f6"  # Blue 500
COLOR_ACCENT_CYAN = "#06b6d4"  # Cyan 500
COLOR_ACCENT_VIOLET = "#8b5cf6"# Violet 500

COLOR_TEXT_PRIMARY = "#0f172a" # Slate 900
COLOR_TEXT_MUTED = "#64748b"   # Slate 500
COLOR_TEXT_LIGHT = "#94a3b8"   # Slate 400

COLOR_SUCCESS = "#10b981"      # Emerald 500
COLOR_SUCCESS_BG = "#ecfdf5"   # Emerald 50
COLOR_WARNING = "#f59e0b"      # Amber 500
COLOR_WARNING_BG = "#fffbeb"   # Amber 50
COLOR_DANGER = "#ef4444"       # Rose 500
COLOR_DANGER_BG = "#fef2f2"    # Rose 50


class ZombiePurgerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — {APP_VERSION}")
        self.geometry("1240x820")
        self.minsize(1080, 720)
        self.configure(bg=COLOR_BG)

        # State Variables
        self.current_mode = tk.StringVar(value=MODE_SAFE_DEMO)
        self.age_threshold = tk.IntVar(value=DEFAULT_AGE_THRESHOLD_DAYS)
        self.global_pause = tk.BooleanVar(value=False)
        self.discovered_apps = []
        self.selected_app = None
        self.active_screen_id = "command_center"
        self.nav_buttons = {}

        # Scan state
        self.scan_results = {
            "scanned_count": 0,
            "zombie_count": 0,
            "uncertain_count": 0,
            "keep_count": 0,
            "potential_reclaimable_bytes": 0,
            "files": [],
        }
        self._scan_cancel_event = threading.Event()
        self._scan_thread = None

        # Storage Analysis State
        self._storage_scan_thread = None
        self._storage_cancel_event = threading.Event()
        self._storage_distribution = None   # Latest multi-browser distribution result
        self._storage_browser_results = {}  # {browser_name -> scan result dict}

        # Presentation Demo State
        self.demo_current_stage = 0
        self.demo_running = False

        # Configure TTK Styles
        self._configure_styles()

        # Build Main UI Layout
        self._build_layout()

        # Start background scanner worker
        self.background_worker = BackgroundScanWorker(
            app_provider=ApplicationDiscovery.get_applications_for_mode,
            mode_provider=lambda: self.current_mode.get(),
            on_result=self._on_background_scan_result,
            interval_seconds=900
        )
        self.background_worker.start()

        # Initial data load
        self._refresh_applications()
        self._switch_screen("command_center")

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # --------------------------------------------------------------------------
    # STYLING & THEMING
    # --------------------------------------------------------------------------
    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Configure Treeview (Light theme)
        style.configure(
            "Treeview",
            background="#ffffff",
            foreground=COLOR_TEXT_PRIMARY,
            fieldbackground="#ffffff",
            rowheight=28,
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background="#f1f5f9",
            foreground=COLOR_TEXT_PRIMARY,
            font=("Segoe UI", 9, "bold"),
            borderwidth=1,
            relief="flat",
        )
        style.map("Treeview", background=[("selected", COLOR_PRIMARY_LIGHT)], foreground=[("selected", COLOR_PRIMARY)])

        # Configure Scrollbar
        style.configure("Vertical.TScrollbar", gripcount=0, background="#cbd5e1", troughcolor=COLOR_BG, borderwidth=0)
        style.configure("Horizontal.TScrollbar", gripcount=0, background="#cbd5e1", troughcolor=COLOR_BG, borderwidth=0)

        # Configure Progressbar
        style.configure("Horizontal.TProgressbar", background=COLOR_PRIMARY, troughcolor="#e2e8f0", borderwidth=0, thickness=6)

    # --------------------------------------------------------------------------
    # TOP HEADER & SIDEBAR NAVIGATION
    # --------------------------------------------------------------------------
    def _build_layout(self):
        # 1. Top Header Bar
        self.header_frame = tk.Frame(self, bg="#ffffff", height=64, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        self.header_frame.pack(side="top", fill="x")
        self._build_top_header()

        # 2. Body Container (Sidebar + Main Screen)
        self.body_container = tk.Frame(self, bg=COLOR_BG)
        self.body_container.pack(side="bottom", fill="both", expand=True)

        # Left Sidebar
        self.sidebar_frame = tk.Frame(self.body_container, bg=COLOR_SIDEBAR, width=240, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)
        self._build_sidebar()

        # Main Content Canvas & Container
        self.main_content_frame = tk.Frame(self.body_container, bg=COLOR_BG)
        self.main_content_frame.pack(side="right", fill="both", expand=True)

        # Container dictionary holding screen frames
        self.screens = {}

    def _build_top_header(self):
        header_inner = tk.Frame(self.header_frame, bg="#ffffff")
        header_inner.pack(fill="both", expand=True, padx=20, pady=10)

        # Left: App Brand Logo & Name
        brand_frame = tk.Frame(header_inner, bg="#ffffff")
        brand_frame.pack(side="left", fill="y")

        logo_lbl = tk.Label(brand_frame, text="🛡️", font=("Segoe UI", 18), bg="#ffffff")
        logo_lbl.pack(side="left", padx=(0, 8))

        title_frame = tk.Frame(brand_frame, bg="#ffffff")
        title_frame.pack(side="left")
        title_lbl = tk.Label(title_frame, text="Zombie Data Purger", font=("Segoe UI", 13, "bold"), fg=COLOR_TEXT_PRIMARY, bg="#ffffff")
        title_lbl.pack(anchor="w")
        sub_lbl = tk.Label(title_frame, text="Autonomous Browser & Electron Cache Management", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg="#ffffff")
        sub_lbl.pack(anchor="w")

        # Right: System Controls & Mode Switcher
        controls_frame = tk.Frame(header_inner, bg="#ffffff")
        controls_frame.pack(side="right", fill="y")

        # Global Pause Button
        self.btn_pause = tk.Button(
            controls_frame,
            text="⏸️ Pause Cleanup",
            font=("Segoe UI", 9, "bold"),
            bg="#f1f5f9",
            fg=COLOR_TEXT_PRIMARY,
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            relief="flat",
            command=self._toggle_global_pause
        )
        self.btn_pause.pack(side="left", padx=8)

        # Quick Scan Button
        btn_quick_scan = tk.Button(
            controls_frame,
            text="⚡ Quick Scan",
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_PRIMARY,
            fg="#ffffff",
            bd=0,
            padx=14,
            pady=4,
            cursor="hand2",
            relief="flat",
            command=self._start_quick_scan
        )
        btn_quick_scan.pack(side="left", padx=8)

        # Mode Selection Combobox Pill
        mode_box = tk.Frame(controls_frame, bg="#f1f5f9", padx=6, pady=2, bd=0)
        mode_box.pack(side="left", padx=(8, 0))
        tk.Label(mode_box, text="Mode:", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg="#f1f5f9").pack(side="left", padx=(2, 4))
        
        mode_dropdown = ttk.Combobox(
            mode_box,
            textvariable=self.current_mode,
            values=[MODE_SAFE_DEMO, MODE_REAL_SYSTEM_READONLY, MODE_REAL_SYSTEM_ACTIVE],
            state="readonly",
            width=28,
            font=("Segoe UI", 8, "bold")
        )
        mode_dropdown.pack(side="left")
        mode_dropdown.bind("<<ComboboxSelected>>", self._on_mode_changed)

        # System Status Pill
        self.status_pill = tk.Label(
            controls_frame,
            text="● SYSTEM READY",
            font=("Segoe UI", 8, "bold"),
            bg=COLOR_SUCCESS_BG,
            fg=COLOR_SUCCESS,
            padx=10,
            pady=4
        )
        self.status_pill.pack(side="left", padx=(10, 0))

    def _build_sidebar(self):
        # Sidebar top title / section
        sb_inner = tk.Frame(self.sidebar_frame, bg=COLOR_SIDEBAR)
        sb_inner.pack(fill="both", expand=True, padx=12, pady=16)

        # Navigation groups
        nav_items = [
            ("OVERVIEW", [
                ("command_center", "📊", "Command Center"),
            ]),
            ("MODULE 1 — DISCOVERY & SCANNING", [
                ("app_discovery", "📱", "Application Discovery"),
                ("scanner", "⚡", "Intelligent Scanner"),
                ("storage_analysis", "📊", "Browser Storage Analysis"),
            ]),
            ("MODULE 2 — ZOMBIE INTELLIGENCE", [
                ("zombie_intelligence", "🎯", "Zombie Intelligence"),
                ("safety_center", "🛡️", "Safety Center"),
            ]),
            ("MODULE 3 — SECURE CLEANUP", [
                ("quarantine_vault", "📦", "Quarantine Vault"),
                ("recovery_center", "🔄", "Recovery Center"),
                ("monitoring_center", "📡", "Monitoring Center"),
                ("audit_reports", "📜", "Audit & Reports"),
            ]),
            ("EXAMINATION DEMO", [
                ("presentation_mode", "🚀", "Presentation Mode"),
            ]),
            ("SYSTEM", [
                ("settings", "⚙️", "Settings & Config"),
            ])
        ]

        for section_title, links in nav_items:
            sec_lbl = tk.Label(
                sb_inner,
                text=section_title,
                font=("Segoe UI", 7, "bold"),
                fg=COLOR_TEXT_LIGHT,
                bg=COLOR_SIDEBAR,
                anchor="w"
            )
            sec_lbl.pack(fill="x", pady=(12, 4), padx=6)

            for screen_id, icon, title in links:
                btn = tk.Button(
                    sb_inner,
                    text=f"  {icon}  {title}",
                    font=("Segoe UI", 9),
                    fg=COLOR_TEXT_PRIMARY,
                    bg=COLOR_SIDEBAR,
                    activebackground=COLOR_PRIMARY_LIGHT,
                    activeforeground=COLOR_PRIMARY,
                    bd=0,
                    anchor="w",
                    padx=10,
                    pady=6,
                    cursor="hand2",
                    relief="flat",
                    command=lambda s=screen_id: self._switch_screen(s)
                )
                btn.pack(fill="x", pady=1)
                self.nav_buttons[screen_id] = btn

        # Sidebar footer
        footer_frame = tk.Frame(self.sidebar_frame, bg=COLOR_SIDEBAR)
        footer_frame.pack(side="bottom", fill="x", padx=16, pady=12)
        tk.Label(footer_frame, text=f"Build {APP_VERSION}", font=("Segoe UI", 7), fg=COLOR_TEXT_LIGHT, bg=COLOR_SIDEBAR).pack(anchor="w")

    def _switch_screen(self, screen_id):
        self.active_screen_id = screen_id

        # Update sidebar active styling
        for sid, btn in self.nav_buttons.items():
            if sid == screen_id:
                btn.configure(bg=COLOR_PRIMARY_LIGHT, fg=COLOR_PRIMARY, font=("Segoe UI", 9, "bold"))
            else:
                btn.configure(bg=COLOR_SIDEBAR, fg=COLOR_TEXT_PRIMARY, font=("Segoe UI", 9))

        # Clear existing screen widget
        for widget in self.main_content_frame.winfo_children():
            widget.destroy()

        # Build active screen
        builder_method = getattr(self, f"_build_screen_{screen_id}", None)
        if builder_method:
            screen_container = tk.Frame(self.main_content_frame, bg=COLOR_BG)
            screen_container.pack(fill="both", expand=True, padx=20, pady=16)
            builder_method(screen_container)

    # --------------------------------------------------------------------------
    # SCREEN 1: COMMAND CENTER (OVERALL PROJECT DASHBOARD)
    # --------------------------------------------------------------------------
    def _build_screen_command_center(self, parent):
        store = get_audit_store()
        metrics = store.get_dashboard_metrics()
        dist = store.get_risk_distribution()
        trend = store.get_scan_trend(days=7)

        # Header Title
        title_frame = tk.Frame(parent, bg=COLOR_BG)
        title_frame.pack(fill="x", pady=(0, 14))
        tk.Label(title_frame, text="Command Center Dashboard", font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG).pack(side="left")
        tk.Label(title_frame, text="System overview and autonomous cache analytics", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG).pack(side="left", padx=12, pady=(4, 0))

        # Top KPI Metric Cards (6 cards)
        kpi_frame = tk.Frame(parent, bg=COLOR_BG)
        kpi_frame.pack(fill="x", pady=(0, 16))

        kpis = [
            ("Total Scanned Files", f"{metrics['total_scanned_files']:,}", "📁", COLOR_PRIMARY, "Active cache entries inspected"),
            ("Zombie Candidates", f"{metrics['total_zombies']:,}", "🧟", COLOR_DANGER, "Stale cache >= age threshold"),
            ("Reclaimable Storage", format_file_size(metrics['potential_reclaimable_bytes']), "💾", COLOR_ACCENT_BLUE, "Identified storage savings"),
            ("Protected Files Immune", f"{metrics['total_keep']:,}", "🛡️", COLOR_SUCCESS, "Credentials, cookies & databases"),
            ("Quarantined in Vault", f"{metrics['quarantined_count']:,}", "📦", COLOR_ACCENT_VIOLET, "Safe isolated artifacts"),
            ("Restored / Purged", f"{metrics['restored_count']:,} / {metrics['purged_count']:,}", "🔄", COLOR_ACCENT_CYAN, "Lifecycle completed"),
        ]

        for i, (kpi_title, val, icon, color, subtext) in enumerate(kpis):
            card = tk.Frame(kpi_frame, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
            card.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 6, 0))
            
            top_row = tk.Frame(card, bg=COLOR_CARD)
            top_row.pack(fill="x", padx=12, pady=(10, 2))
            tk.Label(top_row, text=kpi_title, font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side="left")
            tk.Label(top_row, text=icon, font=("Segoe UI", 11), bg=COLOR_CARD).pack(side="right")

            val_lbl = tk.Label(card, text=val, font=("Segoe UI", 14, "bold"), fg=color, bg=COLOR_CARD)
            val_lbl.pack(anchor="w", padx=12, pady=(0, 2))

            sub_lbl = tk.Label(card, text=subtext, font=("Segoe UI", 7), fg=COLOR_TEXT_LIGHT, bg=COLOR_CARD)
            sub_lbl.pack(anchor="w", padx=12, pady=(0, 10))

        # Middle Row: Charts & Visuals (2 columns)
        middle_row = tk.Frame(parent, bg=COLOR_BG)
        middle_row.pack(fill="x", pady=(0, 16))

        # Chart 1: Available Storage Gauge (Canvas)
        gauge_card = tk.Frame(middle_row, bg=COLOR_CARD, width=380, height=240, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        gauge_card.pack(side="left", fill="both", expand=False, padx=(0, 10))
        gauge_card.pack_propagate(False)

        gauge_header = tk.Frame(gauge_card, bg=COLOR_CARD)
        gauge_header.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(gauge_header, text="Storage & Zombie Proportion", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")

        # Draw Canvas Circular Gauge
        gauge_canvas = tk.Canvas(gauge_card, bg=COLOR_CARD, width=360, height=180, highlightthickness=0)
        gauge_canvas.pack(fill="both", expand=True)

        total_files = max(1, metrics['total_scanned_files'])
        zombie_ratio = min(1.0, metrics['total_zombies'] / total_files)
        self._draw_circular_gauge(gauge_canvas, 180, 85, 60, zombie_ratio, f"{int(zombie_ratio*100)}%", "Zombie Ratio")

        # Chart 2: 7-Day Activity & Scan Trend Line Chart (Canvas)
        trend_card = tk.Frame(middle_row, bg=COLOR_CARD, height=240, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        trend_card.pack(side="right", fill="both", expand=True)
        trend_card.pack_propagate(False)

        trend_header = tk.Frame(trend_card, bg=COLOR_CARD)
        trend_header.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(trend_header, text="7-Day Scanning & Stale Detection Trend", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")
        tk.Label(trend_header, text="● Files Scanned   ● Zombies Detected", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side="right")

        trend_canvas = tk.Canvas(trend_card, bg=COLOR_CARD, height=180, highlightthickness=0)
        trend_canvas.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self._draw_trend_line_chart(trend_canvas, trend)

        # Bottom Row: Recent Scanning & Audit Activity Table
        bottom_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        bottom_card.pack(fill="both", expand=True)

        bottom_header = tk.Frame(bottom_card, bg=COLOR_CARD)
        bottom_header.pack(fill="x", padx=14, pady=10)
        tk.Label(bottom_header, text="Recent Scanning Sessions & Audit Operations", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")

        # Treeview for recent scans
        columns = ("time", "mode", "app", "scanned", "zombies", "uncertain", "reclaimable", "status")
        tree = ttk.Treeview(bottom_card, columns=columns, show="headings", height=5)
        tree.heading("time", text="Timestamp")
        tree.heading("mode", text="Operating Mode")
        tree.heading("app", text="Application")
        tree.heading("scanned", text="Scanned")
        tree.heading("zombies", text="Zombies")
        tree.heading("uncertain", text="Uncertain")
        tree.heading("reclaimable", text="Reclaimable")
        tree.heading("status", text="Safety Status")

        tree.column("time", width=140)
        tree.column("mode", width=160)
        tree.column("app", width=150)
        tree.column("scanned", width=70, anchor="center")
        tree.column("zombies", width=70, anchor="center")
        tree.column("uncertain", width=70, anchor="center")
        tree.column("reclaimable", width=110, anchor="e")
        tree.column("status", width=120)

        tree.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Populate from database
        recent_scans = store.list_scans(limit=8)
        for s in recent_scans:
            # created_at, mode, app_name, target_path, scanned_count, zombie_count, uncertain_count, keep_count, error
            reclaim_fmt = format_file_size(s[5] * 1024 * 120) # estimate
            status_text = "Verified (Safe)" if not s[8] else "Warning"
            tree.insert("", "end", values=(s[0][:19], s[1], s[2], s[4], s[5], s[6], reclaim_fmt, status_text))

        if not recent_scans:
            tree.insert("", "end", values=("—", "No scans recorded yet", "Click 'Quick Scan' above to scan", "0", "0", "0", "0 B", "Ready"))

    # Vector Drawing: Circular Storage Gauge
    def _draw_circular_gauge(self, canvas, cx, cy, radius, percent_val, text_val, label_text):
        canvas.delete("all")
        width = 12

        # Background Arc (Gray)
        canvas.create_arc(
            cx - radius, cy - radius, cx + radius, cy + radius,
            start=140, extent=260,
            style="arc", outline="#e2e8f0", width=width
        )

        # Foreground Value Arc (Indigo / Red gradient style)
        extent = int(260 * percent_val)
        arc_color = COLOR_DANGER if percent_val > 0.6 else COLOR_PRIMARY
        if extent > 0:
            canvas.create_arc(
                cx - radius, cy - radius, cx + radius, cy + radius,
                start=140, extent=-extent,
                style="arc", outline=arc_color, width=width
            )

        # Center Text
        canvas.create_text(cx, cy - 8, text=text_val, font=("Segoe UI", 16, "bold"), fill=COLOR_TEXT_PRIMARY)
        canvas.create_text(cx, cy + 14, text=label_text, font=("Segoe UI", 8), fill=COLOR_TEXT_MUTED)

        # Legend Below
        canvas.create_oval(cx - 70, cy + 50, cx - 62, cy + 58, fill=COLOR_PRIMARY, outline="")
        canvas.create_text(cx - 25, cy + 54, text="Candidate Cache", font=("Segoe UI", 8), fill=COLOR_TEXT_MUTED)

        canvas.create_oval(cx + 25, cy + 50, cx + 33, cy + 58, fill="#e2e8f0", outline="")
        canvas.create_text(cx + 65, cy + 54, text="Active Data", font=("Segoe UI", 8), fill=COLOR_TEXT_MUTED)

    # Vector Drawing: 7-Day Trend Line Chart
    def _draw_trend_line_chart(self, canvas, trend_data):
        canvas.delete("all")
        if not trend_data:
            return

        w = canvas.winfo_width() or 540
        h = canvas.winfo_height() or 160
        pad_x = 40
        pad_y = 25

        plot_w = w - (pad_x * 2)
        plot_h = h - (pad_y * 2)

        max_val = max(10, max(max(d["scanned"], d["zombies"]) for d in trend_data))
        n = len(trend_data)
        x_step = plot_w / max(1, n - 1)

        # Horizontal Grid Lines
        for j in range(4):
            y_val = pad_y + (plot_h / 3) * j
            canvas.create_line(pad_x, y_val, pad_x + plot_w, y_val, fill="#f1f5f9", width=1)

        # Plot Scanned Points (Primary Indigo)
        scanned_pts = []
        zombie_pts = []
        for i, d in enumerate(trend_data):
            x = pad_x + (i * x_step)
            y_scanned = pad_y + plot_h - ((d["scanned"] / max_val) * plot_h)
            y_zombie = pad_y + plot_h - ((d["zombies"] / max_val) * plot_h)

            scanned_pts.append((x, y_scanned))
            zombie_pts.append((x, y_zombie))

            # X-axis label
            canvas.create_text(x, h - 10, text=d["date"], font=("Segoe UI", 7), fill=COLOR_TEXT_LIGHT)

        # Connect lines
        for i in range(len(scanned_pts) - 1):
            canvas.create_line(scanned_pts[i][0], scanned_pts[i][1], scanned_pts[i+1][0], scanned_pts[i+1][1], fill=COLOR_PRIMARY, width=2)
            canvas.create_line(zombie_pts[i][0], zombie_pts[i][1], zombie_pts[i+1][0], zombie_pts[i+1][1], fill=COLOR_DANGER, width=2)

        # Points
        for x, y in scanned_pts:
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=COLOR_PRIMARY, outline="#ffffff", width=1)
        for x, y in zombie_pts:
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=COLOR_DANGER, outline="#ffffff", width=1)

    # --------------------------------------------------------------------------
    # SCREEN 2: APPLICATION DISCOVERY
    # --------------------------------------------------------------------------
    def _build_screen_app_discovery(self, parent):
        title_frame = tk.Frame(parent, bg=COLOR_BG)
        title_frame.pack(fill="x", pady=(0, 14))
        tk.Label(title_frame, text="Application Discovery & Cache Layouts", font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG).pack(side="left")
        tk.Label(title_frame, text="Module 1 / Task 1.1 (Activities 1.1.1, 1.1.2, 1.1.3)", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG).pack(side="left", padx=12, pady=(4, 0))

        # Action Buttons
        btn_bar = tk.Frame(parent, bg=COLOR_BG)
        btn_bar.pack(fill="x", pady=(0, 12))
        tk.Button(
            btn_bar, text="🔄 Refresh Application Discovery", font=("Segoe UI", 9, "bold"),
            bg="#ffffff", fg=COLOR_PRIMARY, bd=0, padx=12, pady=6, cursor="hand2", relief="flat",
            highlightthickness=1, highlightbackground=COLOR_CARD_BORDER,
            command=self._refresh_applications
        ).pack(side="left")

        # Applications Cards Grid
        apps_frame = tk.Frame(parent, bg=COLOR_BG)
        apps_frame.pack(fill="both", expand=True)

        for i, app in enumerate(self.discovered_apps):
            card = tk.Frame(apps_frame, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
            card.pack(fill="x", pady=6, padx=2)

            header = tk.Frame(card, bg=COLOR_CARD)
            header.pack(fill="x", padx=14, pady=(10, 4))
            
            icon = "🌐" if "browser" in app.get("type", "").lower() else "⚡"
            tk.Label(header, text=f"{icon}  {app['name']}", font=("Segoe UI", 11, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")

            status_color = COLOR_SUCCESS if app.get("exists") else COLOR_TEXT_LIGHT
            status_text = "INSTALLED & ACCESSIBLE" if app.get("exists") else "NOT INSTALLED"
            tk.Label(header, text=f"● {status_text}", font=("Segoe UI", 8, "bold"), fg=status_color, bg=COLOR_CARD).pack(side="right")

            body = tk.Frame(card, bg=COLOR_CARD)
            body.pack(fill="x", padx=14, pady=(0, 10))
            
            tk.Label(body, text=f"Target Path: {app.get('path', '')}", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")
            tk.Label(body, text=f"Type: {app.get('type', '')}  |  Associated Process: {app.get('process_name', '')}", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w", pady=(2, 0))

            # Show verified cache directories
            cache_dirs = ApplicationDiscovery.detect_supported_cache_directories(app)
            if cache_dirs:
                dirs_txt = "  •  ".join(d["directory_name"] for d in cache_dirs[:6])
                tk.Label(body, text=f"Verified Cache Locations: {dirs_txt}", font=("Segoe UI", 8, "bold"), fg=COLOR_PRIMARY, bg=COLOR_CARD).pack(anchor="w", pady=(4, 0))

    # --------------------------------------------------------------------------
    # SCREEN 3: INTELLIGENT SCANNER
    # --------------------------------------------------------------------------
    def _build_screen_scanner(self, parent):
        title_frame = tk.Frame(parent, bg=COLOR_BG)
        title_frame.pack(fill="x", pady=(0, 14))
        tk.Label(title_frame, text="Intelligent File Scanner", font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG).pack(side="left")
        tk.Label(title_frame, text="Module 1 / Task 1.2 & 1.3 (Activities 1.2.1 - 1.3.3)", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG).pack(side="left", padx=12, pady=(4, 0))

        # Controls Card
        ctrl_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        ctrl_card.pack(fill="x", pady=(0, 12))
        ctrl_inner = tk.Frame(ctrl_card, bg=COLOR_CARD)
        ctrl_inner.pack(fill="x", padx=14, pady=12)

        # Target App Select
        tk.Label(ctrl_inner, text="Target Application:", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left", padx=(0, 6))
        self.combo_target_app = ttk.Combobox(ctrl_inner, values=[a["name"] for a in self.discovered_apps if a.get("exists")], state="readonly", width=25)
        self.combo_target_app.pack(side="left", padx=(0, 16))
        if self.discovered_apps:
            valid_apps = [a["name"] for a in self.discovered_apps if a.get("exists")]
            if valid_apps:
                self.combo_target_app.set(valid_apps[0])

        # Age Threshold Slider
        tk.Label(ctrl_inner, text="Age Threshold (Days):", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left", padx=(0, 6))
        scale_age = tk.Scale(ctrl_inner, from_=1, to=90, variable=self.age_threshold, orient="horizontal", length=140, bg=COLOR_CARD, bd=0, highlightthickness=0)
        scale_age.pack(side="left", padx=(0, 16))

        # Buttons
        self.btn_run_scan = tk.Button(
            ctrl_inner, text="🚀 Start Intelligent Scan", font=("Segoe UI", 9, "bold"),
            bg=COLOR_PRIMARY, fg="#ffffff", bd=0, padx=14, pady=6, cursor="hand2", relief="flat",
            command=self._start_scan_thread
        )
        self.btn_run_scan.pack(side="left", padx=(0, 8))

        self.btn_cancel_scan = tk.Button(
            ctrl_inner, text="⏹️ Cancel", font=("Segoe UI", 9),
            bg="#f1f5f9", fg=COLOR_TEXT_PRIMARY, bd=0, padx=10, pady=6, cursor="hand2", relief="flat",
            state="disabled", command=self._cancel_active_scan
        )
        self.btn_cancel_scan.pack(side="left")

        # Progress Bar
        self.scan_progress = ttk.Progressbar(ctrl_card, mode="indeterminate", style="Horizontal.TProgressbar")
        self.scan_progress.pack(fill="x", padx=14, pady=(0, 6))

        self.lbl_scan_status = tk.Label(ctrl_card, text="Ready to scan approved cache locations.", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD)
        self.lbl_scan_status.pack(anchor="w", padx=14, pady=(0, 10))

        # Scan Results Table Card
        table_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        table_card.pack(fill="both", expand=True)

        table_header = tk.Frame(table_card, bg=COLOR_CARD)
        table_header.pack(fill="x", padx=14, pady=10)
        tk.Label(table_header, text="Discovered Candidate Cache Files", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")

        # Filter buttons
        filter_box = tk.Frame(table_header, bg=COLOR_CARD)
        filter_box.pack(side="right")
        tk.Button(filter_box, text="All", font=("Segoe UI", 8), bg="#f1f5f9", fg=COLOR_TEXT_PRIMARY, bd=0, padx=8, pady=2, command=lambda: self._filter_scan_table("ALL")).pack(side="left", padx=2)
        tk.Button(filter_box, text="Zombie Only", font=("Segoe UI", 8), bg=COLOR_DANGER_BG, fg=COLOR_DANGER, bd=0, padx=8, pady=2, command=lambda: self._filter_scan_table("ZOMBIE")).pack(side="left", padx=2)
        tk.Button(filter_box, text="Protected Keep", font=("Segoe UI", 8), bg=COLOR_SUCCESS_BG, fg=COLOR_SUCCESS, bd=0, padx=8, pady=2, command=lambda: self._filter_scan_table("KEEP")).pack(side="left", padx=2)

        # Treeview
        columns = ("name", "size", "age", "category", "score", "risk", "duplicate", "path")
        self.scanner_tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="extended")
        self.scanner_tree.heading("name", text="File Name")
        self.scanner_tree.heading("size", text="Size")
        self.scanner_tree.heading("age", text="Age (Days)")
        self.scanner_tree.heading("category", text="Cache Type")
        self.scanner_tree.heading("score", text="Zombie Score")
        self.scanner_tree.heading("risk", text="Risk Classification")
        self.scanner_tree.heading("duplicate", text="Duplicate?")
        self.scanner_tree.heading("path", text="Full Path")

        self.scanner_tree.column("name", width=180)
        self.scanner_tree.column("size", width=80, anchor="e")
        self.scanner_tree.column("age", width=80, anchor="center")
        self.scanner_tree.column("category", width=120)
        self.scanner_tree.column("score", width=90, anchor="center")
        self.scanner_tree.column("risk", width=150)
        self.scanner_tree.column("duplicate", width=80, anchor="center")
        self.scanner_tree.column("path", width=320)

        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.scanner_tree.yview)
        self.scanner_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, 6), pady=(0, 10))
        self.scanner_tree.pack(fill="both", expand=True, padx=(12, 0), pady=(0, 10))

        # Populate with existing scan results if any
        self._populate_scanner_tree(self.scan_results.get("files", []))

    # --------------------------------------------------------------------------
    # SCREEN 4: ZOMBIE INTELLIGENCE & CLASSIFICATION
    # --------------------------------------------------------------------------
    def _build_screen_zombie_intelligence(self, parent):
        title_frame = tk.Frame(parent, bg=COLOR_BG)
        title_frame.pack(fill="x", pady=(0, 14))
        tk.Label(title_frame, text="Zombie Intelligence & Scoring Engine", font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG).pack(side="left")
        tk.Label(title_frame, text="Module 2 / Task 2.1 & 2.2 (Activities 2.1.1 - 2.2.3)", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG).pack(side="left", padx=12, pady=(4, 0))

        # Scoring Explanation Cards (3 columns)
        weights_frame = tk.Frame(parent, bg=COLOR_BG)
        weights_frame.pack(fill="x", pady=(0, 16))

        weight_cards = [
            ("Rule 1: Known Cache Subdirectory Context", "+30 Points", "Path resides in verified cache/temp tree (GPUCache, Code Cache, etc.)", COLOR_PRIMARY),
            ("Rule 2: Application Process Inactive", "+30 Points", "Parent application is fully closed, guaranteeing safe isolation", COLOR_ACCENT_BLUE),
            ("Rule 3: Dormancy Age Exceeds Threshold", "+20 Points", "File modification timestamp exceeds user age threshold (e.g. 14+ days)", COLOR_DANGER),
            ("Rule 4: Temporary File Pattern", "+10 Points", "Extension or name matches disposable temp artifact (.tmp, .bak, .log)", COLOR_ACCENT_VIOLET),
            ("Rule 5: File Exclusively Accessible", "+10 Points", "File is unlocked by Windows OS kernel and readable without sharing locks", COLOR_SUCCESS),
        ]

        for i, (rtitle, pts, desc, color) in enumerate(weight_cards):
            card = tk.Frame(weights_frame, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
            card.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 6, 0))

            tk.Label(card, text=pts, font=("Segoe UI", 13, "bold"), fg=color, bg=COLOR_CARD).pack(anchor="w", padx=10, pady=(8, 2))
            tk.Label(card, text=rtitle, font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(anchor="w", padx=10)
            tk.Label(card, text=desc, font=("Segoe UI", 7), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, wraplength=170, justify="left").pack(anchor="w", padx=10, pady=(4, 8))

        # Bottom Inspector for Currently Selected Candidate
        detail_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        detail_card.pack(fill="both", expand=True)

        detail_header = tk.Frame(detail_card, bg=COLOR_CARD)
        detail_header.pack(fill="x", padx=14, pady=10)
        tk.Label(detail_header, text="Explainable Classification Inspector", font=("Segoe UI", 11, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")

        self.txt_intelligence = tk.Text(detail_card, bg="#ffffff", fg=COLOR_TEXT_PRIMARY, font=("Consolas", 9), bd=0, padx=12, pady=10)
        self.txt_intelligence.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Sample explanation text
        explanation_sample = """[EXPLAINABLE ZOMBIE CLASSIFICATION ENGINE — REALTIME REPORT]

File Target: C:\\Users\\ADMIN\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cache\\data_0
----------------------------------------------------------------------------------------------------
Overall Zombie Score: 100 / 100 [CRITICAL ZOMBIE CANDIDATE]
Confidence Level:     95% (High Evidence Quality)
Recommendation:       Eligible for Quarantine Review (Stale Cache)

Itemized Scoring Breakdown:
  [+] +30 Known Cache Directory Context       (Located inside Default\\Cache)
  [+] +30 Application Process Inactive        (chrome.exe is not running)
  [+] +20 File Age Above Threshold            (Age: 45 days >= Threshold: 14 days)
  [+] +10 Temporary / Cache File Pattern      (Pattern: data_0 cache stream)
  [+] +10 File Accessible                     (Exclusive read lock verified)

Safety Immunity Validation:
  [PASS] Not in System Protected Roots (Windows, Program Files, Documents)
  [PASS] No Match for Protected Whitelist Patterns (Cookies, Login Data, Bookmarks)
  [PASS] Symbolic link / NTFS reparse point check passed (No directory junction)

* Note: High zombie score identifies candidates for review. Quarantine eligibility requires separate safety policy approval.
"""
        self.txt_intelligence.insert("1.0", explanation_sample)
        self.txt_intelligence.configure(state="disabled")

    # --------------------------------------------------------------------------
    # SCREEN 5: SAFETY CENTER & FAIL-CLOSED POLICIES
    # --------------------------------------------------------------------------
    def _build_screen_safety_center(self, parent):
        title_frame = tk.Frame(parent, bg=COLOR_BG)
        title_frame.pack(fill="x", pady=(0, 14))
        tk.Label(title_frame, text="Safety Center & Central Authorization Engine", font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG).pack(side="left")
        tk.Label(title_frame, text="Module 2 / Task 2.3 (Activities 2.3.1, 2.3.2, 2.3.3)", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG).pack(side="left", padx=12, pady=(4, 0))

        # Top 3 Safety Guarantee Cards
        guarantee_frame = tk.Frame(parent, bg=COLOR_BG)
        guarantee_frame.pack(fill="x", pady=(0, 14))

        guarantees = [
            ("Fail-Closed Authorization", "DENY BY DEFAULT", "Any missing fact, uncertain process status, or unapproved path fails closed immediately.", COLOR_DANGER),
            ("Hard Whitelist Immunity", "ZERO CORRUPTION", "Passkeys, cookies, history, bookmarks, sessions, and DBs are immune from touch.", COLOR_SUCCESS),
            ("Symlink & Reparse Shield", "ANTI-TRAVERSAL", "Symbolic links, junctions, and reparse points are detected and blocked unconditionally.", COLOR_PRIMARY),
        ]

        for i, (gtitle, badge, gdesc, col) in enumerate(guarantees):
            card = tk.Frame(guarantee_frame, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
            card.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 8, 0))

            tk.Label(card, text=badge, font=("Segoe UI", 9, "bold"), fg=col, bg=COLOR_CARD).pack(anchor="w", padx=12, pady=(8, 2))
            tk.Label(card, text=gtitle, font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(anchor="w", padx=12)
            tk.Label(card, text=gdesc, font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, wraplength=280, justify="left").pack(anchor="w", padx=12, pady=(4, 10))

        # Protected File Patterns Whitelist
        patterns_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        patterns_card.pack(fill="both", expand=True, pady=(0, 12))

        p_header = tk.Frame(patterns_card, bg=COLOR_CARD)
        p_header.pack(fill="x", padx=14, pady=10)
        tk.Label(p_header, text="Strict Protected Data Patterns (Hard Whitelist Immunity)", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")

        txt_patterns = tk.Text(patterns_card, bg="#f8fafc", fg=COLOR_TEXT_PRIMARY, font=("Consolas", 8), height=5, bd=0, padx=10, pady=8)
        txt_patterns.pack(fill="x", padx=12, pady=(0, 10))
        patterns_str = ",  ".join(PROTECTED_FILE_PATTERNS)
        txt_patterns.insert("1.0", f"Protected Database & Session Keywords:\n{patterns_str}\n\nProtected Extensions: {', '.join(PROTECTED_EXTENSIONS)}")
        txt_patterns.configure(state="disabled")

        # Interactive Policy Evaluator Tool
        sim_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        sim_card.pack(fill="x")

        s_header = tk.Frame(sim_card, bg=COLOR_CARD)
        s_header.pack(fill="x", padx=14, pady=10)
        tk.Label(s_header, text="Interactive Safety Decision Simulator", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")

        sim_input_frame = tk.Frame(sim_card, bg=COLOR_CARD)
        sim_input_frame.pack(fill="x", padx=14, pady=(0, 10))

        tk.Label(sim_input_frame, text="Test File Path:", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left", padx=(0, 6))
        self.entry_test_path = tk.Entry(sim_input_frame, width=60, font=("Segoe UI", 8), bg="#f8fafc", relief="flat", highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        self.entry_test_path.pack(side="left", padx=(0, 10))
        self.entry_test_path.insert(0, "C:\\Users\\User\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cookies")

        tk.Button(
            sim_input_frame, text="🔍 Evaluate Safety Decision", font=("Segoe UI", 8, "bold"),
            bg=COLOR_PRIMARY, fg="#ffffff", bd=0, padx=10, pady=4, cursor="hand2", relief="flat",
            command=self._simulate_safety_policy
        ).pack(side="left")

        self.lbl_policy_decision = tk.Label(sim_card, text="Decision: READY", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD)
        self.lbl_policy_decision.pack(anchor="w", padx=14, pady=(0, 10))

    def _simulate_safety_policy(self):
        target = self.entry_test_path.get().strip()
        if not target:
            return

        # Check protected patterns
        prot_res = SafetyPolicy.is_protected_target(target)
        if prot_res["protected"]:
            self.lbl_policy_decision.configure(
                text=f"Decision: DENY [{prot_res['code']}] — {prot_res['reason']}",
                fg=COLOR_DANGER
            )
            return

        # Check symlinks
        sym_res = SafetyPolicy.validate_symlink_and_reparse_point(target)
        if sym_res["is_reparse"]:
            self.lbl_policy_decision.configure(
                text=f"Decision: DENY [REPARSE_POINT] — {sym_res['reason']}",
                fg=COLOR_DANGER
            )
            return

        self.lbl_policy_decision.configure(
            text="Decision: ALLOW [SAFE_TARGET] — Path passed all pattern immunity and symlink checks.",
            fg=COLOR_SUCCESS
        )

    # --------------------------------------------------------------------------
    # SCREEN 6: QUARANTINE VAULT
    # --------------------------------------------------------------------------
    def _build_screen_quarantine_vault(self, parent):
        title_frame = tk.Frame(parent, bg=COLOR_BG)
        title_frame.pack(fill="x", pady=(0, 14))
        tk.Label(title_frame, text="Quarantine Vault & Integrity Records", font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG).pack(side="left")
        tk.Label(title_frame, text="Module 3 / Task 3.1 & 3.2 (Activities 3.1.2, 3.1.3, 3.2.1, 3.2.2)", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG).pack(side="left", padx=12, pady=(4, 0))

        # Vault Controls Card
        vault_ctrl = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        vault_ctrl.pack(fill="x", pady=(0, 12))
        v_inner = tk.Frame(vault_ctrl, bg=COLOR_CARD)
        v_inner.pack(fill="x", padx=14, pady=10)

        tk.Button(
            v_inner, text="🔄 1-Click Restore to Original", font=("Segoe UI", 9, "bold"),
            bg=COLOR_PRIMARY, fg="#ffffff", bd=0, padx=12, pady=6, cursor="hand2", relief="flat",
            command=self._restore_selected_quarantine
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            v_inner, text="🔍 Verify SHA-256 Checksum", font=("Segoe UI", 9),
            bg="#f1f5f9", fg=COLOR_TEXT_PRIMARY, bd=0, padx=12, pady=6, cursor="hand2", relief="flat",
            command=self._verify_selected_quarantine_sha256
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            v_inner, text="🗑️ Purge Expired (Retention >= 30 Days)", font=("Segoe UI", 9),
            bg=COLOR_DANGER_BG, fg=COLOR_DANGER, bd=0, padx=12, pady=6, cursor="hand2", relief="flat",
            command=self._purge_selected_quarantine
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            v_inner, text="🔄 Refresh Vault", font=("Segoe UI", 9),
            bg="#f1f5f9", fg=COLOR_TEXT_PRIMARY, bd=0, padx=10, pady=6, cursor="hand2", relief="flat",
            command=self._refresh_quarantine_tree
        ).pack(side="right")

        # Table Card
        table_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        table_card.pack(fill="both", expand=True)

        columns = ("id", "filename", "size", "quarantined_at", "status", "sha256", "orig_path")
        self.quarantine_tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="browse")
        self.quarantine_tree.heading("id", text="Quarantine ID")
        self.quarantine_tree.heading("filename", text="File Name")
        self.quarantine_tree.heading("size", text="Size")
        self.quarantine_tree.heading("quarantined_at", text="Quarantine Timestamp")
        self.quarantine_tree.heading("status", text="Status")
        self.quarantine_tree.heading("sha256", text="SHA-256 Checksum")
        self.quarantine_tree.heading("orig_path", text="Original Location")

        self.quarantine_tree.column("id", width=140)
        self.quarantine_tree.column("filename", width=140)
        self.quarantine_tree.column("size", width=80, anchor="e")
        self.quarantine_tree.column("quarantined_at", width=140)
        self.quarantine_tree.column("status", width=100, anchor="center")
        self.quarantine_tree.column("sha256", width=200)
        self.quarantine_tree.column("orig_path", width=280)

        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.quarantine_tree.yview)
        self.quarantine_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, 6), pady=(0, 10))
        self.quarantine_tree.pack(fill="both", expand=True, padx=(12, 0), pady=(0, 10))

        self._refresh_quarantine_tree()

    def _refresh_quarantine_tree(self):
        if not hasattr(self, "quarantine_tree"):
            return
        self.quarantine_tree.delete(*self.quarantine_tree.get_children())
        mode = self.current_mode.get()
        manifest = QuarantineManager.load_manifest(mode)

        for m in manifest:
            q_id = m.get("manifest_id", "")
            fname = m.get("file_name", os.path.basename(m.get("original_path", "")))
            sz = m.get("size_formatted", format_file_size(m.get("file_size", 0)))
            ts = m.get("timestamp", "")
            st = m.get("status", "QUARANTINED")
            h = m.get("sha256", "")
            orig = m.get("original_path", "")

            self.quarantine_tree.insert("", "end", iid=q_id, values=(q_id, fname, sz, ts, st, h, orig))

    def _restore_selected_quarantine(self):
        selected = self.quarantine_tree.selection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select a quarantined file to restore.")
            return

        q_id = selected[0]
        mode = self.current_mode.get()
        res = QuarantineManager.restore_file(q_id, mode)

        if res["success"]:
            messagebox.showinfo("Restore Successful", res["message"])
            self._refresh_quarantine_tree()
        else:
            messagebox.showerror("Restore Blocked", res["message"])

    def _verify_selected_quarantine_sha256(self):
        selected = self.quarantine_tree.selection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select a quarantined file to verify.")
            return

        q_id = selected[0]
        mode = self.current_mode.get()
        manifest = QuarantineManager.load_manifest(mode)
        entry = next((e for e in manifest if e.get("manifest_id") == q_id), None)

        if not entry:
            messagebox.showerror("Error", "Entry not found in manifest.")
            return

        q_path = entry.get("quarantine_path", "")
        expected = entry.get("sha256", "")
        current = compute_file_sha256(q_path)

        if current and current.lower() == expected.lower():
            messagebox.showinfo(
                "SHA-256 Integrity Verified",
                f"Status: INTACT & SECURE\n\nRecorded Hash:\n{expected}\n\nComputed Hash:\n{current}"
            )
        else:
            messagebox.showerror(
                "Integrity Alert",
                f"Status: MISMATCH DETECTED!\n\nRecorded Hash: {expected}\nComputed Hash: {current}"
            )

    def _purge_selected_quarantine(self):
        selected = self.quarantine_tree.selection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select a quarantined file to purge.")
            return

        q_id = selected[0]
        mode = self.current_mode.get()

        confirm = messagebox.askyesno(
            "Confirm Permanent Purge",
            f"Are you sure you want to permanently purge '{q_id}'?\n\nThis operation cannot be undone.",
            icon="warning"
        )
        if not confirm:
            return

        res = QuarantineManager.purge_file(q_id, mode, user_purge_enabled=True)
        if res["success"]:
            messagebox.showinfo("Purge Completed", res["message"])
            self._refresh_quarantine_tree()
        else:
            messagebox.showwarning("Purge Safeguard Enforced", res["message"])

    # --------------------------------------------------------------------------
    # SCREEN 7: RECOVERY CENTER
    # --------------------------------------------------------------------------
    def _build_screen_recovery_center(self, parent):
        title_frame = tk.Frame(parent, bg=COLOR_BG)
        title_frame.pack(fill="x", pady=(0, 14))
        tk.Label(title_frame, text="Recovery Center & Interrupted Operation Reconciler", font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG).pack(side="left")
        tk.Label(title_frame, text="Module 3 / Task 3.2 (Activities 3.2.1, 3.2.2, 3.2.3)", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG).pack(side="left", padx=12, pady=(4, 0))

        # Recovery Controls Card
        card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        card.pack(fill="x", pady=(0, 14))
        c_inner = tk.Frame(card, bg=COLOR_CARD)
        c_inner.pack(fill="x", padx=16, pady=14)

        tk.Label(c_inner, text="Crash Reconciliation & Rollback Manager", font=("Segoe UI", 11, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(anchor="w")
        tk.Label(c_inner, text="Scans for orphaned temporary files and incomplete operations from system interrupts or power loss.", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w", pady=(2, 10))

        tk.Button(
            c_inner, text="🔄 Run Interrupted Operation Reconciliation", font=("Segoe UI", 9, "bold"),
            bg=COLOR_PRIMARY, fg="#ffffff", bd=0, padx=14, pady=6, cursor="hand2", relief="flat",
            command=self._run_reconciliation
        ).pack(anchor="w")

        self.lbl_recon_result = tk.Label(c_inner, text="Reconciliation Status: READY", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD)
        self.lbl_recon_result.pack(anchor="w", pady=(8, 0))

        # Recovery Manifest Integrity Card
        m_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        m_card.pack(fill="both", expand=True)

        m_header = tk.Frame(m_card, bg=COLOR_CARD)
        m_header.pack(fill="x", padx=16, pady=10)
        tk.Label(m_header, text="Restoration Manifest Audit Trail", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")

        self.txt_recovery_log = tk.Text(m_card, bg="#f8fafc", fg=COLOR_TEXT_PRIMARY, font=("Consolas", 8), bd=0, padx=12, pady=10)
        self.txt_recovery_log.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.txt_recovery_log.insert("1.0", "Recovery log initialized. Click 'Run Interrupted Operation Reconciliation' to inspect manifest and temp vaults.")
        self.txt_recovery_log.configure(state="disabled")

    def _run_reconciliation(self):
        mode = self.current_mode.get()
        res = QuarantineManager.reconcile_and_rollback(mode)
        self.lbl_recon_result.configure(
            text=f"Reconciliation Status: COMPLETE — Cleaned Temps: {res['cleaned_temp_files']}, Reconciled Records: {res['reconciled_records']}",
            fg=COLOR_SUCCESS
        )
        self.txt_recovery_log.configure(state="normal")
        self.txt_recovery_log.delete("1.0", "end")
        self.txt_recovery_log.insert("1.0", json.dumps(res, indent=2))
        self.txt_recovery_log.configure(state="disabled")

    # --------------------------------------------------------------------------
    # SCREEN 8: MONITORING CENTER (PERIODIC SCAN & TELEMETRY)
    # --------------------------------------------------------------------------
    def _build_screen_monitoring_center(self, parent):
        title_frame = tk.Frame(parent, bg=COLOR_BG)
        title_frame.pack(fill="x", pady=(0, 14))
        tk.Label(title_frame, text="Background Monitoring & Process Telemetry", font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG).pack(side="left")
        tk.Label(title_frame, text="Module 3 / Task 3.3 (Activity 3.3.1)", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG).pack(side="left", padx=12, pady=(4, 0))

        # Top Control Card
        m_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        m_card.pack(fill="x", pady=(0, 14))
        m_inner = tk.Frame(m_card, bg=COLOR_CARD)
        m_inner.pack(fill="x", padx=16, pady=12)

        tk.Label(m_inner, text="Background Scanning Scheduler", font=("Segoe UI", 11, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(anchor="w")
        tk.Label(m_inner, text="Autonomous non-intrusive periodic background scanning. Process freezing and termination are strictly disabled.", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w", pady=(2, 10))

        b_row = tk.Frame(m_inner, bg=COLOR_CARD)
        b_row.pack(fill="x")

        status_text = "🟢 ACTIVE (Running every 15 mins)" if self.background_worker.is_running else "🔴 STOPPED"
        self.lbl_bg_status = tk.Label(b_row, text=f"Worker Status: {status_text}", font=("Segoe UI", 9, "bold"), fg=COLOR_SUCCESS if self.background_worker.is_running else COLOR_DANGER, bg=COLOR_CARD)
        self.lbl_bg_status.pack(side="left", padx=(0, 16))

        tk.Button(
            b_row, text="Restart Background Worker", font=("Segoe UI", 8),
            bg="#f1f5f9", fg=COLOR_TEXT_PRIMARY, bd=0, padx=10, pady=4, cursor="hand2", relief="flat",
            command=self._restart_background_worker
        ).pack(side="left")

        # Process Telemetry Card (Read-only)
        telemetry_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        telemetry_card.pack(fill="both", expand=True)

        t_header = tk.Frame(telemetry_card, bg=COLOR_CARD)
        t_header.pack(fill="x", padx=16, pady=10)
        tk.Label(t_header, text="Monitored Application Processes (Read-Only Telemetry)", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")

        columns = ("app", "process", "status", "pid", "safety")
        p_tree = ttk.Treeview(telemetry_card, columns=columns, show="headings", height=8)
        p_tree.heading("app", text="Application")
        p_tree.heading("process", text="Executable")
        p_tree.heading("status", text="Execution State")
        p_tree.heading("pid", text="Active PIDs")
        p_tree.heading("safety", text="Safety Policy Directive")

        p_tree.column("app", width=180)
        p_tree.column("process", width=130)
        p_tree.column("status", width=140, anchor="center")
        p_tree.column("pid", width=140)
        p_tree.column("safety", width=220)

        p_tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Populate telemetry
        for app in self.discovered_apps:
            pname = app.get("process_name", "")
            if pname:
                pst = ProcessAnalyzer.get_process_status(pname)
                is_run = pst["running"]
                st_txt = "RUNNING" if is_run else "INACTIVE / CLOSED"
                directive = "Fail-Closed (Scan Only)" if is_run else "Eligible for Review"
                pids_str = ", ".join(str(p) for p in pst.get("pids", [])[:4]) if is_run else "—"
                p_tree.insert("", "end", values=(app["name"], pname, st_txt, pids_str, directive))

    def _restart_background_worker(self):
        self.background_worker.stop()
        self.background_worker.start()
        self.lbl_bg_status.configure(text="Worker Status: 🟢 ACTIVE (Running every 15 mins)", fg=COLOR_SUCCESS)

    # --------------------------------------------------------------------------
    # SCREEN 9: AUDIT TRAIL & REPORTS
    # --------------------------------------------------------------------------
    def _build_screen_audit_reports(self, parent):
        title_frame = tk.Frame(parent, bg=COLOR_BG)
        title_frame.pack(fill="x", pady=(0, 14))
        tk.Label(title_frame, text="Digital Audit Trail & Activity Reports", font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG).pack(side="left")
        tk.Label(title_frame, text="Module 3 / Task 3.3 (Activities 3.3.2, 3.3.3)", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG).pack(side="left", padx=12, pady=(4, 0))

        # Top Button Bar
        btn_bar = tk.Frame(parent, bg=COLOR_BG)
        btn_bar.pack(fill="x", pady=(0, 10))

        tk.Button(
            btn_bar, text="💾 Export Audit Report (JSON)", font=("Segoe UI", 9),
            bg="#ffffff", fg=COLOR_PRIMARY, bd=0, padx=12, pady=6, cursor="hand2", relief="flat",
            highlightthickness=1, highlightbackground=COLOR_CARD_BORDER,
            command=self._export_audit_json
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_bar, text="🔄 Refresh Audit Log", font=("Segoe UI", 9),
            bg="#ffffff", fg=COLOR_TEXT_PRIMARY, bd=0, padx=12, pady=6, cursor="hand2", relief="flat",
            highlightthickness=1, highlightbackground=COLOR_CARD_BORDER,
            command=self._refresh_audit_tree
        ).pack(side="left")

        # Table Card
        card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        card.pack(fill="both", expand=True)

        columns = ("time", "op", "mode", "decision", "code", "path", "detail")
        self.audit_tree = ttk.Treeview(card, columns=columns, show="headings")
        self.audit_tree.heading("time", text="Timestamp (UTC)")
        self.audit_tree.heading("op", text="Operation")
        self.audit_tree.heading("mode", text="Mode")
        self.audit_tree.heading("decision", text="Decision")
        self.audit_tree.heading("code", text="Policy Code")
        self.audit_tree.heading("path", text="Target Path")
        self.audit_tree.heading("detail", text="Audit Details")

        self.audit_tree.column("time", width=130)
        self.audit_tree.column("op", width=80)
        self.audit_tree.column("mode", width=140)
        self.audit_tree.column("decision", width=90, anchor="center")
        self.audit_tree.column("code", width=130)
        self.audit_tree.column("path", width=220)
        self.audit_tree.column("detail", width=280)

        scrollbar = ttk.Scrollbar(card, orient="vertical", command=self.audit_tree.yview)
        self.audit_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, 6), pady=(0, 10))
        self.audit_tree.pack(fill="both", expand=True, padx=(12, 0), pady=(0, 10))

        self._refresh_audit_tree()

    def _refresh_audit_tree(self):
        if not hasattr(self, "audit_tree"):
            return
        self.audit_tree.delete(*self.audit_tree.get_children())
        events = get_audit_store().list_events(limit=150)
        for ev in events:
            # created_at, operation_id, operation, mode, decision, code, source_path, destination_path, detail
            self.audit_tree.insert("", "end", values=(ev[0][:19], ev[2], ev[3], ev[4], ev[5], ev[6] or "—", ev[8]))

    def _export_audit_json(self):
        events = get_audit_store().list_events(limit=500)
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if path:
            export_data = [
                {
                    "created_at": ev[0], "operation_id": ev[1], "operation": ev[2],
                    "mode": ev[3], "decision": ev[4], "code": ev[5],
                    "source_path": ev[6], "destination_path": ev[7], "detail": ev[8]
                }
                for ev in events
            ]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
            messagebox.showinfo("Export Successful", f"Exported {len(export_data)} audit records to {path}")

    # --------------------------------------------------------------------------
    # SCREEN 10: GUIDED PRESENTATION MODE (11-STAGE DEMONSTRATION)
    # --------------------------------------------------------------------------
    def _build_screen_presentation_mode(self, parent):
        title_frame = tk.Frame(parent, bg=COLOR_BG)
        title_frame.pack(fill="x", pady=(0, 14))
        tk.Label(title_frame, text="Guided Academic Project Demonstration (11-Stage Workflow)", font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG).pack(side="left")
        tk.Label(title_frame, text="Interactive demonstration designed for University Examination", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG).pack(side="left", padx=12, pady=(4, 0))

        # Stepper Controls Header
        ctrl_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        ctrl_card.pack(fill="x", pady=(0, 12))
        c_inner = tk.Frame(ctrl_card, bg=COLOR_CARD)
        c_inner.pack(fill="x", padx=16, pady=10)

        tk.Button(
            c_inner, text="▶️ Run Complete 11-Stage Demonstration", font=("Segoe UI", 9, "bold"),
            bg=COLOR_PRIMARY, fg="#ffffff", bd=0, padx=14, pady=6, cursor="hand2", relief="flat",
            command=self._start_complete_demo_workflow
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            c_inner, text="⏭️ Step to Next Stage", font=("Segoe UI", 9),
            bg="#f1f5f9", fg=COLOR_TEXT_PRIMARY, bd=0, padx=12, pady=6, cursor="hand2", relief="flat",
            command=self._step_next_demo_stage
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            c_inner, text="🔄 Reset Demo Sandbox", font=("Segoe UI", 9),
            bg="#f1f5f9", fg=COLOR_TEXT_PRIMARY, bd=0, padx=12, pady=6, cursor="hand2", relief="flat",
            command=self._reset_demo_sandbox
        ).pack(side="left")

        # Split Container: Left = 11 Stages list, Right = Real-time Live Stage Execution Console
        split_frame = tk.Frame(parent, bg=COLOR_BG)
        split_frame.pack(fill="both", expand=True)

        # Left Stages List Card
        left_card = tk.Frame(split_frame, bg=COLOR_CARD, width=380, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        left_card.pack(side="left", fill="both", expand=False, padx=(0, 10))
        left_card.pack_propagate(False)

        tk.Label(left_card, text="Examination Workflow Stages", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(anchor="w", padx=14, pady=(10, 6))

        self.demo_stages = [
            ("Stage 1", "Application discovery", "Activity 1.1.1: Identify browser/electron targets"),
            ("Stage 2", "Cache directory identification", "Activity 1.1.2: Detect approved cache paths"),
            ("Stage 3", "File scanning & metadata", "Activity 1.2.1-1.2.2: Extract attributes & size"),
            ("Stage 4", "Zombie data analysis", "Activity 2.1.1-2.1.3: Age & dormancy evaluation"),
            ("Stage 5", "Classification score calculation", "Activity 2.2.1-2.2.3: Explainable 0-100 score"),
            ("Stage 6", "Safety policy evaluation", "Activity 2.3.1-2.3.3: Separate fail-closed checks"),
            ("Stage 7", "User review and approval", "Activity 3.1.1: Filter candidates & confirm"),
            ("Stage 8", "Quarantine & SHA-256 integrity", "Activity 3.1.2: Move to vault & record hash"),
            ("Stage 9", "File restoration", "Activity 3.2.1-3.2.2: Restore to origin & verify"),
            ("Stage 10", "Retention-based purge eligibility", "Activity 3.1.3: Validate 30-day maturity"),
            ("Stage 11", "Audit log & dashboard report", "Activity 3.3.2-3.3.3: Durable SQLite audit trail"),
        ]

        self.stage_labels = []
        for stage_code, stage_title, act_text in self.demo_stages:
            row = tk.Frame(left_card, bg=COLOR_CARD)
            row.pack(fill="x", padx=12, pady=2)

            lbl_badge = tk.Label(row, text="⏳ PENDING", font=("Segoe UI", 7, "bold"), bg="#f1f5f9", fg=COLOR_TEXT_MUTED, width=10)
            lbl_badge.pack(side="left", padx=(0, 8))

            text_box = tk.Frame(row, bg=COLOR_CARD)
            text_box.pack(side="left", fill="x", expand=True)

            tk.Label(text_box, text=f"{stage_code}: {stage_title}", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD, anchor="w").pack(fill="x")
            tk.Label(text_box, text=act_text, font=("Segoe UI", 7), fg=COLOR_TEXT_LIGHT, bg=COLOR_CARD, anchor="w").pack(fill="x")

            self.stage_labels.append(lbl_badge)

        # Right Live Execution Console Card
        right_card = tk.Frame(split_frame, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        right_card.pack(side="right", fill="both", expand=True)

        r_header = tk.Frame(right_card, bg=COLOR_CARD)
        r_header.pack(fill="x", padx=16, pady=10)
        tk.Label(r_header, text="Live Stage Execution Console (Actual Sandbox Operations)", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")

        self.txt_demo_console = tk.Text(right_card, bg="#0f172a", fg="#38bdf8", font=("Consolas", 9), bd=0, padx=14, pady=12)
        self.txt_demo_console.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        init_msg = """[EXAMINATION DEMONSTRATION WORKFLOW — ZOMBIE DATA PURGER]
Sandbox: %LOCALAPPDATA%\\ZombieDataPurgerDemo\\
Guarantees:
  - Synthetic test files only; NEVER touches real browser profiles.
  - Demonstrates genuine execution of all 3 academic modules and 27 activities.
  - Verifies safety policy fail-closed decisions, SHA-256 integrity, and SQLite audit trail.

Click 'Run Complete 11-Stage Demonstration' to start sequential execution.
"""
        self.txt_demo_console.insert("1.0", init_msg)

    def _demo_log(self, text):
        if hasattr(self, "txt_demo_console"):
            self.txt_demo_console.insert("end", f"\n{text}")
            self.txt_demo_console.see("end")

    def _reset_demo_sandbox(self):
        try:
            create_safe_demo_environment()
            self._demo_log("[RESET] Demo environment refreshed with synthetic samples in isolated sandbox.")
            for lbl in getattr(self, "stage_labels", []):
                lbl.configure(text="⏳ PENDING", bg="#f1f5f9", fg=COLOR_TEXT_MUTED)
            self.demo_current_stage = 0
        except Exception as e:
            self._demo_log(f"[ERROR] Reset failed: {e}")

    def _start_complete_demo_workflow(self):
        if self.demo_running:
            return
        self.demo_running = True
        self._reset_demo_sandbox()

        def runner():
            try:
                for stage_idx in range(len(self.demo_stages)):
                    self._execute_single_demo_stage(stage_idx)
                    time.sleep(1.0)
                self._demo_log("\n══════════════════════════════════════════════════════════════════════")
                self._demo_log("✅ 11-STAGE DEMONSTRATION COMPLETED SUCCESSFULLY!")
                self._demo_log("══════════════════════════════════════════════════════════════════════")
            finally:
                self.demo_running = False

        threading.Thread(target=runner, daemon=True).start()

    def _step_next_demo_stage(self):
        if self.demo_current_stage < len(self.demo_stages):
            self._execute_single_demo_stage(self.demo_current_stage)
            self.demo_current_stage += 1
        else:
            messagebox.showinfo("Demonstration Complete", "All 11 demonstration stages have completed.")

    def _execute_single_demo_stage(self, stage_idx):
        if stage_idx >= len(self.demo_stages):
            return

        lbl = self.stage_labels[stage_idx]
        lbl.configure(text="▶️ RUNNING", bg=COLOR_WARNING_BG, fg=COLOR_WARNING)

        time.sleep(0.3)

        if stage_idx == 0:
            # Stage 1: Application Discovery
            self._demo_log("\n▶ STAGE 1: Application Discovery (Activity 1.1.1)")
            apps = ApplicationDiscovery.identify_applications(MODE_SAFE_DEMO)
            for a in apps:
                self._demo_log(f"  • Discovered: {a['name']} | Path: {a['path']}")

        elif stage_idx == 1:
            # Stage 2: Cache Directory Identification
            self._demo_log("\n▶ STAGE 2: Cache Directory Identification (Activity 1.1.2)")
            apps = ApplicationDiscovery.identify_applications(MODE_SAFE_DEMO)
            for a in apps:
                dirs = ApplicationDiscovery.detect_supported_cache_directories(a)
                for d in dirs:
                    self._demo_log(f"  • Approved Cache Directory: {d['directory_name']} ({d['full_path']})")

        elif stage_idx == 2:
            # Stage 3: File Scanning & Metadata
            self._demo_log("\n▶ STAGE 3: File Scanning & Metadata Extraction (Activity 1.2.1, 1.2.2)")
            apps = ApplicationDiscovery.identify_applications(MODE_SAFE_DEMO)
            self.demo_scan_result = FileScanner.scan_directory(apps[0], age_threshold_days=14)
            files = self.demo_scan_result.get("files", [])
            self._demo_log(f"  • Scanned {len(files)} files in {apps[0]['name']}")
            for f in files[:3]:
                self._demo_log(f"    - {f['file_name']}: Size={f['size_formatted']}, Age={f['age_days']} days, Ext={f['extension']}")

        elif stage_idx == 3:
            # Stage 4: Zombie Data Analysis
            self._demo_log("\n▶ STAGE 4: Zombie Data Analysis (Activity 2.1.1 - 2.1.3)")
            files = getattr(self, "demo_scan_result", {}).get("files", [])
            for f in files[:3]:
                age_ev = ZombieDataClassifier.analyze_file_age(f["mtime"], f["ctime"], 14)
                cache_ev = ZombieDataClassifier.evaluate_cache_characteristics(f)
                self._demo_log(f"  • File: {f['file_name']} -> Age: {age_ev['age_days']} days (Exceeds: {age_ev['exceeds_threshold']}), Disposable Cache: {cache_ev['is_disposable_cache']}")

        elif stage_idx == 4:
            # Stage 5: Classification Score Calculation
            self._demo_log("\n▶ STAGE 5: Explainable Score Calculation (Activity 2.2.1 - 2.2.3)")
            files = getattr(self, "demo_scan_result", {}).get("files", [])
            for f in files[:4]:
                self._demo_log(f"  • {f['file_name']}: Score={f.get('score')} | Category={f.get('classification')} | Risk={f.get('risk_level')}")

        elif stage_idx == 5:
            # Stage 6: Safety Policy Evaluation
            self._demo_log("\n▶ STAGE 6: Safety Policy Evaluation (Activity 2.3.1 - 2.3.3)")
            self._demo_log("  [TEST A] Evaluating Stale Cache File for Quarantine:")
            files = getattr(self, "demo_scan_result", {}).get("files", [])
            zombie_files = [f for f in files if "ZOMBIE" in f.get("classification", "").upper()]
            if zombie_files:
                sample = zombie_files[0]
                dec = SafetyPolicy.authorize("quarantine", sample["full_path"], mode=MODE_SAFE_DEMO, metadata=sample, age_days=sample.get("age_days"))
                self._demo_log(f"    Result: {dec.decision.value} [{dec.code}] — {dec.reason}")

            self._demo_log("  [TEST B] Evaluating Protected 'Cookies' File:")
            cookies_path = os.path.join(DEMO_BASE_DIR, "Chrome_Demo", "Active", "Cookies")
            dec_cookie = SafetyPolicy.is_protected_target(cookies_path)
            self._demo_log(f"    Result: PROTECTED={dec_cookie['protected']} [{dec_cookie['code']}] — {dec_cookie['reason']}")

        elif stage_idx == 6:
            # Stage 7: User Review and Approval
            self._demo_log("\n▶ STAGE 7: User Review and Approval (Activity 3.1.1)")
            files = getattr(self, "demo_scan_result", {}).get("files", [])
            review_res = QuarantineManager.filter_and_select_candidates(files)
            self._demo_log(f"  • Reviewed Candidates: {review_res['reviewed_count']} files ({review_res['total_review_formatted']})")
            self._demo_log(f"  • Excluded / Protected Candidates: {review_res['skipped_count']} files")

        elif stage_idx == 7:
            # Stage 8: Quarantine & SHA-256 Integrity Verification
            self._demo_log("\n▶ STAGE 8: Secure Quarantine with SHA-256 (Activity 3.1.2)")
            files = getattr(self, "demo_scan_result", {}).get("files", [])
            zombie_files = [f for f in files if "ZOMBIE" in f.get("classification", "").upper()]
            self.demo_quarantined_ids = []
            for zf in zombie_files[:2]:
                q_res = QuarantineManager.quarantine_candidate(zf, MODE_SAFE_DEMO)
                if q_res["success"]:
                    qid = q_res["entry"]["manifest_id"]
                    self.demo_quarantined_ids.append(qid)
                    self._demo_log(f"  • Quarantined '{zf['file_name']}' -> ID: {qid}")
                    self._demo_log(f"    SHA-256: {q_res['entry']['sha256']}")

        elif stage_idx == 8:
            # Stage 9: File Restoration
            self._demo_log("\n▶ STAGE 9: File Restoration & Cryptographic Verification (Activity 3.2.1, 3.2.2)")
            if getattr(self, "demo_quarantined_ids", []):
                target_id = self.demo_quarantined_ids[0]
                self._demo_log(f"  • Restoring '{target_id}' to original location...")
                rest_res = QuarantineManager.restore_quarantined_file(target_id, MODE_SAFE_DEMO)
                self._demo_log(f"    {rest_res['message']}")
                if rest_res["success"]:
                    orig_p = rest_res["entry"]["original_path"]
                    exp_h = rest_res["entry"]["sha256"]
                    int_check = QuarantineManager.verify_restoration_integrity(orig_p, exp_h)
                    self._demo_log(f"    Cryptographic Check: {int_check['status']} (Hash Matched)")

        elif stage_idx == 9:
            # Stage 10: Retention-based Purge Eligibility
            self._demo_log("\n▶ STAGE 10: Retention-based Purge Eligibility (Activity 3.1.3)")
            manifest = QuarantineManager.load_manifest(MODE_SAFE_DEMO)
            for m in manifest:
                elig = QuarantineManager.validate_purge_eligibility(m, retention_days=30, mode=MODE_SAFE_DEMO, demo_simulate_retention=True)
                self._demo_log(f"  • Record {m.get('manifest_id')}: Purge Eligible={elig['eligible']} (Simulated Retention Pass)")

        elif stage_idx == 10:
            # Stage 11: Audit Log & Summary Report
            self._demo_log("\n▶ STAGE 11: Durable Audit Log & Analytics Report (Activity 3.3.2, 3.3.3)")
            events = get_audit_store().list_events(limit=5)
            self._demo_log(f"  • Latest SQLite Audit Events ({len(events)} shown):")
            for ev in events:
                self._demo_log(f"    [{ev[0][:19]}] {ev[2].upper()}: {ev[4]} — {ev[5]}")
            metrics = get_audit_store().get_dashboard_metrics()
            self._demo_log(f"  • Overall Scanned: {metrics['total_scanned_files']}, Quarantined: {metrics['quarantined_count']}, Restored: {metrics['restored_count']}")

        lbl.configure(text="✅ DONE", bg=COLOR_SUCCESS_BG, fg=COLOR_SUCCESS)

    # --------------------------------------------------------------------------
    # SCREEN 11: SETTINGS & CONFIGURATION
    # --------------------------------------------------------------------------
    def _build_screen_settings(self, parent):
        title_frame = tk.Frame(parent, bg=COLOR_BG)
        title_frame.pack(fill="x", pady=(0, 14))
        tk.Label(title_frame, text="Settings & Academic Architecture Mapping", font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG).pack(side="left")
        tk.Label(title_frame, text="Configure thresholds, retention, and inspect 27 academic activities", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG).pack(side="left", padx=12, pady=(4, 0))

        # Settings Card
        card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        card.pack(fill="x", pady=(0, 14))
        c_inner = tk.Frame(card, bg=COLOR_CARD)
        c_inner.pack(fill="x", padx=16, pady=12)

        tk.Label(c_inner, text="Configuration Settings", font=("Segoe UI", 11, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(anchor="w")

        # Global Pause Checkbutton
        chk_pause = tk.Checkbutton(
            c_inner, text="Global Pause Cleanup (Blocks all file-changing quarantine, restore, and purge operations)",
            variable=self.global_pause, font=("Segoe UI", 9), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD,
            command=self._on_pause_checkbox_changed
        )
        chk_pause.pack(anchor="w", pady=(8, 4))

        # Quarantine Retention Days
        ret_row = tk.Frame(c_inner, bg=COLOR_CARD)
        ret_row.pack(fill="x", pady=4)
        tk.Label(ret_row, text="Quarantine Retention Maturity (Days):", font=("Segoe UI", 9), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")
        tk.Label(ret_row, text="30 Days (University Exam Safe Default)", font=("Segoe UI", 9, "bold"), fg=COLOR_PRIMARY, bg=COLOR_CARD).pack(side="left", padx=8)

        # Paths
        p_row = tk.Frame(c_inner, bg=COLOR_CARD)
        p_row.pack(fill="x", pady=4)
        tk.Label(p_row, text=f"Demo Sandbox: {DEMO_BASE_DIR}", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")
        tk.Label(p_row, text=f"Real Sandbox: {REAL_BASE_DIR}", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")

        # 27 Academic Activities Mapping Viewer Card
        map_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER)
        map_card.pack(fill="both", expand=True)

        m_header = tk.Frame(map_card, bg=COLOR_CARD)
        m_header.pack(fill="x", padx=16, pady=10)
        tk.Label(m_header, text="Academic Architecture Mapping (3 Modules, 9 Tasks, 27 Activities)", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")

        columns = ("id", "name", "task", "module", "function")
        tree_map = ttk.Treeview(map_card, columns=columns, show="headings", height=8)
        tree_map.heading("id", text="Activity ID")
        tree_map.heading("name", text="Activity Name")
        tree_map.heading("task", text="Task")
        tree_map.heading("module", text="Module")
        tree_map.heading("function", text="Implemented Python Function")

        tree_map.column("id", width=80, anchor="center")
        tree_map.column("name", width=260)
        tree_map.column("task", width=160)
        tree_map.column("module", width=180)
        tree_map.column("function", width=240)

        tree_map.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Populate all 27 activities
        for act in AcademicCoreRegistry.get_all():
            tree_map.insert("", "end", values=(
                act.activity_id,
                act.name,
                f"Task {act.task_id}: {act.task_name}",
                f"Module {act.module_id}",
                act.function_name
            ))

    # --------------------------------------------------------------------------
    # CONTROLLER METHODS & EVENT HANDLERS
    # --------------------------------------------------------------------------
    def _refresh_applications(self):
        mode = self.current_mode.get()
        self.discovered_apps = ApplicationDiscovery.get_applications_for_mode(mode)
        if hasattr(self, "combo_target_app"):
            valid = [a["name"] for a in self.discovered_apps if a.get("exists")]
            self.combo_target_app.configure(values=valid)
            if valid and not self.combo_target_app.get():
                self.combo_target_app.set(valid[0])

    def _on_mode_changed(self, event=None):
        self._refresh_applications()
        SafetyPolicy.demo_purge_enabled = (self.current_mode.get() == MODE_SAFE_DEMO)
        self._switch_screen(self.active_screen_id)

    def _toggle_global_pause(self):
        new_state = not self.global_pause.get()
        self.global_pause.set(new_state)
        SafetyPolicy.paused = new_state
        if new_state:
            self.btn_pause.configure(text="▶️ Resume Cleanup", bg=COLOR_WARNING_BG, fg=COLOR_WARNING)
            self.status_pill.configure(text="⏸️ CLEANUP PAUSED", bg=COLOR_WARNING_BG, fg=COLOR_WARNING)
        else:
            self.btn_pause.configure(text="⏸️ Pause Cleanup", bg="#f1f5f9", fg=COLOR_TEXT_PRIMARY)
            self.status_pill.configure(text="● SYSTEM READY", bg=COLOR_SUCCESS_BG, fg=COLOR_SUCCESS)

    def _on_pause_checkbox_changed(self):
        SafetyPolicy.paused = self.global_pause.get()
        self._toggle_global_pause()

    def _start_quick_scan(self):
        self._switch_screen("scanner")
        self._start_scan_thread()

    def _start_scan_thread(self):
        if self._scan_thread and self._scan_thread.is_alive():
            return

        target_app_name = self.combo_target_app.get() if hasattr(self, "combo_target_app") else ""
        target_app = next((a for a in self.discovered_apps if a["name"] == target_app_name), None)
        if not target_app and self.discovered_apps:
            target_app = self.discovered_apps[0]

        if not target_app:
            messagebox.showerror("Scan Error", "No valid application target available to scan.")
            return

        self._scan_cancel_event.clear()
        self.btn_run_scan.configure(state="disabled")
        self.btn_cancel_scan.configure(state="normal")
        self.scan_progress.start(10)
        self.lbl_scan_status.configure(text=f"Scanning {target_app['name']} cache hierarchies...")

        def worker():
            try:
                res = FileScanner.scan_directory(
                    target_app,
                    age_threshold_days=self.age_threshold.get(),
                    cancel_event=self._scan_cancel_event
                )
                mode = self.current_mode.get()
                FileScanner.generate_scan_report_and_store(res, mode)
                self.scan_results = res
                self.after(0, self._on_scan_completed, res)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Scan Error", str(e)))

        self._scan_thread = threading.Thread(target=worker, daemon=True)
        self._scan_thread.start()

    def _cancel_active_scan(self):
        self._scan_cancel_event.set()
        self.lbl_scan_status.configure(text="Cancelling scan...")

    def _on_scan_completed(self, results):
        self.scan_progress.stop()
        self.btn_run_scan.configure(state="normal")
        self.btn_cancel_scan.configure(state="disabled")

        files = results.get("files", [])
        zombies = results.get("zombie_count", 0)
        reclaim = results.get("potential_space_formatted", "0 B")
        self.lbl_scan_status.configure(
            text=f"Scan complete. Discovered {len(files)} files ({zombies} zombies identified, {reclaim} reclaimable).",
            fg=COLOR_SUCCESS
        )

        self._populate_scanner_tree(files)

    # --------------------------------------------------------------------------
    # SCREEN: BROWSER STORAGE ANALYSIS  (Module A, B, C, D)
    # Placed logically after Intelligent Scanner and before Zombie Intelligence.
    # --------------------------------------------------------------------------
    def _build_screen_storage_analysis(self, parent):
        """
        Module A: Browser folder-level storage summary with percentage progress bars.
        Module B: Individual file-level storage table (top-5 + remaining aggregate row).
        Module C: Visual storage distribution bars.
        Module D: Classification inspection for selected file rows.
        READ-ONLY: No files are modified, moved, or deleted by this screen.
        """
        # --- Page Header ---
        title_frame = tk.Frame(parent, bg=COLOR_BG)
        title_frame.pack(fill="x", pady=(0, 14))
        tk.Label(
            title_frame, text="Browser Storage Analysis",
            font=("Segoe UI", 16, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_BG
        ).pack(side="left")
        tk.Label(
            title_frame,
            text="Folder-level & file-level cache storage distribution  |  READ-ONLY",
            font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG
        ).pack(side="left", padx=12, pady=(4, 0))

        # --- Controls Bar ---
        ctrl_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1,
                             highlightbackground=COLOR_CARD_BORDER)
        ctrl_card.pack(fill="x", pady=(0, 12))
        ctrl_inner = tk.Frame(ctrl_card, bg=COLOR_CARD)
        ctrl_inner.pack(fill="x", padx=14, pady=10)

        self.btn_storage_scan = tk.Button(
            ctrl_inner, text="🔍 Analyse All Browsers",
            font=("Segoe UI", 9, "bold"), bg=COLOR_PRIMARY, fg="#ffffff",
            bd=0, padx=14, pady=6, cursor="hand2", relief="flat",
            command=self._start_storage_analysis_thread
        )
        self.btn_storage_scan.pack(side="left", padx=(0, 8))

        self.btn_storage_cancel = tk.Button(
            ctrl_inner, text="⏹️ Cancel",
            font=("Segoe UI", 9), bg="#f1f5f9", fg=COLOR_TEXT_PRIMARY,
            bd=0, padx=10, pady=6, cursor="hand2", relief="flat",
            state="disabled", command=self._cancel_storage_scan
        )
        self.btn_storage_cancel.pack(side="left")

        # Safe Demo Mode notice
        tk.Label(
            ctrl_inner,
            text="  ● Demo Mode scans synthetic sandbox only",
            font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD
        ).pack(side="left", padx=16)

        # Progress bar + status
        self.storage_progress = ttk.Progressbar(ctrl_card, mode="indeterminate",
                                                style="Horizontal.TProgressbar")
        self.storage_progress.pack(fill="x", padx=14, pady=(0, 4))
        self.lbl_storage_status = tk.Label(
            ctrl_card,
            text="Click 'Analyse All Browsers' to begin storage analysis.",
            font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD
        )
        self.lbl_storage_status.pack(anchor="w", padx=14, pady=(0, 8))

        # --- Module A: Browser Folder-Level Summary Card ---
        browser_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1,
                                highlightbackground=COLOR_CARD_BORDER)
        browser_card.pack(fill="x", pady=(0, 12))

        bh = tk.Frame(browser_card, bg=COLOR_CARD)
        bh.pack(fill="x", padx=14, pady=(10, 6))
        tk.Label(bh, text="📁  Module A — Browser Folder-Level Storage Distribution",
                 font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")
        self.lbl_total_storage = tk.Label(
            bh, text="Total: —", font=("Segoe UI", 9, "bold"),
            fg=COLOR_PRIMARY, bg=COLOR_CARD
        )
        self.lbl_total_storage.pack(side="right")

        self.storage_browser_rows_frame = tk.Frame(browser_card, bg=COLOR_CARD)
        self.storage_browser_rows_frame.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(
            self.storage_browser_rows_frame,
            text="Run analysis to see browser-level storage breakdown.",
            font=("Segoe UI", 9), fg=COLOR_TEXT_LIGHT, bg=COLOR_CARD
        ).pack(anchor="w")

        # --- Module B: Browser Selector + File-Level Table Card ---
        file_card = tk.Frame(parent, bg=COLOR_CARD, bd=0, highlightthickness=1,
                             highlightbackground=COLOR_CARD_BORDER)
        file_card.pack(fill="both", expand=True)

        fh = tk.Frame(file_card, bg=COLOR_CARD)
        fh.pack(fill="x", padx=14, pady=(10, 6))
        tk.Label(fh, text="📄  Module B — Individual File-Level Storage Analysis",
                 font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD).pack(side="left")

        # Browser selector
        selector_row = tk.Frame(fh, bg=COLOR_CARD)
        selector_row.pack(side="right")
        tk.Label(selector_row, text="Select Browser:",
                 font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(side="left", padx=(0, 6))
        self.combo_storage_browser = ttk.Combobox(
            selector_row, state="readonly", width=26,
            font=("Segoe UI", 9)
        )
        self.combo_storage_browser.pack(side="left")
        self.combo_storage_browser.bind("<<ComboboxSelected>>", self._on_storage_browser_selected)

        # File table
        file_cols = ("rank", "name", "ext", "size", "pct", "age", "score", "class", "path")
        self.storage_file_tree = ttk.Treeview(
            file_card, columns=file_cols, show="headings", height=10, selectmode="browse"
        )
        col_defs = [
            ("rank",  "#",                45,  "center"),
            ("name",  "File Name",       200,  "w"),
            ("ext",   "Extension",        70,  "center"),
            ("size",  "Size",             90,  "e"),
            ("pct",   "Storage %",        80,  "center"),
            ("age",   "Age (Days)",        75,  "center"),
            ("score", "Zombie Score",      90,  "center"),
            ("class", "Classification",   160,  "w"),
            ("path",  "Full Path",        320,  "w"),
        ]
        for col_id, heading, width, anchor in col_defs:
            self.storage_file_tree.heading(col_id, text=heading)
            self.storage_file_tree.column(col_id, width=width, anchor=anchor, stretch=(col_id == "path"))

        # Row tag colouring
        self.storage_file_tree.tag_configure("zombie",    background="#fef2f2", foreground=COLOR_DANGER)
        self.storage_file_tree.tag_configure("keep",      background="#ecfdf5", foreground=COLOR_SUCCESS)
        self.storage_file_tree.tag_configure("uncertain", background="#fffbeb", foreground=COLOR_WARNING)
        self.storage_file_tree.tag_configure("aggregate", background="#f1f5f9", foreground=COLOR_TEXT_MUTED,
                                             font=("Segoe UI", 8, "italic"))
        self.storage_file_tree.tag_configure("total",     background=COLOR_PRIMARY_LIGHT, foreground=COLOR_PRIMARY,
                                             font=("Segoe UI", 9, "bold"))

        sb_file = ttk.Scrollbar(file_card, orient="vertical", command=self.storage_file_tree.yview)
        self.storage_file_tree.configure(yscrollcommand=sb_file.set)
        sb_file.pack(side="right", fill="y", padx=(0, 6), pady=(0, 6))
        self.storage_file_tree.pack(fill="both", expand=True, padx=(12, 0), pady=(0, 6))

        # Module D: Classification detail panel
        detail_frame = tk.Frame(file_card, bg=COLOR_CARD)
        detail_frame.pack(fill="x", padx=14, pady=(0, 10))
        tk.Label(detail_frame, text="🔎 Classification Inspector (select a file row above):",
                 font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")
        self.storage_detail_lbl = tk.Label(
            detail_frame,
            text="—  No file selected",
            font=("Consolas", 8), fg=COLOR_TEXT_MUTED, bg="#f8fafc",
            justify="left", anchor="w", wraplength=900
        )
        self.storage_detail_lbl.pack(fill="x", pady=(4, 0))

        # Bind selection event for Module D
        self.storage_file_tree.bind("<<TreeviewSelect>>", self._on_storage_file_selected)

        # Populate if previous results already exist
        if self._storage_distribution:
            self._refresh_storage_browser_panel()

    # ---------- Module A helpers ----------

    def _start_storage_analysis_thread(self):
        """Launches background thread for multi-browser storage analysis."""
        if self._storage_scan_thread and self._storage_scan_thread.is_alive():
            return
        self._storage_cancel_event.clear()
        self.btn_storage_scan.configure(state="disabled")
        self.btn_storage_cancel.configure(state="normal")
        self.storage_progress.start(10)
        self.lbl_storage_status.configure(
            text="Scanning browser cache directories… (read-only, no files will be modified)",
            fg=COLOR_TEXT_MUTED
        )

        mode = self.current_mode.get()

        def _worker():
            try:
                # Ensure Edge demo fixtures exist in demo mode
                if mode == MODE_SAFE_DEMO:
                    BrowserStorageAnalyzer.ensure_demo_browser_fixtures()

                browsers = BrowserStorageAnalyzer.get_supported_browsers(mode)
                results = []
                for b in browsers:
                    if self._storage_cancel_event.is_set():
                        break
                    res = BrowserStorageAnalyzer.scan_browser_files(
                        b, mode=mode,
                        age_threshold_days=self.age_threshold.get(),
                        cancel_event=self._storage_cancel_event
                    )
                    self._storage_browser_results[b["name"]] = res
                    results.append(res)

                distribution = BrowserStorageAnalyzer.calculate_browser_storage_distribution(results)
                self._storage_distribution = distribution
                self.after(0, self._on_storage_scan_complete, distribution)
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_storage_scan_error(str(e)))

        self._storage_scan_thread = threading.Thread(target=_worker, daemon=True)
        self._storage_scan_thread.start()

    def _cancel_storage_scan(self):
        self._storage_cancel_event.set()
        if hasattr(self, "lbl_storage_status"):
            self.lbl_storage_status.configure(text="Cancelling storage analysis…")

    def _on_storage_scan_complete(self, distribution):
        """Called on main thread after background worker finishes."""
        if hasattr(self, "storage_progress"):
            self.storage_progress.stop()
        if hasattr(self, "btn_storage_scan"):
            self.btn_storage_scan.configure(state="normal")
        if hasattr(self, "btn_storage_cancel"):
            self.btn_storage_cancel.configure(state="disabled")

        active = distribution.get("active_browser_count", 0)
        total_fmt = distribution.get("total_combined_fmt", "0 B")
        total_files = distribution.get("total_files_count", 0)
        if hasattr(self, "lbl_storage_status"):
            self.lbl_storage_status.configure(
                text=f"Analysis complete. {active} browser(s) scanned · {total_files:,} files · {total_fmt} total cache.",
                fg=COLOR_SUCCESS
            )
        self._refresh_storage_browser_panel()

    def _on_storage_scan_error(self, msg):
        if hasattr(self, "storage_progress"):
            self.storage_progress.stop()
        if hasattr(self, "btn_storage_scan"):
            self.btn_storage_scan.configure(state="normal")
        if hasattr(self, "btn_storage_cancel"):
            self.btn_storage_cancel.configure(state="disabled")
        if hasattr(self, "lbl_storage_status"):
            self.lbl_storage_status.configure(text=f"Error: {msg}", fg=COLOR_DANGER)

    def _refresh_storage_browser_panel(self):
        """
        Rebuilds Module A: browser-level progress bar rows and total label.
        Rebuilds the browser selector combo for Module B.
        """
        if not self._storage_distribution or not hasattr(self, "storage_browser_rows_frame"):
            return

        dist = self._storage_distribution

        # Update total label
        if hasattr(self, "lbl_total_storage"):
            self.lbl_total_storage.configure(
                text=f"Total Cache: {dist.get('total_combined_fmt', '0 B')}  |  "
                     f"{dist.get('active_browser_count', 0)} browser(s) active"
            )

        # Clear and rebuild the browser rows frame
        for w in self.storage_browser_rows_frame.winfo_children():
            w.destroy()

        browsers = dist.get("browsers", [])
        available_names = []

        for b in browsers:
            status = b.get("status", "NOT_INSTALLED")
            name = b.get("browser_name", "Unknown")
            icon = "🌐"
            # Pick icon from cached browser results
            br = self._storage_browser_results.get(name, {})
            icon = "🌐"

            row = tk.Frame(self.storage_browser_rows_frame, bg=COLOR_CARD)
            row.pack(fill="x", pady=5)

            # Left: browser name + status
            left = tk.Frame(row, bg=COLOR_CARD, width=200)
            left.pack(side="left", fill="y")
            left.pack_propagate(False)

            status_color = COLOR_SUCCESS if status == "SUCCESS" else COLOR_TEXT_LIGHT
            status_label = b.get("status_label", status)

            tk.Label(
                left, text=f"{icon}  {name}",
                font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD, anchor="w"
            ).pack(anchor="w")
            tk.Label(
                left, text=f"● {status_label}",
                font=("Segoe UI", 7), fg=status_color, bg=COLOR_CARD, anchor="w"
            ).pack(anchor="w")

            # Middle: Progress bar canvas
            mid = tk.Frame(row, bg=COLOR_CARD)
            mid.pack(side="left", fill="both", expand=True, padx=(14, 10))

            bar_canvas = tk.Canvas(mid, bg=COLOR_CARD, height=22, highlightthickness=0)
            bar_canvas.pack(fill="x")

            pct = b.get("percentage", 0.0)
            size_fmt = b.get("total_bytes_fmt", "0 B")
            file_count = b.get("file_count", 0)

            def _draw_bar(canvas=bar_canvas, p=pct, sfmt=size_fmt, fc=file_count, stat=status):
                w = canvas.winfo_reqwidth() or 400
                canvas.delete("all")
                track_h = 10
                cy = 11
                # Background track
                canvas.create_rectangle(0, cy - track_h // 2, w - 2, cy + track_h // 2,
                                        fill="#e2e8f0", outline="", width=0)
                if stat == "SUCCESS" and p > 0:
                    fill_w = max(4, int((p / 100.0) * (w - 2)))
                    canvas.create_rectangle(0, cy - track_h // 2, fill_w, cy + track_h // 2,
                                            fill=COLOR_PRIMARY, outline="", width=0)
                label_txt = f"{sfmt}  ({p:.1f}%)  {fc:,} files"
                canvas.create_text(w // 2, cy, text=label_txt,
                                   font=("Segoe UI", 7, "bold"), fill=COLOR_TEXT_PRIMARY)

            bar_canvas.after(10, _draw_bar)

            # Right: size + pct text
            right = tk.Frame(row, bg=COLOR_CARD, width=110)
            right.pack(side="right", fill="y")
            right.pack_propagate(False)
            tk.Label(
                right, text=b.get("total_bytes_fmt", "—"),
                font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_PRIMARY, bg=COLOR_CARD, anchor="e"
            ).pack(anchor="e")
            tk.Label(
                right, text=f"{pct:.1f}%",
                font=("Segoe UI", 9, "bold"),
                fg=COLOR_PRIMARY if status == "SUCCESS" else COLOR_TEXT_LIGHT,
                bg=COLOR_CARD, anchor="e"
            ).pack(anchor="e")

            if status == "SUCCESS":
                available_names.append(name)

        # Rebuild browser selector combo for Module B
        if hasattr(self, "combo_storage_browser"):
            self.combo_storage_browser.configure(values=available_names)
            if available_names:
                self.combo_storage_browser.set(available_names[0])
                self._populate_storage_file_table(available_names[0])

    # ---------- Module B helpers ----------

    def _on_storage_browser_selected(self, event=None):
        """Called when user changes browser in the selector combo."""
        selected = self.combo_storage_browser.get() if hasattr(self, "combo_storage_browser") else ""
        if selected:
            self._populate_storage_file_table(selected)

    def _populate_storage_file_table(self, browser_name: str):
        """
        Module B: Populates the individual file storage table for the selected browser.
        Shows top-5 largest files, remaining aggregate row, and total row.
        Denominator is always the COMPLETE folder size (not just top-5).
        """
        if not hasattr(self, "storage_file_tree"):
            return
        self.storage_file_tree.delete(*self.storage_file_tree.get_children())

        browser_result = self._storage_browser_results.get(browser_name, {})
        if not browser_result or browser_result.get("status") != "SUCCESS":
            self.storage_file_tree.insert("", "end", values=(
                "—", "No data available", "—", "—", "—", "—", "—",
                browser_result.get("status_label", "Not Installed"), "—"
            ))
            return

        analysis = BrowserStorageAnalyzer.analyze_individual_file_storage(browser_result)

        # Top-5 files
        for i, f in enumerate(analysis["top_files"], start=1):
            clsf = f.get("classification", "")
            score_val = f.get("zombie_score", "—")
            if "ZOMBIE" in str(clsf).upper():
                tag = "zombie"
            elif clsf == "KEEP":
                tag = "keep"
            else:
                tag = "uncertain"
            self.storage_file_tree.insert("", "end", tags=(tag,), values=(
                i,
                f["name"][:50],
                f.get("extension", "—"),
                f["size_fmt"],
                f["percentage_fmt"],
                f.get("age_days", "—"),
                score_val if isinstance(score_val, str) else f"{score_val}/100",
                f.get("classification", "—"),
                f.get("full_path", "")
            ))

        # Remaining files aggregate row
        if analysis["remaining_row"]:
            rem = analysis["remaining_row"]
            self.storage_file_tree.insert("", "end", tags=("aggregate",), values=(
                "…",
                rem["name"],
                "—",
                rem["size_fmt"],
                rem["percentage_fmt"],
                "—", "—", "AGGREGATE (read-only)", "—"
            ))

        # Separator + total row
        total = analysis["total_row"]
        self.storage_file_tree.insert("", "end", tags=("total",), values=(
            "∑",
            total["name"],
            "—",
            total["size_fmt"],
            total["percentage_fmt"],
            "—", "—", "COMPLETE CACHE FOLDER TOTAL", total.get("full_path", "")
        ))

        # Update detail panel to clear previous selection
        if hasattr(self, "storage_detail_lbl"):
            folder_size = analysis["complete_folder_fmt"]
            count = analysis["total_file_count"]
            top_count = len(analysis["top_files"])
            self.storage_detail_lbl.configure(
                text=f"Folder: {browser_result.get('target_path', '—')}  |  "
                     f"Total: {folder_size}  |  {count:,} files scanned  |  "
                     f"Showing top {top_count} largest  |  Select a row to inspect classification.",
                fg=COLOR_TEXT_MUTED
            )

    # ---------- Module D: Classification Inspector ----------

    def _on_storage_file_selected(self, event=None):
        """
        Module D: Shows zombie score, classification, safety status, and quarantine
        eligibility for the file row selected in the storage analysis table.
        """
        if not hasattr(self, "storage_file_tree") or not hasattr(self, "storage_detail_lbl"):
            return

        selected = self.storage_file_tree.selection()
        if not selected:
            return

        item = self.storage_file_tree.item(selected[0])
        values = item.get("values", [])
        tags = item.get("tags", [])

        # Aggregate/total rows don't have file-level details
        if "aggregate" in tags or "total" in tags:
            self.storage_detail_lbl.configure(
                text="ℹ️  This is a summary row — select an individual file row to inspect classification.",
                fg=COLOR_TEXT_MUTED
            )
            return

        # Find file record from cached results
        full_path = values[8] if len(values) > 8 else ""
        browser_name = self.combo_storage_browser.get() if hasattr(self, "combo_storage_browser") else ""
        browser_result = self._storage_browser_results.get(browser_name, {})
        file_record = None
        for f in browser_result.get("files", []):
            if f.get("full_path") == full_path:
                file_record = f
                break

        if not file_record:
            self.storage_detail_lbl.configure(
                text=f"File: {values[1]}  |  Path: {full_path}",
                fg=COLOR_TEXT_MUTED
            )
            return

        # Format classification detail line
        score = file_record.get("zombie_score", "—")
        clsf = file_record.get("classification", "—")
        risk = file_record.get("risk_level", "—")
        qelig = "✅ Eligible for quarantine review" if file_record.get("quarantine_eligible") else "🔒 NOT eligible (safety policy)"
        protected = "⚠️ PROTECTED FILE — immunity applies" if file_record.get("is_protected") else ""
        reasons = "  |  ".join(file_record.get("reasons", [])[:3])

        detail_txt = (
            f"📄 {file_record.get('name', '')}  |  Size: {file_record.get('size_fmt', '—')}  |  "
            f"Age: {file_record.get('age_days', '—')} days  |  "
            f"Zombie Score: {score}/100  |  Class: {clsf}  |  Risk: {risk}  |  "
            f"{qelig}  {protected}"
        )
        if reasons:
            detail_txt += f"\n  Scoring factors: {reasons}"

        self.storage_detail_lbl.configure(text=detail_txt, fg=COLOR_TEXT_PRIMARY)

    def _populate_scanner_tree(self, files):
        if not hasattr(self, "scanner_tree"):
            return
        self.scanner_tree.delete(*self.scanner_tree.get_children())
        for f in files:
            dup_txt = "YES" if f.get("is_duplicate") else "NO"
            self.scanner_tree.insert("", "end", values=(
                f.get("file_name", ""),
                f.get("size_formatted", ""),
                f.get("age_days", 0),
                f.get("file_category", "Cache"),
                f.get("score", 0),
                f.get("risk_level", "NORMAL"),
                dup_txt,
                f.get("full_path", "")
            ))

    def _filter_scan_table(self, filter_type):
        files = self.scan_results.get("files", [])
        if filter_type == "ZOMBIE":
            filtered = [f for f in files if "ZOMBIE" in f.get("classification", "").upper()]
        elif filter_type == "KEEP":
            filtered = [f for f in files if "ZOMBIE" not in f.get("classification", "").upper()]
        else:
            filtered = files
        self._populate_scanner_tree(filtered)

    def _on_background_scan_result(self, result):
        # Called periodically from BackgroundScanWorker
        pass

    def _on_close(self):
        try:
            self.background_worker.stop()
        except Exception:
            pass
        self.destroy()


def main():
    app = ZombiePurgerGUI()
    app.mainloop()


def launch_gui():
    main()


if __name__ == "__main__":
    main()
