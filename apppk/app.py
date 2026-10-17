import customtkinter as ctk
import requests
import threading
import time
import json
import os
import sys
import math
import random
import re
import tkinter as tk
from datetime import datetime

# ============================================================
# КОНФИГ
# ============================================================
API_URL = "https://telegramprobot.relaxdev.ru/webhook"
APP_TOKEN = "871410danil"
APP_VERSION = "7.0.0-ultra"

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".redsave_config.json")
HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".redsave_history.json")

COLOR_THEMES = {
    1: ("#0a1929", "#4da6ff", "#2a5d8f", "Ocean"),
    2: ("#0a1f0a", "#33ff33", "#1a5c1a", "Matrix"),
    3: ("#1f0a0a", "#ff4d4d", "#8f2a2a", "Crimson"),
    4: ("#1f1400", "#ffa64d", "#8f5a2a", "Sunset"),
    5: ("#0a0510", "#c084fc", "#6d28d9", "Aurora"),
    6: ("#1a0a1f", "#e879f9", "#a21caf", "Neon"),
    7: ("#001a1a", "#22d3ee", "#0e7490", "Cyber"),
    8: ("#1a1a00", "#facc15", "#a16207", "Gold"),
}

ALIASES = {"cls": "clear", "q": "ping", "h": "help",
           "b": "banlist", "l": "idlist", "?": "help"}

FORTUNES = [
    "«Код — это поэзия, только компилятор — критик.»",
    "«Преждевременная оптимизация — корень всех зол.» — Дональд Кнут",
    "«Простота — высшая форма изящества.» — Леонардо да Винчи",
    "«Работает? Не трогай!» — Народная мудрость",
    "«Программист — это машина, превращающая кофе в код.»",
    "«Хороший код — это код, который легко удалить.»",
]

# ============================================================
# УТИЛИТЫ
# ============================================================
def parse_duration(s):
    if not s: return 0
    s = s.strip().lower()
    matches = re.findall(r'(\d+)\s*([hms])', s)
    if not matches:
        return int(s) * 60 if s.isdigit() else 0
    total = 0
    for value, unit in matches:
        v = int(value)
        if unit == "h": total += v * 3600
        elif unit == "m": total += v * 60
        elif unit == "s": total += v
    return total

def format_duration(seconds):
    if seconds <= 0: return "0s"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s and not h: parts.append(f"{s}s")
    return " ".join(parts) if parts else "0s"

# ============================================================
# ПАЛИТРА (Aurora Premium)
# ============================================================
class Palette:
    # Глубокие фоны
    BG_VOID = "#030108"
    BG_DEEP = "#070312"
    BG_DARK = "#0c0518"
    BG_PANEL = "#13081f"
    BG_CARD = "#1a0f28"
    BG_CARD_HOVER = "#251538"
    BG_INPUT = "#0e0618"
    BG_GLASS = "#1a0f2880"
    
    # Границы
    BORDER = "#2d1a45"
    BORDER_LIGHT = "#3d2560"
    BORDER_GLASS = "#ffffff15"
    
    # Текст
    TEXT = "#ffffff"
    TEXT_DIM = "#b8a5d4"
    TEXT_DIM2 = "#7a6899"
    TEXT_MUTED = "#4a3d66"
    
    # Градиентные акценты
    ACCENT = "#a855f7"
    ACCENT_HOVER = "#9333ea"
    ACCENT_GLOW = "#d8b4fe"
    ACCENT_DEEP = "#7e22ce"
    
    # Неоновые
    NEON_PINK = "#ec4899"
    NEON_CYAN = "#06b6d4"
    NEON_BLUE = "#3b82f6"
    NEON_PURPLE = "#a855f7"
    
    # Статусы
    SUCCESS = "#10b981"
    SUCCESS_GLOW = "#34d399"
    ERROR = "#ef4444"
    ERROR_GLOW = "#f87171"
    WARNING = "#f59e0b"
    WARNING_GLOW = "#fbbf24"
    INFO = "#3b82f6"

# ============================================================
# NETWORK MONITOR
# ============================================================
class NetworkMonitor:
    def __init__(self, limit=300):
        self.requests = []
        self.limit = limit
        self.lock = threading.Lock()

    def log(self, method, url, status, duration_ms, size=0, error=None):
        entry = {"ts": time.time(), "method": method, "url": url,
                 "status": status, "duration_ms": duration_ms,
                 "size": size, "error": error}
        with self.lock:
            self.requests.append(entry)
            if len(self.requests) > self.limit:
                self.requests.pop(0)

    def get_all(self):
        with self.lock: return list(self.requests)

    def clear(self):
        with self.lock: self.requests.clear()

NET_MONITOR = NetworkMonitor(limit=300)

# ============================================================
# КОНФИГ / ИСТОРИЯ
# ============================================================
def load_config():
    defaults = {"color": 5, "font_size": 13, "sound": True, "lang": "ru",
                "window_geometry": "1440x920", "aliases": {}}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                defaults.update(json.load(f))
        except Exception: pass
    return defaults

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception: pass

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass
    return []

def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history[-200:], f, ensure_ascii=False, indent=2)
    except Exception: pass

def play_sound(kind="ok", enabled=True):
    if not enabled: return
    try:
        if sys.platform == "win32":
            import winsound
            if kind == "ok": winsound.MessageBeep(winsound.MB_ICONASTERISK)
            elif kind == "err": winsound.MessageBeep(winsound.MB_ICONHAND)
            elif kind == "warn": winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception: pass

# ============================================================
# API КЛИЕНТ
# ============================================================
class BotAPI:
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.headers = {"X-App-Token": token, "Content-Type": "application/json"}

    def _post(self, endpoint, data=None):
        url = f"{self.base_url}/api/{endpoint}"
        t0 = time.time()
        status = 0
        size = 0
        error = None
        try:
            r = requests.post(url, headers=self.headers, json=data or {}, timeout=15)
            status = r.status_code
            size = len(r.content)
            r.raise_for_status()
            result = r.json()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            size = len(e.response.content) if e.response is not None else 0
            if status == 401: result = {"error": "Неверный токен"}
            elif status == 423: result = {"error": "Бот на паузе"}
            elif status == 404: result = {"error": "404"}
            else: result = {"error": f"HTTP {status}"}
            error = result["error"]
        except requests.exceptions.ConnectionError:
            result = {"error": "Нет соединения"}
            error = "ConnectionError"
        except requests.exceptions.Timeout:
            result = {"error": "Таймаут"}
            error = "Timeout"
        except Exception as e:
            result = {"error": str(e)}
            error = str(e)
        duration = int((time.time() - t0) * 1000)
        NET_MONITOR.log("POST", url, status, duration, size, error)
        return result

    def ping(self): return self._post("ping")
    def status(self): return self._post("status")
    def command(self, cmd): return self._post("command", {"command": cmd})
    def pause(self): return self._post("pause")
    def resume(self): return self._post("resume")

# ============================================================
# АНИМИРОВАННЫЙ ГРАДИЕНТНЫЙ ФОН (Aurora)
# ============================================================
class AuroraBackground(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)
        self.phase = 0
        self.blobs = []
        self._animate()

    def _init_blobs(self, w, h):
        self.blobs = [
            {"x": w * 0.2, "y": h * 0.3, "r": 280, "c": (168, 85, 247), "vx": 0.3, "vy": 0.2},
            {"x": w * 0.8, "y": h * 0.7, "r": 320, "c": (236, 72, 153), "vx": -0.2, "vy": 0.3},
            {"x": w * 0.5, "y": h * 0.5, "r": 260, "c": (6, 182, 212), "vx": 0.25, "vy": -0.25},
            {"x": w * 0.7, "y": h * 0.2, "r": 220, "c": (59, 130, 246), "vx": -0.3, "vy": -0.15},
        ]

    def _animate(self):
        if not self.winfo_exists():
            self.after(100, self._animate)
            return
        try:
            w = self.winfo_width() or 1440
            h = self.winfo_height() or 920
            
            if not self.blobs:
                self._init_blobs(w, h)
            
            self.delete("all")
            
            # Базовый тёмный фон
            self.create_rectangle(0, 0, w, h, fill=Palette.BG_VOID, outline="")
            
            # Двигаем blobs
            for b in self.blobs:
                b["x"] += b["vx"]
                b["y"] += b["vy"]
                if b["x"] < -b["r"]: b["x"] = w + b["r"]
                if b["x"] > w + b["r"]: b["x"] = -b["r"]
                if b["y"] < -b["r"]: b["y"] = h + b["r"]
                if b["y"] > h + b["r"]: b["y"] = -b["r"]
            
            # Рисуем blobs с градиентным затуханием
            for b in self.blobs:
                r, g, bl = b["c"]
                # Внешнее свечение (очень прозрачное)
                for i in range(8, 0, -1):
                    radius = b["r"] * (i / 8)
                    alpha = int(15 * (i / 8))
                    color = f"#{r:02x}{g:02x}{bl:02x}"
                    self.create_oval(
                        b["x"] - radius, b["y"] - radius,
                        b["x"] + radius, b["y"] + radius,
                        fill=color, outline="", stipple="gray25"
                    )
            
            # Шум/зерно
            self.phase = (self.phase + 0.5) % 360
            
        except Exception: pass
        self.after(60, self._animate)

# ============================================================
# ГРАДИЕНТНАЯ КНОПКА (Glassmorphism)
# ============================================================
class GradientButton(ctk.CTkFrame):
    def __init__(self, parent, text, command=None, color=Palette.ACCENT, 
                 width=140, height=44, icon=""):
        super().__init__(parent, fg_color="transparent", width=width, height=height)
        self.pack_propagate(False)
        self.command = command
        self.color = color
        self.is_hover = False
        
        # Основной контейнер с градиентным эффектом
        self.btn_bg = ctk.CTkFrame(self, fg_color=Palette.BG_CARD, 
                                    corner_radius=14,
                                    border_width=1, border_color=Palette.BORDER)
        self.btn_bg.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Внутренний контент
        inner = ctk.CTkFrame(self.btn_bg, fg_color="transparent")
        inner.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        content = ctk.CTkFrame(inner, fg_color="transparent")
        content.place(relx=0.5, rely=0.5, anchor="center")
        
        if icon:
            ctk.CTkLabel(content, text=icon, font=ctk.CTkFont(size=16),
                         text_color=color).pack(side="left", padx=(0, 6))
        
        self.text_label = ctk.CTkLabel(content, text=text,
                                        font=ctk.CTkFont(size=12, weight="bold"),
                                        text_color=color)
        self.text_label.pack(side="left")
        
        # Bindings
        for w in (self, self.btn_bg, inner, content, self.text_label):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_click)

    def _on_enter(self, e):
        self.is_hover = True
        try:
            self.btn_bg.configure(fg_color=Palette.BG_CARD_HOVER,
                                   border_color=self.color)
        except Exception: pass

    def _on_leave(self, e):
        self.is_hover = False
        try:
            self.btn_bg.configure(fg_color=Palette.BG_CARD,
                                   border_color=Palette.BORDER)
        except Exception: pass

    def _on_click(self, e):
        if self.command: self.command()

    def configure_text(self, text, color=None):
        try:
            self.text_label.configure(text=text)
            if color:
                self.text_label.configure(text_color=color)
                self.color = color
        except Exception: pass

# ============================================================
# TOP NAVIGATION BAR
# ============================================================
class TopNavBar(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent", height=72)
        self.pack_propagate(False)
        self.app = app
        self.build()

    def build(self):
        # Стеклянная подложка
        self.glass = ctk.CTkFrame(self, fg_color=Palette.BG_PANEL,
                                   corner_radius=0, height=72,
                                   border_width=0)
        self.glass.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Нижний бордер с градиентом
        self.border_line = tk.Canvas(self, height=1, bg=Palette.BG_PANEL,
                                      highlightthickness=0)
        self.border_line.place(relx=0, rely=1, relwidth=1, height=1)
        
        # Внутренний контейнер
        inner = ctk.CTkFrame(self.glass, fg_color="transparent")
        inner.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # ЛЕВАЯ ЧАСТЬ: Логотип
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", padx=(28, 0), fill="y")
        
        # Логотип с градиентной иконкой
        logo_frame = ctk.CTkFrame(left, fg_color="transparent")
        logo_frame.pack(side="left", fill="y")
        
        # Анимированный градиентный круг
        self.logo_canvas = tk.Canvas(logo_frame, width=42, height=42,
                                      bg=Palette.BG_PANEL, highlightthickness=0)
        self.logo_canvas.pack(side="left", padx=(0, 12))
        self.logo_phase = 0
        self._animate_logo()
        
        tf = ctk.CTkFrame(logo_frame, fg_color="transparent")
        tf.pack(side="left", fill="y")
        ctk.CTkLabel(tf, text="RedSave", font=ctk.CTkFont(size=18, weight="bold"),
                      text_color=Palette.TEXT).pack(anchor="w", pady=(14, 0))
        ctk.CTkLabel(tf, text=f"v{APP_VERSION}", font=ctk.CTkFont(size=10),
                      text_color=Palette.TEXT_DIM2).pack(anchor="w")
        
        # Разделитель
        ctk.CTkFrame(left, fg_color=Palette.BORDER, width=1, height=32).pack(side="left", padx=24)
        
        # ЦЕНТР: Навигация (табы)
        center = ctk.CTkFrame(inner, fg_color="transparent")
        center.pack(side="left", fill="y", padx=(0, 20))
        
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "⌂", "Dashboard"),
            ("terminal", "▶_", "Terminal"),
            ("bans", "⊘", "Bans"),
            ("network", "◉", "Network"),
            ("settings", "⚙", "Settings"),
        ]
        
        for k, icon, lbl in nav_items:
            btn = NavTab(center, lbl, icon,
                         command=lambda kk=k: self.app._switch_tab(kk),
                         active=(k == "dashboard"))
            btn.pack(side="left", padx=2)
            self.nav_buttons[k] = btn
        
        # ПРАВАЯ ЧАСТЬ: Статус и действия
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right", padx=(0, 28), fill="y")
        
        # Статус-индикатор
        self.status_pill = ctk.CTkFrame(right, fg_color=Palette.BG_CARD,
                                         corner_radius=20, height=38,
                                         border_width=1, border_color=Palette.BORDER)
        self.status_pill.pack(side="left", padx=(0, 12))
        self.status_pill.pack_propagate(False)
        self.status_pill.configure(width=130)
        
        status_inner = ctk.CTkFrame(self.status_pill, fg_color="transparent")
        status_inner.pack(fill="both", expand=True, padx=12)
        
        # Анимированная точка статуса
        self.status_dot_canvas = tk.Canvas(status_inner, width=14, height=14,
                                            bg=Palette.BG_CARD, highlightthickness=0)
        self.status_dot_canvas.pack(side="left", padx=(0, 8))
        self.status_dot = self.status_dot_canvas.create_oval(3, 3, 11, 11,
                                                              fill=Palette.TEXT_DIM2, outline="")
        self._animate_status_dot()
        
        self.status_text = ctk.CTkLabel(status_inner, text="Checking...",
                                         font=ctk.CTkFont(size=11, weight="bold"),
                                         text_color=Palette.TEXT_DIM)
        self.status_text.pack(side="left")
        
        # Кнопка паузы
        self.pause_btn = GradientButton(right, "Pause", 
                                         command=self.app._toggle_pause,
                                         color=Palette.TEXT_DIM,
                                         width=110, height=38, icon="⏸")
        self.pause_btn.pack(side="left")

    def _animate_logo(self):
        if not self.logo_canvas.winfo_exists(): return
        try:
            self.logo_canvas.delete("all")
            self.logo_phase = (self.logo_phase + 2) % 360
            
            # Градиентный круг с вращением
            cx, cy = 21, 21
            r = 18
            
            # Внешнее свечение
            glow_r = r + 2 + math.sin(self.logo_phase * math.pi / 180) * 2
            self.logo_canvas.create_oval(cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r,
                                          fill="", outline=Palette.ACCENT_GLOW, width=1, stipple="gray25")
            
            # Основной круг с градиентом
            self.logo_canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                          fill=Palette.ACCENT, outline="")
            
            # Блик
            self.logo_canvas.create_oval(cx - r + 4, cy - r + 4, cx - r + 12, cy - r + 12,
                                          fill=Palette.ACCENT_GLOW, outline="")
            
            # Молния (символ)
            bolt = [
                (cx - 2, cy - 8),
                (cx + 4, cy - 8),
                (cx, cy - 1),
                (cx + 5, cy - 1),
                (cx - 3, cy + 9),
                (cx + 1, cy + 1),
                (cx - 4, cy + 1),
            ]
            self.logo_canvas.create_polygon(bolt, fill="#ffffff", outline="")
            
        except Exception: pass
        self.after(50, self._animate_logo)

    def _animate_status_dot(self):
        if not self.status_dot_canvas.winfo_exists(): return
        try:
            phase = (time.time() * 2) % (2 * math.pi)
            scale = 1 + 0.15 * math.sin(phase)
            cx, cy = 7, 7
            r = 4 * scale
            self.status_dot_canvas.coords(self.status_dot, cx - r, cy - r, cx + r, cy + r)
        except Exception: pass
        self.after(50, self._animate_status_dot)

    def set_status(self, state, ping=None):
        colors = {
            "online": (Palette.SUCCESS, "Online"),
            "paused": (Palette.WARNING, "Paused"),
            "offline": (Palette.ERROR, "Offline"),
            "unknown": (Palette.TEXT_DIM2, "Checking..."),
        }
        color, text = colors.get(state, colors["unknown"])
        
        try:
            self.status_dot_canvas.itemconfig(self.status_dot, fill=color)
            self.status_text.configure(text=text, text_color=color)
            self.status_pill.configure(border_color=color)
        except Exception: pass

    def set_pause_state(self, paused):
        try:
            if paused:
                self.pause_btn.configure_text("Resume", Palette.SUCCESS)
            else:
                self.pause_btn.configure_text("Pause", Palette.TEXT_DIM)
        except Exception: pass

# ============================================================
# НАВИГАЦИОННЫЙ ТАБ
# ============================================================
class NavTab(ctk.CTkFrame):
    def __init__(self, parent, text, icon, command=None, active=False):
        super().__init__(parent, fg_color="transparent", height=44)
        self.pack_propagate(False)
        self.command = command
        self.active = active
        
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14)
        
        # Иконка
        self.icon_label = ctk.CTkLabel(inner, text=icon,
                                        font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
                                        text_color=Palette.ACCENT if active else Palette.TEXT_DIM2,
                                        width=22)
        self.icon_label.pack(side="left")
        
        # Текст
        self.text_label = ctk.CTkLabel(inner, text=text,
                                        font=ctk.CTkFont(size=12, weight="bold"),
                                        text_color=Palette.TEXT if active else Palette.TEXT_DIM)
        self.text_label.pack(side="left", padx=(4, 0))
        
        # Индикатор снизу
        self.indicator = tk.Canvas(self, width=60, height=2,
                                    bg="transparent", highlightthickness=0)
        self.indicator.place(relx=0.5, rely=1, anchor="s")
        self.indicator_line = self.indicator.create_rectangle(
            0, 0, 60, 2,
            fill=Palette.ACCENT if active else "",
            outline=""
        )
        
        self._set_active(active)
        for w in (self, inner, self.icon_label, self.text_label):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_click)

    def _set_active(self, active):
        self.active = active
        if active:
            self.icon_label.configure(text_color=Palette.ACCENT)
            self.text_label.configure(text_color=Palette.TEXT)
            self.indicator.itemconfig(self.indicator_line, fill=Palette.ACCENT)
        else:
            self.icon_label.configure(text_color=Palette.TEXT_DIM2)
            self.text_label.configure(text_color=Palette.TEXT_DIM)
            self.indicator.itemconfig(self.indicator_line, fill="")

    def _on_enter(self, e):
        if not self.active:
            self.text_label.configure(text_color=Palette.TEXT)
            self.icon_label.configure(text_color=Palette.TEXT_DIM)

    def _on_leave(self, e):
        if not self.active:
            self.text_label.configure(text_color=Palette.TEXT_DIM)
            self.icon_label.configure(text_color=Palette.TEXT_DIM2)

    def _on_click(self, e):
        if self.command: self.command()

# ============================================================
# BENTO CARD (разные размеры)
# ============================================================
class BentoCard(ctk.CTkFrame):
    def __init__(self, parent, title="", icon="", accent=Palette.ACCENT,
                 subtitle="", large_value=""):
        super().__init__(parent, fg_color=Palette.BG_CARD, corner_radius=20,
                         border_width=1, border_color=Palette.BORDER)
        self.accent = accent
        
        # Внутренний контейнер
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=24, pady=20)
        
        # Заголовок с иконкой
        if title or icon:
            header = ctk.CTkFrame(inner, fg_color="transparent")
            header.pack(fill="x")
            
            if icon:
                # Градиентный фон иконки
                icon_bg = ctk.CTkFrame(header, fg_color=accent, corner_radius=10,
                                        width=36, height=36)
                icon_bg.pack(side="left", padx=(0, 12))
                icon_bg.pack_propagate(False)
                ctk.CTkLabel(icon_bg, text=icon,
                             font=ctk.CTkFont(size=16),
                             text_color="#ffffff").pack()
            
            title_frame = ctk.CTkFrame(header, fg_color="transparent")
            title_frame.pack(side="left", fill="y")
            
            if title:
                ctk.CTkLabel(title_frame, text=title,
                             font=ctk.CTkFont(size=11, weight="bold"),
                             text_color=Palette.TEXT_DIM2).pack(anchor="w")
            if subtitle:
                ctk.CTkLabel(title_frame, text=subtitle,
                             font=ctk.CTkFont(size=10),
                             text_color=Palette.TEXT_MUTED).pack(anchor="w")
        
        # Большое значение
        if large_value:
            self.value_label = ctk.CTkLabel(inner, text=large_value,
                                             font=ctk.CTkFont(size=42, weight="bold"),
                                             text_color=accent)
            self.value_label.pack(anchor="w", pady=(14, 0))
        
        self.bind("<Enter>", self._hover_in)
        self.bind("<Leave>", self._hover_out)

    def set_value(self, value):
        if hasattr(self, "value_label"):
            self.value_label.configure(text=value)

    def _hover_in(self, e):
        try:
            self.configure(border_color=self.accent, border_width=2)
        except Exception: pass

    def _hover_out(self, e):
        try:
            self.configure(border_color=Palette.BORDER, border_width=1)
        except Exception: pass

# ============================================================
# СТАТУСНЫЙ РИНГ (с ИДЕАЛЬНО РОВНЫМИ иконками)
# ============================================================
class StatusRing(tk.Canvas):
    def __init__(self, parent, size=120, bg=Palette.BG_CARD):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        self.size = size
        self.state = "unknown"
        self.pulse = 0
        self._animate()

    def set_state(self, state): self.state = state

    def _animate(self):
        if not self.winfo_exists(): return
        try:
            self.delete("all")
            cx = cy = self.size / 2
            r = self.size / 2 - 12
            colors = {"online": Palette.SUCCESS, "paused": Palette.WARNING,
                      "offline": Palette.ERROR, "unknown": Palette.TEXT_DIM2}
            color = colors.get(self.state, Palette.TEXT_DIM2)
            self.pulse = (self.pulse + 1) % 60
            
            # Внешнее свечение (пульсирующее)
            glow_r = r + 6 + 3 * math.sin(self.pulse / 60 * 2 * math.pi)
            self.create_oval(cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r,
                             outline=color, width=1, stipple="gray25")
            
            # Второе кольцо
            ring_r = r + 3 * math.sin(self.pulse / 60 * 2 * math.pi)
            self.create_oval(cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r,
                             outline=color, width=2, fill="")
            
            # Основное кольцо
            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                             outline=color, width=3, fill="")
            
            # Центральный круг
            r2 = 14
            self.create_oval(cx - r2, cy - r2, cx + r2, cy + r2, fill=color, outline="")
            
            # ИДЕАЛЬНО РОВНАЯ ИКОНКА В ЦЕНТРЕ
            if self.state == "online":
                # ГАЛОЧКА — математически точная
                # Три точки образуют правильную галочку
                offset = r2 * 0.55
                x1 = cx - offset * 0.75
                y1 = cy + offset * 0.05
                x2 = cx - offset * 0.15
                y2 = cy + offset * 0.55
                x3 = cx + offset * 0.80
                y3 = cy - offset * 0.50
                
                self.create_line(x1, y1, x2, y2, fill="#ffffff", width=3, 
                                 capstyle="round", joinstyle="round")
                self.create_line(x2, y2, x3, y3, fill="#ffffff", width=3,
                                 capstyle="round", joinstyle="round")
            elif self.state == "offline":
                # КРЕСТИК — математически точный
                offset = r2 * 0.50
                self.create_line(cx - offset, cy - offset, cx + offset, cy + offset,
                                 fill="#ffffff", width=3, capstyle="round")
                self.create_line(cx + offset, cy - offset, cx - offset, cy + offset,
                                 fill="#ffffff", width=3, capstyle="round")
            elif self.state == "paused":
                # ПАУЗА — две вертикальные линии
                offset = r2 * 0.35
                line_h = r2 * 0.70
                self.create_rectangle(cx - offset - 3, cy - line_h/2,
                                       cx - offset + 3, cy + line_h/2,
                                       fill="#ffffff", outline="")
                self.create_rectangle(cx + offset - 3, cy - line_h/2,
                                       cx + offset + 3, cy + line_h/2,
                                       fill="#ffffff", outline="")
            else:
                # НЕИЗВЕСТНО — точка
                self.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill="#ffffff", outline="")
                
        except Exception: pass
        try: self.after(50, self._animate)
        except Exception: pass

# ============================================================
# MAINTENANCE BADGE (с ИДЕАЛЬНО РОВНЫМИ иконками)
# ============================================================
class MaintenanceBadge(tk.Canvas):
    def __init__(self, parent, width=340, height=48, bg=Palette.BG_PANEL):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0)
        self.w = width
        self.h = height
        self.active = False
        self.phase = 0
        self.remaining = 0
        self._draw()
        self._animate()

    def set_state(self, active, remaining=0):
        self.active = active
        self.remaining = remaining

    def _draw(self):
        try:
            self.delete("all")
            w, h = self.w, self.h
            cy = h / 2
            pad = 6
            pill_h = h - 2 * pad

            if self.active:
                color = Palette.ERROR
                glow = Palette.ERROR_GLOW
                text = "Maintenance"
                if self.remaining > 0:
                    text = f"Maintenance · {format_duration(self.remaining)}"
            else:
                color = Palette.SUCCESS
                glow = Palette.SUCCESS_GLOW
                text = "All Systems Operational"

            text_w = 7 * len(text) + 32
            circle_w = pill_h
            pill_w = min(w, circle_w + text_w + 28)
            r = pill_h / 2

            # Фон таблетки
            self.create_oval(pad, pad, pad + pill_h, h - pad, fill=Palette.BG_CARD, outline="")
            self.create_oval(pill_w - pad - pill_h, pad, pill_w - pad, h - pad, fill=Palette.BG_CARD, outline="")
            self.create_rectangle(pad + r, pad, pill_w - pad - r, h - pad, fill=Palette.BG_CARD, outline="")

            # Обводка
            self.create_arc(pad, pad, pad + pill_h, h - pad, start=90, extent=180,
                            outline=color, style="arc", width=1)
            self.create_arc(pill_w - pad - pill_h, pad, pill_w - pad, h - pad, start=270, extent=180,
                            outline=color, style="arc", width=1)
            self.create_line(pad + r, pad, pill_w - pad - r, pad, fill=color, width=1)
            self.create_line(pad + r, h - pad, pill_w - pad - r, h - pad, fill=color, width=1)

            # Свечение если активно
            if self.active:
                gx = pad + r
                glow_size = r + 8 + 2 * math.sin(self.phase / 30 * math.pi)
                self.create_oval(gx - glow_size, cy - glow_size, gx + glow_size, cy + glow_size,
                                 fill="", outline=glow, width=2, stipple="gray50")

            # Иконка: центр круга
            cx = pad + r
            cr = r - 5
            
            # Рисуем цветной круг
            self.create_oval(cx - cr, cy - cr, cx + cr, cy + cr, fill=color, outline="")

            # ИДЕАЛЬНО РОВНЫЕ ИКОНКИ
            if self.active:
                # КРЕСТИК
                offset = cr * 0.45
                self.create_line(cx - offset, cy - offset, cx + offset, cy + offset,
                                 fill="#ffffff", width=2.5, capstyle="round")
                self.create_line(cx + offset, cy - offset, cx - offset, cy + offset,
                                 fill="#ffffff", width=2.5, capstyle="round")
            else:
                # ГАЛОЧКА
                x1 = cx - cr * 0.45
                y1 = cy + cr * 0.05
                x2 = cx - cr * 0.05
                y2 = cy + cr * 0.45
                x3 = cx + cr * 0.50
                y3 = cy - cr * 0.40
                
                self.create_line(x1, y1, x2, y2, fill="#ffffff", width=2.5,
                                 capstyle="round", joinstyle="round")
                self.create_line(x2, y2, x3, y3, fill="#ffffff", width=2.5,
                                 capstyle="round", joinstyle="round")

            # Текст
            self.create_text(pad + pill_h + 16, cy, text=text, anchor="w",
                             fill=Palette.TEXT, font=("Inter", 12, "bold"))
        except Exception: pass

    def _animate(self):
        if not self.winfo_exists(): return
        try:
            self.phase = (self.phase + 1) % 60
            self._draw()
        except Exception: pass
        try: self.after(50, self._animate)
        except Exception: pass

# ============================================================
# RTT GRAPH (обновлённый)
# ============================================================
class RTTGraph(tk.Canvas):
    def __init__(self, parent, width=280, height=80, bg=Palette.BG_CARD):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0)
        self.width = width
        self.height = height
        self.values = [0] * 40
        self.max_v = 200
        self._draw()

    def push(self, value):
        if value is None or value < 0: value = 0
        self.values.pop(0)
        self.values.append(value)
        self.max_v = max(200, max(self.values) + 20)
        self._draw()

    def _draw(self):
        try:
            self.delete("all")
            w, h = self.width, self.height
            
            # Сетка
            for i in range(1, 4):
                y = h * i / 4
                self.create_line(0, y, w, y, fill=Palette.BORDER, dash=(2, 3), width=1)
            
            n = len(self.values)
            step = w / max(1, n - 1)
            points = []
            for i, v in enumerate(self.values):
                x = i * step
                y = h - (v / self.max_v) * h
                points.extend([x, y])
            
            if len(points) >= 4:
                # Градиентная заливка
                poly = points + [w, h, 0, h]
                self.create_polygon(*poly, fill=Palette.ACCENT, outline="", stipple="gray25")
                
                # Двойная линия для неонового эффекта
                self.create_line(*points, fill=Palette.ACCENT_GLOW, width=4, smooth=True, stipple="gray50")
                self.create_line(*points, fill=Palette.ACCENT, width=2, smooth=True)
                
                # Точка на последнем значении
                last_x = (n - 1) * step
                last_y = h - (self.values[-1] / self.max_v) * h
                self.create_oval(last_x - 4, last_y - 4, last_x + 4, last_y + 4,
                                 fill=Palette.ACCENT_GLOW, outline="")
                self.create_oval(last_x - 2, last_y - 2, last_x + 2, last_y + 2,
                                 fill="#ffffff", outline="")
            
            # Текущее значение
            cur = self.values[-1]
            color = Palette.SUCCESS if cur < 100 else (Palette.WARNING if cur < 500 else Palette.ERROR)
            self.create_text(w - 12, 16, text=f"{cur}ms", anchor="e",
                             fill=color, font=("Consolas", 13, "bold"))
        except Exception: pass

# ============================================================
# ТЕРМИНАЛ (в стиле Warp)
# ============================================================
class Terminal(ctk.CTkFrame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.app = app
        self.history = load_history()
        self.history_index = len(self.history)
        self.aliases = dict(ALIASES)
        self.aliases.update(app.config_data.get("aliases", {}))
        self.sticky_scroll = True
        self.build()

    def build(self):
        self.term_container = ctk.CTkFrame(
            self, fg_color=Palette.BG_DEEP, corner_radius=24,
            border_width=1, border_color=Palette.BORDER)
        self.term_container.pack(fill="both", expand=True)
        self.term_container.grid_columnconfigure(0, weight=1)
        self.term_container.grid_rowconfigure(1, weight=1)

        # Заголовок терминала
        title_bar = ctk.CTkFrame(self.term_container, fg_color=Palette.BG_PANEL,
                                  corner_radius=0, height=52)
        title_bar.grid(row=0, column=0, sticky="ew")
        title_bar.grid_propagate(False)

        # Traffic lights
        self.traffic = tk.Canvas(title_bar, width=68, height=24,
                                  bg=Palette.BG_PANEL, highlightthickness=0)
        self.traffic.pack(side="left", padx=(22, 18))
        self._tc1 = self.traffic.create_oval(4, 4, 20, 20, fill="#ff5f57", outline="")
        self._tc2 = self.traffic.create_oval(26, 4, 42, 20, fill="#febc2e", outline="")
        self._tc3 = self.traffic.create_oval(48, 4, 64, 20, fill="#28c840", outline="")

        # Заголовок
        self.term_title = ctk.CTkLabel(
            title_bar, text="⚡ redsave — terminal",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=Palette.TEXT_DIM)
        self.term_title.pack(side="left", padx=14)

        # Кнопка Live
        self.live_btn = ctk.CTkButton(
            title_bar, text="", width=100, height=30,
            fg_color="transparent", hover_color=Palette.BG_CARD,
            text_color=Palette.ACCENT_GLOW,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._jump_to_end)
        self.live_btn.pack(side="right", padx=18)

        # Поле вывода
        self.terminal = ctk.CTkTextbox(
            self.term_container,
            font=ctk.CTkFont(family="Consolas", size=self.app.config_data.get("font_size", 13)),
            fg_color=Palette.BG_DEEP, border_width=0, corner_radius=0,
            text_color=Palette.TEXT, wrap="word")
        self.terminal.grid(row=1, column=0, sticky="nsew")
        for ev in ("<Key>", "<<Paste>>", "<BackSpace>", "<Delete>", "<Control-v>", "<Control-V>"):
            self.terminal.bind(ev, lambda e: "break")
        self.terminal.bind("<Control-c>", self._copy_selection)
        self.terminal.bind("<Control-C>", self._copy_selection)
        self.terminal.bind("<MouseWheel>", self._on_scroll)
        self.terminal.bind("<Button-4>", self._on_scroll)
        self.terminal.bind("<Button-5>", self._on_scroll)
        self.terminal.bind("<Button-3>", lambda e: self._clear_terminal())
        self.terminal.bind("<Button-1>", self._on_terminal_click)

        # Поле ввода
        input_container = ctk.CTkFrame(self.term_container, fg_color=Palette.BG_INPUT,
                                        corner_radius=0, height=68)
        input_container.grid(row=2, column=0, sticky="ew")
        input_container.grid_propagate(False)

        # Промпт
        self.prompt = ctk.CTkLabel(
            input_container, text="❯",
            font=ctk.CTkFont(family="Consolas", size=22, weight="bold"),
            text_color=Palette.ACCENT)
        self.prompt.pack(side="left", padx=(28, 14))
        self._start_prompt_pulse()

        # Поле ввода команды
        self.entry = ctk.CTkEntry(
            input_container,
            placeholder_text="type a command... (help, ping, tex on 1h)",
            font=ctk.CTkFont(family="Consolas", size=self.app.config_data.get("font_size", 13)),
            fg_color="transparent", border_width=0,
            text_color=Palette.TEXT, placeholder_text_color=Palette.TEXT_MUTED)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 18), pady=18)
        self.entry.bind("<Return>", lambda e: self.on_enter())
        self.entry.bind("<Up>", self.history_up)
        self.entry.bind("<Down>", self.history_down)
        self.entry.bind("<Tab>", self.autocomplete)
        self.entry.bind("<Control-v>", self._paste)
        self.entry.bind("<Control-V>", self._paste)
        self.entry.focus_set()

        # Кнопка Run
        ctk.CTkButton(
            input_container, text="Run ↵", width=110, height=42,
            fg_color=Palette.ACCENT, hover_color=Palette.ACCENT_HOVER,
            text_color="#ffffff", corner_radius=14,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.on_enter).pack(side="right", padx=(0, 28), pady=13)

        # Прогресс бар
        self.progress = ctk.CTkProgressBar(self.term_container, height=3,
                                            progress_color=Palette.ACCENT_GLOW)
        self.progress.grid(row=3, column=0, sticky="ew")
        self.progress.grid_remove()
        self.progress.configure(mode="indeterminate")

        # Приветственное сообщение
        self.typing_queue = [
            (f"⚡ redsave terminal {APP_VERSION}", "header"),
            (f"→ api: {API_URL}", "info"),
            (f"💭 {random.choice(FORTUNES)}", "info"),
            ("→ tex on 1h / tex off — maintenance mode", "info"),
            ("→ help — available commands", "info"),
            ("", "normal"),
        ]
        self.after(200, self._type_next)

    def _start_prompt_pulse(self):
        def pulse(i=0):
            if not self.prompt.winfo_exists(): return
            try:
                colors = [Palette.ACCENT, Palette.ACCENT_GLOW, Palette.NEON_CYAN, Palette.ACCENT]
                self.prompt.configure(text_color=colors[i % len(colors)])
            except Exception: pass
            try: self.after(400, lambda: pulse(i + 1))
            except Exception: pass
        pulse()

    def _type_next(self):
        if not self.typing_queue: return
        text, kind = self.typing_queue.pop(0)
        if text:
            self._animate_typing(text, kind)
        else:
            self.write("", kind)
            self.after(150, self._type_next)

    def _animate_typing(self, full_text, kind, idx=0):
        if idx > len(full_text):
            self.after(150, self._type_next)
            return
        partial = full_text[:idx]
        self.terminal.configure(state="normal")
        try: self.terminal.delete("end-2l", "end-1l")
        except Exception: pass
        self.terminal.insert("end", partial + "\n", f"tag_{kind}")
        self._apply_tag(f"tag_{kind}", kind)
        if self.sticky_scroll: self.terminal.see("end")
        self.terminal.configure(state="disabled")
        self.after(15, lambda: self._animate_typing(full_text, kind, idx + 1))

    def _apply_tag(self, tag, kind):
        colors = {"cmd": Palette.NEON_BLUE, "ok": Palette.SUCCESS, "err": Palette.ERROR,
                  "warn": Palette.WARNING, "info": Palette.TEXT_DIM2,
                  "header": Palette.ACCENT_GLOW, "id": "#fbbf24", "date": "#d8b4fe"}
        if kind in colors:
            self.terminal.tag_config(tag, foreground=colors[kind])

    def write(self, text, kind="normal"):
        try:
            line_count = int(self.terminal.index("end-1c").split(".")[0])
            if line_count > 10000:
                self.terminal.configure(state="normal")
                self.terminal.delete("1.0", f"{line_count - 10000}.0")
                self.terminal.configure(state="disabled")
        except Exception: pass
        self.terminal.configure(state="normal")
        tag = f"tag_{kind}"
        self.terminal.insert("end", text + "\n", tag)
        self._apply_tag(tag, kind)
        if self.sticky_scroll: self.terminal.see("end")
        self.terminal.configure(state="disabled")
        self._update_live_indicator()

    def _update_live_indicator(self):
        try:
            _, bottom = self.terminal.yview()
            live = bottom >= 0.99
            if live and self.live_btn.cget("text"):
                self.live_btn.configure(text="")
            elif not live and not self.live_btn.cget("text"):
                self.live_btn.configure(text="⬇ Live OFF")
        except Exception: pass

    def _jump_to_end(self):
        self.sticky_scroll = True
        try:
            self.terminal.see("end")
            self.live_btn.configure(text="")
        except Exception: pass

    def _clear_terminal(self):
        self.terminal.configure(state="normal")
        self.terminal.delete("1.0", "end")
        self.terminal.configure(state="disabled")

    def _copy_selection(self, event=None):
        try:
            text = self.terminal.get("sel.first", "sel.last")
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
        except Exception: pass
        return "break"

    def _paste(self, event=None):
        try: self.entry.insert("end", self.clipboard_get())
        except Exception: pass
        return "break"

    def _on_scroll(self, event):
        if event.state & 0x0004:
            delta = 1 if (getattr(event, "delta", 0) > 0 or event.num == 4) else -1
            self.app.config_data["font_size"] = max(8, min(24, self.app.config_data.get("font_size", 13) + delta))
            save_config(self.app.config_data)
            self.app._apply_font_size()
            return "break"
        self.after(50, self._update_live_indicator)

    def _on_terminal_click(self, event=None):
        try:
            index = self.terminal.index(f"@{event.x},{event.y}")
            line = self.terminal.get(f"{index} linestart", f"{index} lineend")
            m = re.search(r"\b\d{5,}\b", line)
            if m:
                self.clipboard_clear()
                self.clipboard_append(m.group(0))
                self.app.toast(f"copied: {m.group(0)}")
        except Exception: pass

    def on_enter(self):
        cmd = self.entry.get().strip()
        self.entry.delete(0, "end")
        if not cmd: return
        if not self.history or self.history[-1] != cmd:
            self.history.append(cmd)
            save_history(self.history)
        self.history_index = len(self.history)
        self.run(cmd)

    def history_up(self, event=None):
        if not self.history: return "break"
        self.history_index = max(0, self.history_index - 1)
        self.entry.delete(0, "end")
        self.entry.insert(0, self.history[self.history_index])
        return "break"

    def history_down(self, event=None):
        if not self.history: return "break"
        self.history_index = min(len(self.history), self.history_index + 1)
        self.entry.delete(0, "end")
        if self.history_index < len(self.history):
            self.entry.insert(0, self.history[self.history_index])
        return "break"

    def autocomplete(self, event=None):
        current = self.entry.get().strip().lower()
        all_cmds = ["ping", "ban", "unban", "banlist", "checkban", "idlist",
                    "ai", "data", "help", "color", "clear", "calc", "alias",
                    "config", "uptime", "mem", "fortune", "export", "mute",
                    "unmute", "lang", "reset", "tex", "maintenance"]
        matches = [c for c in all_cmds if c.startswith(current) and current]
        if len(matches) == 1:
            self.entry.delete(0, "end")
            self.entry.insert(0, matches[0] + " ")
        elif matches:
            self.write("  ".join(matches), "info")
        return "break"

    def run(self, raw):
        low = raw.strip().lower()
        parts = low.split(maxsplit=1)
        cmd = parts[0] if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in self.aliases:
            cmd = self.aliases[cmd]
            raw = cmd + (" " + arg if arg else "")

        if cmd == "clear":
            self._clear_terminal()
            return

        if cmd == "help":
            self.write(f"❯ {raw}", "cmd")
            for line in [
                "ping              — check connection",
                "ban ID [time] [reason] — ban user",
                "unban ID          — unban user",
                "banlist           — list of bans",
                "checkban ID       — check ban status",
                "idlist            — list of users",
                "ai question       — ask AI",
                "data              — current date/time",
                "tex on 1h         — maintenance for 1 hour",
                "tex off           — disable maintenance",
                "tex               — maintenance status",
                "calc expression   — calculator",
                "alias name=cmd    — create alias",
                "config            — show settings",
                "color N           — change theme (1-8)",
                "uptime / mem      — resources info",
                "export <path>     — save log to file",
                "reset             — reset settings",
                "clear             — clear screen",
            ]:
                self.write("  " + line, "info")
            self.write("")
            return

        if cmd == "color":
            if arg == "list":
                self.write(f"❯ {raw}", "cmd")
                for n, (_, _, _, name) in COLOR_THEMES.items():
                    marker = " ←" if n == self.app.current_color else ""
                    self.write(f"  {n} — {name}{marker}", "info")
                self.write("")
                return
            try:
                n = int(arg)
                self.write(f"❯ {raw}", "cmd")
                if self.app._apply_color(n):
                    self.write(f"✅ theme changed: {COLOR_THEMES[n][3]}", "ok")
                else:
                    self.write("❌ choose 1-8", "err")
                self.write("")
            except Exception:
                self.write("❌ usage: color N (1-8) or color list", "err")
            return

        if cmd == "calc":
            self.write(f"❯ {raw}", "cmd")
            try:
                allowed = set("0123456789+-*/(). %")
                if not all(c in allowed for c in arg):
                    raise ValueError("invalid characters")
                result = eval(arg, {"__builtins__": {}}, {})
                self.write(f"  = {result}", "ok")
            except Exception as e:
                self.write(f"❌ error: {e}", "err")
            self.write("")
            return

        if cmd == "alias":
            if "=" in arg:
                name, cmd_val = arg.split("=", 1)
                name, cmd_val = name.strip(), cmd_val.strip()
                self.aliases[name] = cmd_val
                self.app.config_data.setdefault("aliases", {})[name] = cmd_val
                save_config(self.app.config_data)
                self.write(f"✅ alias: {name} → {cmd_val}", "ok")
            else:
                self.write(f"❯ {raw}", "cmd")
                for k, v in self.aliases.items():
                    self.write(f"  {k} → {v}", "info")
                self.write("")
            return

        if cmd == "config":
            if not arg:
                self.write(f"❯ {raw}", "cmd")
                for k, v in self.app.config_data.items():
                    self.write(f"  {k}: {v}", "info")
                self.write("")
                return
            if arg.startswith("font"):
                try:
                    n = int(arg.split()[1])
                    self.app.config_data["font_size"] = max(8, min(24, n))
                    save_config(self.app.config_data)
                    self.app._apply_font_size()
                    self.write(f"✅ font size: {n}", "ok")
                except Exception:
                    self.write("❌ usage: config font N", "err")
                return
            return

        if cmd == "mute":
            self.app.config_data["sound"] = False
            save_config(self.app.config_data)
            self.write("🔇 sound off", "ok")
            return

        if cmd == "unmute":
            self.app.config_data["sound"] = True
            save_config(self.app.config_data)
            self.write("🔊 sound on", "ok")
            play_sound("ok", True)
            return

        if cmd == "lang":
            if arg in ("ru", "en"):
                self.app.config_data["lang"] = arg
                save_config(self.app.config_data)
                self.write(f"✅ lang: {arg.upper()}", "ok")
            else:
                self.write("❌ usage: lang ru or lang en", "err")
            return

        if cmd == "fortune":
            self.write(random.choice(FORTUNES), "info")
            return

        if cmd == "uptime":
            up = int(time.time() - self.app.start_time)
            h, rem = divmod(up, 3600)
            m, s = divmod(rem, 60)
            self.write(f"⏱ uptime: {h}h {m}m {s}s", "info")
            return

        if cmd == "mem":
            try:
                import psutil
                p = psutil.Process(os.getpid())
                mb = p.memory_info().rss / 1024 / 1024
                self.write(f"💾 memory: {mb:.1f} MB", "info")
            except Exception:
                self.write("📦 psutil not installed", "warn")
            return

        if cmd == "export":
            path = arg or "export.txt"
            try:
                text = self.terminal.get("1.0", "end")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.write(f"✅ saved: {path}", "ok")
            except Exception as e:
                self.write(f"❌ error: {e}", "err")
            return

        if cmd == "reset":
            self.app.config_data = {
                "color": 5, "font_size": 13, "sound": True, "lang": "ru",
                "window_geometry": "1440x920", "aliases": {},
            }
            save_config(self.app.config_data)
            self.app._apply_color(5)
            self.app._apply_font_size()
            self.write("✅ settings reset", "ok")
            return

        self.write(f"❯ {raw}", "cmd")
        self._progress_show()

        def task():
            data = self.app.api.command(raw)
            self.after(0, self._progress_hide)
            if "error" in data:
                self.after(0, lambda: self.write(f"❌ {data['error']}", "err"))
                self.after(0, lambda: play_sound("err", self.app.config_data.get("sound", True)))
                self.after(0, lambda: self.app.toast(data["error"], "err"))
            else:
                result = data.get("result", "")
                for line in result.split("\n"):
                    self.after(0, lambda l=line: self._write_highlighted(l))
                self.after(0, lambda: play_sound("ok", self.app.config_data.get("sound", True)))
                self.after(0, lambda: self.app.mini_log(f"✓ {cmd}", "ok"))
                self.after(0, lambda: self.app.toast("done"))
            self.after(0, lambda: self.write(""))
        threading.Thread(target=task, daemon=True).start()

    def _write_highlighted(self, line):
        self.terminal.configure(state="normal")
        parts = re.split(r"(\b\d{5,}\b|\d{2}\.\d{2}\.\d{4})", line)
        for part in parts:
            if not part: continue
            if re.fullmatch(r"\d{5,}", part):
                tag = f"id_{time.time_ns()}"
                self.terminal.insert("end", part, tag)
                self.terminal.tag_config(tag, foreground="#fbbf24")
            elif re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", part):
                tag = f"date_{time.time_ns()}"
                self.terminal.insert("end", part, tag)
                self.terminal.tag_config(tag, foreground="#d8b4fe")
            else:
                self.terminal.insert("end", part, "normal")
        self.terminal.insert("end", "\n")
        if self.sticky_scroll: self.terminal.see("end")
        self.terminal.configure(state="disabled")
        self._update_live_indicator()

    def _progress_show(self):
        try:
            self.progress.grid()
            self.progress.start()
        except Exception: pass

    def _progress_hide(self):
        try:
            self.progress.stop()
            self.progress.grid_remove()
        except Exception: pass

# ============================================================
# ГЛАВНОЕ ОКНО (полностью переработано)
# ============================================================
class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=Palette.BG_VOID)
        self.title(f"⚡ RedSave Control {APP_VERSION}")
        self.config_data = load_config()
        self.geometry(self.config_data.get("window_geometry", "1440x920"))
        self.minsize(1100, 700)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Aurora фон
        self.bg_canvas = tk.Canvas(self, bg=Palette.BG_VOID, highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bg_animator = AuroraBackground(self.bg_canvas)

        self.api = BotAPI(API_URL, APP_TOKEN)
        self.paused = False
        self._status_running = True
        self.current_color = self.config_data.get("color", 5)
        self.current_tab = "dashboard"
        self.start_time = time.time()
        self.maintenance_active = False
        self.maintenance_remaining = 0

        self._build_ui()
        self._apply_color(self.current_color)
        self._apply_font_size()
        self._start_status_loop()
        self._start_network_refresh()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)
        
        # TOP NAVIGATION
        self.top_nav = TopNavBar(self.main_container, self)
        self.top_nav.grid(row=0, column=0, sticky="ew")
        
        # CONTENT AREA
        self.content_area = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_area.grid(row=1, column=0, sticky="nsew", padx=28, pady=(20, 28))
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

        self.tabs = {
            "dashboard": self._build_dashboard_tab(),
            "terminal": self._build_terminal_tab(),
            "bans": self._build_bans_tab(),
            "network": self._build_network_tab(),
            "settings": self._build_settings_tab(),
        }
        self._show_tab("dashboard")

    def _build_dashboard_tab(self):
        """BENTO GRID LAYOUT — разные размеры карточек"""
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=2, uniform="bento")
        tab.grid_columnconfigure(1, weight=1, uniform="bento")
        tab.grid_columnconfigure(2, weight=1, uniform="bento")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_rowconfigure(2, weight=2)

        # === СТРОКА 1: Главная карточка статуса + 2 маленькие ===
        
        # Главная карточка статуса (большая, занимает 2 строки)
        main_status = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=24,
                                    border_width=1, border_color=Palette.BORDER)
        main_status.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 14), pady=(0, 14))
        
        main_inner = ctk.CTkFrame(main_status, fg_color="transparent")
        main_inner.pack(fill="both", expand=True, padx=32, pady=28)
        
        # Заголовок
        header = ctk.CTkFrame(main_inner, fg_color="transparent")
        header.pack(fill="x")
        
        ctk.CTkLabel(header, text="SYSTEM STATUS",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=Palette.TEXT_DIM2).pack(anchor="w")
        ctk.CTkLabel(header, text="Real-time monitoring",
                     font=ctk.CTkFont(size=10),
                     text_color=Palette.TEXT_MUTED).pack(anchor="w")
        
        # Статус ринг
        self.status_ring = StatusRing(main_inner, size=140, bg=Palette.BG_CARD)
        self.status_ring.pack(pady=(24, 16))
        
        self.status_label = ctk.CTkLabel(main_inner, text="Checking...",
                                          font=ctk.CTkFont(size=22, weight="bold"),
                                          text_color=Palette.TEXT)
        self.status_label.pack()
        
        self.ping_label = ctk.CTkLabel(main_inner, text="— ms",
                                        font=ctk.CTkFont(size=13),
                                        text_color=Palette.TEXT_DIM2)
        self.ping_label.pack(pady=(6, 0))
        
        # Бейдж тех. работ
        self.maintenance_badge = MaintenanceBadge(main_inner, width=340, height=48,
                                                    bg=Palette.BG_CARD)
        self.maintenance_badge.pack(pady=(20, 0))
        
        # === Карточка пользователей ===
        self.card_users = BentoCard(tab, title="USERS", icon="👥",
                                     accent=Palette.NEON_BLUE,
                                     subtitle="Active accounts",
                                     large_value="—")
        self.card_users.grid(row=0, column=1, sticky="nsew", padx=7, pady=(0, 7))
        
        # === Карточка банов ===
        self.card_bans = BentoCard(tab, title="BANS", icon="⊘",
                                    accent=Palette.ERROR,
                                    subtitle="Total bans",
                                    large_value="—")
        self.card_bans.grid(row=0, column=2, sticky="nsew", padx=(7, 0), pady=(0, 7))
        
        # === Карточка RTT (широкая) ===
        rtt_card = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=24,
                                 border_width=1, border_color=Palette.BORDER)
        rtt_card.grid(row=1, column=1, columnspan=2, sticky="nsew", padx=(7, 0), pady=(7, 14))
        
        rtt_inner = ctk.CTkFrame(rtt_card, fg_color="transparent")
        rtt_inner.pack(fill="both", expand=True, padx=28, pady=22)
        
        rtt_header = ctk.CTkFrame(rtt_inner, fg_color="transparent")
        rtt_header.pack(fill="x")
        
        ctk.CTkLabel(rtt_header, text="API LATENCY",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=Palette.TEXT_DIM2).pack(side="left")
        ctk.CTkLabel(rtt_header, text="Last 40 requests",
                     font=ctk.CTkFont(size=10),
                     text_color=Palette.TEXT_MUTED).pack(side="right")
        
        self.card_ping = ctk.CTkLabel(rtt_inner, text="— ms",
                                       font=ctk.CTkFont(size=32, weight="bold"),
                                       text_color=Palette.SUCCESS)
        self.card_ping.pack(anchor="w", pady=(8, 0))
        
        self.rtt_graph = RTTGraph(rtt_inner, width=400, height=80, bg=Palette.BG_CARD)
        self.rtt_graph.pack(fill="x", pady=(12, 0))

        # === СТРОКА 2: Быстрые действия (широкая карточка) ===
        actions = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=24,
                                border_width=1, border_color=Palette.BORDER)
        actions.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(0, 0))
        
        actions_inner = ctk.CTkFrame(actions, fg_color="transparent")
        actions_inner.pack(fill="both", expand=True, padx=32, pady=26)
        
        actions_header = ctk.CTkFrame(actions_inner, fg_color="transparent")
        actions_header.pack(fill="x")
        
        ctk.CTkLabel(actions_header, text="⚡ QUICK ACTIONS",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=Palette.TEXT_DIM2).pack(side="left")
        
        row = ctk.CTkFrame(actions_inner, fg_color="transparent")
        row.pack(fill="x", pady=(16, 0))
        
        for text, cmd, color, icon in [
            ("Ping", "ping", Palette.NEON_BLUE, "🏓"),
            ("Banlist", "banlist", Palette.WARNING, "📋"),
            ("ID List", "idlist", Palette.NEON_PURPLE, "🔢"),
            ("Date", "data", Palette.NEON_CYAN, "🕒"),
            ("Maintenance 1h", "tex on 1h", Palette.ERROR, "🔧"),
            ("Help", "help", Palette.TEXT_DIM, "❓"),
        ]:
            btn = GradientButton(row, text,
                                  command=lambda c=cmd: self._send_to_terminal(c),
                                  color=color, width=150, height=48, icon=icon)
            btn.pack(side="left", padx=(0, 12))

        # === СТРОКА 3: Лог событий ===
        log_card = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=24,
                                 border_width=1, border_color=Palette.BORDER)
        log_card.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(14, 0))
        
        log_inner = ctk.CTkFrame(log_card, fg_color="transparent")
        log_inner.pack(fill="both", expand=True, padx=32, pady=26)
        
        log_header = ctk.CTkFrame(log_inner, fg_color="transparent")
        log_header.pack(fill="x")
        
        ctk.CTkLabel(log_header, text="📝 ACTIVITY LOG",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=Palette.TEXT_DIM2).pack(side="left")
        
        self.mini_log = ctk.CTkTextbox(log_inner,
                                        font=ctk.CTkFont(family="Consolas", size=12),
                                        fg_color=Palette.BG_DEEP, border_width=0, corner_radius=16,
                                        text_color=Palette.TEXT_DIM, wrap="word")
        self.mini_log.pack(fill="both", expand=True, pady=(12, 0))
        self.mini_log.configure(state="disabled")
        
        return tab

    def _build_terminal_tab(self):
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self.terminal_widget = Terminal(tab, self)
        self.terminal_widget.grid(row=0, column=0, sticky="nsew")
        return tab

    def _build_bans_tab(self):
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        # Header
        header = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=24,
                               border_width=1, border_color=Palette.BORDER)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        
        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="x", padx=28, pady=22)
        
        ctk.CTkLabel(header_inner, text="⊘ BANS",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=Palette.TEXT).pack(side="left")
        
        ctk.CTkButton(header_inner, text="🔄  Refresh", width=140, height=40,
                       fg_color=Palette.ACCENT, hover_color=Palette.ACCENT_HOVER,
                       text_color="#ffffff", corner_radius=12,
                       font=ctk.CTkFont(size=12, weight="bold"),
                       command=self._load_bans).pack(side="right")
        
        # Список банов
        self.bans_container = ctk.CTkScrollableFrame(tab, fg_color=Palette.BG_CARD,
                                                      corner_radius=24,
                                                      border_width=1, border_color=Palette.BORDER)
        self.bans_container.grid(row=1, column=0, sticky="nsew")
        self.bans_container.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.bans_container, text="Click «Refresh» to load bans",
                      font=ctk.CTkFont(size=13), text_color=Palette.TEXT_DIM2).pack(pady=120)
        return tab

    def _build_network_tab(self):
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        # Header
        header = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=24,
                               border_width=1, border_color=Palette.BORDER)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        
        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="x", padx=28, pady=22)
        
        ctk.CTkLabel(header_inner, text="◉ NETWORK MONITOR",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=Palette.TEXT).pack(side="left")
        
        btns = ctk.CTkFrame(header_inner, fg_color="transparent")
        btns.pack(side="right")
        
        ctk.CTkButton(btns, text="🔄  Refresh", width=130, height=40,
                       fg_color=Palette.ACCENT, hover_color=Palette.ACCENT_HOVER,
                       text_color="#ffffff", corner_radius=12,
                       font=ctk.CTkFont(size=12, weight="bold"),
                       command=self._render_network).pack(side="left", padx=(0, 8))
        
        ctk.CTkButton(btns, text="🗑  Clear", width=120, height=40,
                       fg_color=Palette.BG_CARD_HOVER, hover_color=Palette.BG_CARD,
                       text_color=Palette.ERROR, corner_radius=12,
                       font=ctk.CTkFont(size=12, weight="bold"),
                       border_width=1, border_color=Palette.BORDER,
                       command=self._clear_network).pack(side="left")
        
        self.net_stats = ctk.CTkLabel(header_inner, text="", font=ctk.CTkFont(size=12),
                                       text_color=Palette.TEXT_DIM)
        
        # Список запросов
        self.net_container = ctk.CTkScrollableFrame(tab, fg_color=Palette.BG_CARD,
                                                     corner_radius=24,
                                                     border_width=1, border_color=Palette.BORDER)
        self.net_container.grid(row=1, column=0, sticky="nsew")
        self.net_container.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.net_container, text="No requests yet",
                      font=ctk.CTkFont(size=13), text_color=Palette.TEXT_DIM2).pack(pady=120)
        return tab

    def _build_settings_tab(self):
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        # Connection info
        info = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=24,
                             border_width=1, border_color=Palette.BORDER)
        info.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        
        info_inner = ctk.CTkFrame(info, fg_color="transparent")
        info_inner.pack(fill="x", padx=32, pady=28)
        
        ctk.CTkLabel(info_inner, text="🔌 CONNECTION",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=Palette.TEXT_DIM2).pack(anchor="w")
        
        for lbl, val in [("API URL", API_URL), ("Token", APP_TOKEN), ("Version", APP_VERSION)]:
            r = ctk.CTkFrame(info_inner, fg_color="transparent")
            r.pack(fill="x", pady=(12, 0))
            ctk.CTkLabel(r, text=lbl, font=ctk.CTkFont(size=10, weight="bold"),
                          text_color=Palette.TEXT_MUTED).pack(anchor="w")
            ctk.CTkLabel(r, text=val, anchor="w",
                          font=ctk.CTkFont(family="Consolas", size=13),
                          text_color=Palette.TEXT).pack(anchor="w")

        # Color themes
        colors = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=24,
                                border_width=1, border_color=Palette.BORDER)
        colors.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        
        colors_inner = ctk.CTkFrame(colors, fg_color="transparent")
        colors_inner.pack(fill="x", padx=32, pady=28)
        
        ctk.CTkLabel(colors_inner, text="🎨 THEME",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=Palette.TEXT_DIM2).pack(anchor="w")
        
        row = ctk.CTkFrame(colors_inner, fg_color="transparent")
        row.pack(fill="x", pady=(16, 0))
        
        for num in range(1, 9):
            bg, fg, _, name = COLOR_THEMES[num]
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="left", padx=6)
            
            ctk.CTkButton(btn_frame, text="", width=56, height=56,
                           fg_color=fg, hover_color=bg,
                           corner_radius=16, border_width=3, border_color=Palette.BORDER,
                           command=lambda n=num: self._apply_color(n)).pack()
            
            ctk.CTkLabel(btn_frame, text=name, font=ctk.CTkFont(size=9),
                          text_color=Palette.TEXT_DIM2).pack(pady=(4, 0))

        # Maintenance controls
        maint = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=24,
                              border_width=1, border_color=Palette.BORDER)
        maint.grid(row=2, column=0, sticky="ew")
        
        maint_inner = ctk.CTkFrame(maint, fg_color="transparent")
        maint_inner.pack(fill="x", padx=32, pady=28)
        
        ctk.CTkLabel(maint_inner, text="🔧 MAINTENANCE",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=Palette.TEXT_DIM2).pack(anchor="w")
        
        btn_row = ctk.CTkFrame(maint_inner, fg_color="transparent")
        btn_row.pack(fill="x", pady=(16, 0))

        for text, cmd, color, hover in [
            ("30 min", "tex on 30m", Palette.WARNING, "#d97706"),
            ("1 hour", "tex on 1h",  Palette.WARNING, "#d97706"),
            ("3 hours", "tex on 3h", Palette.WARNING, "#d97706"),
            ("Disable", "tex off",   Palette.SUCCESS, "#16a34a"),
        ]:
            ctk.CTkButton(btn_row, text=text, width=130, height=46,
                           fg_color=color, hover_color=hover,
                           text_color="#000000" if color == Palette.WARNING else "#ffffff",
                           corner_radius=14,
                           font=ctk.CTkFont(size=12, weight="bold"),
                           command=lambda c=cmd: self._send_to_terminal(c)
                           ).pack(side="left", padx=(0, 12))
        return tab

    def _switch_tab(self, key):
        if key == self.current_tab: return
        self.current_tab = key
        for k, btn in self.top_nav.nav_buttons.items():
            btn._set_active(k == key)
        for k, tab in self.tabs.items():
            if k == key:
                tab.grid(row=0, column=0, sticky="nsew")
            else:
                tab.grid_forget()
        if key == "bans": self._load_bans()
        if key == "network": self._render_network()

    def _show_tab(self, key):
        self.current_tab = key
        for k, tab in self.tabs.items():
            if k == key:
                tab.grid(row=0, column=0, sticky="nsew")
            else:
                tab.grid_forget()

    def _apply_color(self, num):
        if num not in COLOR_THEMES: return False
        self.current_color = num
        self.config_data["color"] = num
        save_config(self.config_data)
        bg, fg, dim, name = COLOR_THEMES[num]
        try:
            if hasattr(self, "terminal_widget"):
                self.terminal_widget.terminal.configure(fg_color=bg, text_color=fg)
                self.terminal_widget.term_title.configure(text=f"⚡ redsave — {name}")
        except Exception: pass
        return True

    def _apply_font_size(self):
        size = self.config_data.get("font_size", 13)
        try:
            if hasattr(self, "terminal_widget"):
                self.terminal_widget.terminal.configure(
                    font=ctk.CTkFont(family="Consolas", size=size))
                self.terminal_widget.entry.configure(
                    font=ctk.CTkFont(family="Consolas", size=size))
        except Exception: pass

    def _send_to_terminal(self, cmd):
        if hasattr(self, "terminal_widget"):
            self._switch_tab("terminal")
            for k, btn in self.top_nav.nav_buttons.items():
                btn._set_active(k == "terminal")
            self.terminal_widget.run(cmd)

    def _set_status(self, online, ping=None, paused=False):
        try:
            if hasattr(self, "terminal_widget"):
                tc = self.terminal_widget.traffic
                if paused:
                    tc.itemconfig(self.terminal_widget._tc1, fill="#2a2a35")
                    tc.itemconfig(self.terminal_widget._tc2, fill=Palette.WARNING)
                    tc.itemconfig(self.terminal_widget._tc3, fill="#2a2a35")
                elif online:
                    tc.itemconfig(self.terminal_widget._tc1, fill=Palette.SUCCESS)
                    tc.itemconfig(self.terminal_widget._tc2, fill="#2a2a35")
                    tc.itemconfig(self.terminal_widget._tc3, fill="#2a2a35")
                else:
                    tc.itemconfig(self.terminal_widget._tc1, fill="#2a2a35")
                    tc.itemconfig(self.terminal_widget._tc2, fill="#2a2a35")
                    tc.itemconfig(self.terminal_widget._tc3, fill=Palette.ERROR)
        except Exception: pass

        # Обновляем top nav статус
        if paused:
            self.top_nav.set_status("paused", ping)
            self.status_ring.set_state("paused")
            self.status_label.configure(text="Paused", text_color=Palette.WARNING)
        elif online:
            self.top_nav.set_status("online", ping)
            self.status_ring.set_state("online")
            self.status_label.configure(text="Online", text_color=Palette.SUCCESS)
        else:
            self.top_nav.set_status("offline", ping)
            self.status_ring.set_state("offline")
            self.status_label.configure(text="Offline", text_color=Palette.ERROR)

        self.ping_label.configure(text=f"{ping} ms" if ping else "— ms")
        if ping:
            if hasattr(self, "card_ping"):
                self.card_ping.configure(text=f"{ping} ms")
            if hasattr(self, "rtt_graph"):
                self.rtt_graph.push(ping)

    def _start_status_loop(self):
        def loop():
            while self._status_running:
                try:
                    data = self.api.status()
                    if "error" in data:
                        self.after(0, lambda: self._set_status(False))
                    else:
                        self.paused = data.get("paused", False)
                        maint = data.get("maintenance", False)
                        rem = data.get("maintenance_remaining", 0)
                        self.after(0, lambda m=maint, r=rem: self._update_maintenance(m, r))
                        self.after(0, self._update_pause_button)
                        u = data.get("users_count", 0)
                        b = data.get("bans_count", 0)
                        self.after(0, lambda uu=u: self.card_users.set_value(str(uu)))
                        self.after(0, lambda bb=b: self.card_bans.set_value(str(bb)))
                        p = self.api.ping()
                        if "error" not in p:
                            pv = p.get("api_ping")
                            pav = self.paused
                            self.after(0, lambda vv=pv, pp=pav: self._set_status(True, vv, pp))
                except Exception: pass
                time.sleep(10)
        threading.Thread(target=loop, daemon=True).start()

    def _update_maintenance(self, active, remaining):
        self.maintenance_active = active
        self.maintenance_remaining = remaining
        if hasattr(self, "maintenance_badge"):
            self.maintenance_badge.set_state(active, remaining)

    def _start_network_refresh(self):
        def loop():
            while self._status_running:
                try:
                    if self.current_tab == "network":
                        self.after(0, self._render_network)
                except Exception: pass
                time.sleep(3)
        threading.Thread(target=loop, daemon=True).start()

    def _update_pause_button(self):
        if hasattr(self, "top_nav"):
            self.top_nav.set_pause_state(self.paused)

    def _toggle_pause(self):
        def task():
            if self.paused:
                data = self.api.resume()
                if "error" not in data:
                    self.paused = False
                    self.after(0, lambda: self.toast("bot resumed"))
            else:
                data = self.api.pause()
                if "error" not in data:
                    self.paused = True
                    self.after(0, lambda: self.toast("bot paused", "warn"))
            self.after(0, self._update_pause_button)
        threading.Thread(target=task, daemon=True).start()

    def _load_bans(self):
        def task():
            data = self.api.command("banlist")
            self.after(0, lambda: self._render_bans(data))
        threading.Thread(target=task, daemon=True).start()

    def _render_bans(self, data):
        for w in self.bans_container.winfo_children():
            w.destroy()
        if "error" in data:
            ctk.CTkLabel(self.bans_container, text=f"❌ {data['error']}",
                          text_color=Palette.ERROR, font=ctk.CTkFont(size=13)).pack(pady=120)
            return
        result = data.get("result", "")
        if "пуст" in result.lower():
            ctk.CTkLabel(self.bans_container, text="📋 Ban list is empty",
                          text_color=Palette.TEXT_DIM2,
                          font=ctk.CTkFont(size=13)).pack(pady=120)
            return
        for line in [l.strip() for l in result.split("\n") if l.strip() and not l.startswith("📋")]:
            row = ctk.CTkFrame(self.bans_container, fg_color=Palette.BG_PANEL,
                                corner_radius=16, border_width=1, border_color=Palette.BORDER)
            row.pack(fill="x", padx=12, pady=6)
            ctk.CTkLabel(row, text=line, anchor="w",
                          font=ctk.CTkFont(family="Consolas", size=12),
                          text_color=Palette.TEXT).pack(fill="x", padx=22, pady=16)

    def _render_network(self):
        for w in self.net_container.winfo_children():
            w.destroy()
        entries = NET_MONITOR.get_all()
        if not entries:
            ctk.CTkLabel(self.net_container, text="No requests yet",
                          text_color=Palette.TEXT_DIM2,
                          font=ctk.CTkFont(size=13)).pack(pady=120)
            self.net_stats.configure(text="")
            return
        total = len(entries)
        errs = sum(1 for e in entries if e.get("error") or (e.get("status") or 0) >= 400)
        avg = sum(e.get("duration_ms", 0) for e in entries) / max(1, total)
        self.net_stats.configure(text=f"Total: {total}  |  Errors: {errs}  |  Avg: {int(avg)}ms")
        for e in reversed(entries[-100:]):
            row = ctk.CTkFrame(self.net_container, fg_color=Palette.BG_PANEL,
                                corner_radius=14, border_width=1, border_color=Palette.BORDER)
            row.pack(fill="x", padx=10, pady=5)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=22, pady=14)
            ts = datetime.fromtimestamp(e["ts"]).strftime("%H:%M:%S")
            method = e["method"]
            status = e.get("status", 0)
            duration = e.get("duration_ms", 0)
            url = e["url"]
            error = e.get("error")
            if error or status >= 400:
                icon, color = "❌", Palette.ERROR
            elif 200 <= status < 300:
                icon, color = "✅", Palette.SUCCESS
            else:
                icon, color = "⚠️", Palette.WARNING
            top = ctk.CTkFrame(inner, fg_color="transparent")
            top.pack(fill="x")
            ctk.CTkLabel(top, text=f"{icon}  {ts}  {method}",
                          font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                          text_color=color).pack(side="left")
            ctk.CTkLabel(top, text=f"{status}  •  {duration}ms",
                          font=ctk.CTkFont(family="Consolas", size=11),
                          text_color=Palette.TEXT_DIM2).pack(side="right")
            ctk.CTkLabel(inner, text=url, anchor="w",
                          font=ctk.CTkFont(family="Consolas", size=11),
                          text_color=Palette.TEXT_DIM).pack(fill="x", pady=(8, 0))
            if error:
                ctk.CTkLabel(inner, text=f"→ {error}", anchor="w",
                              font=ctk.CTkFont(family="Consolas", size=10),
                              text_color=Palette.ERROR).pack(fill="x")

    def _clear_network(self):
        NET_MONITOR.clear()
        self._render_network()

    def mini_log(self, text, kind="normal"):
        if not hasattr(self, "mini_log") or not self.mini_log.winfo_exists(): return
        self.mini_log.configure(state="normal")
        ts = time.strftime("%H:%M:%S")
        tag = f"m_{kind}_{time.time_ns()}"
        self.mini_log.insert("end", f"[{ts}] {text}\n", tag)
        colors = {"ok": Palette.SUCCESS, "err": Palette.ERROR, "info": Palette.TEXT_DIM2}
        if kind in colors:
            self.mini_log.tag_config(tag, foreground=colors[kind])
        self.mini_log.see("end")
        self.mini_log.configure(state="disabled")

    def toast(self, text, kind="ok"):
        if hasattr(self, "terminal_widget"):
            self.terminal_widget.write(f"• {text}", kind)

    def on_close(self):
        try:
            self.config_data["window_geometry"] = self.geometry()
            save_config(self.config_data)
        except Exception: pass
        self._status_running = False
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
