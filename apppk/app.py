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
# КОНФИГ (Логика не изменена)
# ============================================================
API_URL = "https://telegramprobot.relaxdev.ru/webhook"
APP_TOKEN = "871410danil" # ⚠️ Внимание: токен виден в коде. Для продакшена лучше использовать .env
APP_VERSION = "5.0.0-ultra"

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".redsave_config.json")
HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".redsave_history.json")

COLOR_THEMES = {
    1: ("#0a1929", "#4da6ff", "#2a5d8f", "Синий"),
    2: ("#0a1f0a", "#33ff33", "#1a5c1a", "Зелёный"),
    3: ("#1f0a0a", "#ff4d4d", "#8f2a2a", "Красный"),
    4: ("#1f1400", "#ffa64d", "#8f5a2a", "Оранжевый"),
    5: ("#09090b", "#8b5cf6", "#3f3f46", "Obsidian"), # Обновлен на современный темный
    6: ("#1a0a1f", "#c44dff", "#7a2a8f", "Фиолетовый"),
    7: ("#001a1a", "#4dffff", "#2a8f8f", "Бирюзовый"),
    8: ("#1a1a00", "#ffff4d", "#8f8f2a", "Жёлтый"),
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
# УТИЛИТЫ (Логика не изменена)
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
# ПАЛИТРА (Обновлена на современную "Zinc/Violet" тему)
# ============================================================
class Palette:
    BG_DARK = "#09090b"       # Zinc 950
    BG_PANEL = "#18181b"      # Zinc 900
    BG_CARD = "#27272a"       # Zinc 800
    BG_CARD_HOVER = "#3f3f46" # Zinc 700
    BG_INPUT = "#18181b"
    BORDER = "#3f3f46"
    BORDER_LIGHT = "#52525b"
    TEXT = "#fafafa"          # Zinc 50
    TEXT_DIM = "#a1a1aa"      # Zinc 400
    TEXT_DIM2 = "#71717a"     # Zinc 500
    ACCENT = "#8b5cf6"        # Violet 500
    ACCENT_HOVER = "#7c3aed"  # Violet 600
    ACCENT_GLOW = "#a78bfa"   # Violet 400
    SUCCESS = "#10b981"       # Emerald 500
    SUCCESS_GLOW = "#34d399"  # Emerald 400
    ERROR = "#ef4444"         # Red 500
    ERROR_GLOW = "#f87171"    # Red 400
    WARNING = "#f59e0b"       # Amber 500
    WARNING_GLOW = "#fbbf24"  # Amber 400
    INFO = "#3b82f6"          # Blue 500
    CYAN = "#06b6d4"          # Cyan 500
    PINK = "#ec4899"          # Pink 500

# ============================================================
# NETWORK MONITOR (Логика не изменена)
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
# КОНФИГ / ИСТОРИЯ (Логика не изменена)
# ============================================================
def load_config():
    defaults = {"color": 5, "font_size": 13, "sound": True, "lang": "ru",
                "window_geometry": "1280x820", "aliases": {}} # Чуть увеличил дефолтный размер окна
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
# API КЛИЕНТ (Логика не изменена)
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
# ВИЗУАЛЬНЫЕ КОМПОНЕНТЫ (Улучшена эстетика, логика та же)
# ============================================================
class AnimatedDot(tk.Canvas):
    def __init__(self, parent, color=Palette.SUCCESS, size=14, bg=Palette.BG_CARD):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        self.size = size
        self.phase = 0
        self.dot = self.create_oval(2, 2, size-2, size-2, fill=color, outline="")
        self._animate()

    def set_color(self, color):
        try: self.itemconfig(self.dot, fill=color)
        except Exception: pass

    def _animate(self):
        if not self.winfo_exists(): return
        try:
            self.phase = (self.phase + 1) % 40
            scale = 1 + 0.15 * math.sin(self.phase / 40 * 2 * math.pi)
            cx, cy = self.size / 2, self.size / 2
            r = (self.size - 4) / 2 * scale
            self.coords(self.dot, cx - r, cy - r, cx + r, cy + r)
        except Exception: pass
        try: self.after(50, self._animate)
        except Exception: pass

class StatusRing(tk.Canvas):
    def __init__(self, parent, size=80, bg=Palette.BG_CARD):
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
            r = self.size / 2 - 6
            colors = {"online": Palette.SUCCESS, "paused": Palette.WARNING,
                      "offline": Palette.ERROR, "unknown": Palette.TEXT_DIM2}
            color = colors.get(self.state, Palette.TEXT_DIM2)
            self.pulse = (self.pulse + 1) % 60
            ring_r = r + 2 * math.sin(self.pulse / 60 * 2 * math.pi)
            
            # Внешнее свечение
            self.create_oval(cx - ring_r - 2, cy - ring_r - 2, cx + ring_r + 2, cy + ring_r + 2,
                             outline=color, width=1, stipple="gray50")
            # Основное кольцо
            self.create_oval(cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r,
                             outline=color, width=3, fill="")
            # Центральная точка
            r2 = 6
            self.create_oval(cx - r2, cy - r2, cx + r2, cy + r2, fill=color, outline="")
        except Exception: pass
        try: self.after(50, self._animate)
        except Exception: pass

class MaintenanceBadge(tk.Canvas):
    def __init__(self, parent, width=280, height=34, bg=Palette.BG_PANEL):
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
            pad = 3
            pill_h = h - 2 * pad

            if self.active:
                color = Palette.ERROR
                glow = Palette.ERROR_GLOW
                text = "Тех. работы"
                if self.remaining > 0:
                    text = f"Тех. работы · {format_duration(self.remaining)}"
            else:
                color = Palette.SUCCESS
                glow = Palette.SUCCESS_GLOW
                text = "Система в норме"

            text_w = 7 * len(text) + 20
            circle_w = pill_h
            pill_w = min(w, circle_w + text_w + 16)
            r = pill_h / 2

            # Фон таблетки
            self.create_oval(pad, pad, pad + pill_h, h - pad, fill=Palette.BG_CARD, outline="")
            self.create_oval(pill_w - pad - pill_h, pad, pill_w - pad, h - pad, fill=Palette.BG_CARD, outline="")
            self.create_rectangle(pad + r, pad, pill_w - pad - r, h - pad, fill=Palette.BG_CARD, outline="")

            # Обводка
            self.create_arc(pad, pad, pad + pill_h, h - pad, start=90, extent=180, outline=Palette.BORDER, style="arc", width=1)
            self.create_arc(pill_w - pad - pill_h, pad, pill_w - pad, h - pad, start=270, extent=180, outline=Palette.BORDER, style="arc", width=1)
            self.create_line(pad + r, pad, pill_w - pad - r, pad, fill=Palette.BORDER)
            self.create_line(pad + r, h - pad, pill_w - pad - r, h - pad, fill=Palette.BORDER)

            # Свечение если активно
            if self.active:
                gx = pad + r
                self.create_oval(gx - r - 3, cy - r - 3, gx + r + 3, cy + r + 3, fill="", outline=glow, width=2)

            # Иконка
            cx = pad + r
            cr = r - 3
            self.create_oval(cx - cr, cy - cr, cx + cr, cy + cr, fill=color, outline="")

            if self.active:
                k = cr * 0.5
                self.create_line(cx - k, cy - k, cx + k, cy + k, fill="#ffffff", width=2, capstyle="round")
                self.create_line(cx + k, cy - k, cx - k, cy + k, fill="#ffffff", width=2, capstyle="round")
            else:
                k = cr * 0.55
                self.create_line(cx - k, cy, cx - k * 0.15, cy + k * 0.75, fill="#ffffff", width=2, capstyle="round")
                self.create_line(cx - k * 0.15, cy + k * 0.75, cx + k, cy - k * 0.7, fill="#ffffff", width=2, capstyle="round")

            # Текст
            self.create_text(pad + pill_h + 10, cy, text=text, anchor="w", fill=Palette.TEXT, font=("Arial", 10, "bold"))
        except Exception: pass

    def _animate(self):
        if not self.winfo_exists(): return
        try:
            self.phase = (self.phase + 1) % 60
            self._draw()
        except Exception: pass
        try: self.after(50, self._animate)
        except Exception: pass

class StatCard(ctk.CTkFrame):
    def __init__(self, parent, label, value="—", accent=Palette.ACCENT):
        super().__init__(parent, fg_color=Palette.BG_CARD, corner_radius=16,
                         border_width=1, border_color=Palette.BORDER)
        self.accent = accent
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=18)
        
        self.value_label = ctk.CTkLabel(
            inner, text=value, font=ctk.CTkFont(size=28, weight="bold"),
            text_color=accent)
        self.value_label.pack(anchor="w")
        
        ctk.CTkLabel(inner, text=label.upper(),
                     font=ctk.CTkFont(size=10, weight="bold", tracking=20), # tracking добавляет разрядку
                     text_color=Palette.TEXT_DIM2).pack(anchor="w", pady=(4, 0))
        
        self.bind("<Enter>", self._hover_in)
        self.bind("<Leave>", self._hover_out)

    def set_value(self, value): self.value_label.configure(text=value)

    def _hover_in(self, e):
        try: self.configure(border_color=self.accent, border_width=2)
        except Exception: pass

    def _hover_out(self, e):
        try: self.configure(border_color=Palette.BORDER, border_width=1)
        except Exception: pass

class RTTGraph(tk.Canvas):
    def __init__(self, parent, width=180, height=40, bg=Palette.BG_CARD):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0)
        self.width = width
        self.height = height
        self.values = [0] * 30
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
                self.create_line(0, y, w, y, fill=Palette.BORDER, dash=(2, 2))
            
            n = len(self.values)
            step = w / max(1, n - 1)
            points = []
            for i, v in enumerate(self.values):
                x = i * step
                y = h - (v / self.max_v) * h
                points.extend([x, y])
            
            if len(points) >= 4:
                # Линия графика
                self.create_line(*points, fill=Palette.ACCENT_GLOW, width=2.5, smooth=True)
                # Заливка под графиком
                poly = points + [w, h, 0, h]
                self.create_polygon(*poly, fill=Palette.ACCENT, outline="", stipple="gray25")
            
            cur = self.values[-1]
            color = Palette.SUCCESS if cur < 100 else (Palette.WARNING if cur < 500 else Palette.ERROR)
            self.create_text(w - 4, 10, text=f"{cur}ms", anchor="e",
                             fill=color, font=("Consolas", 10, "bold"))
        except Exception: pass

class GradientBackground(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)
        self.phase = 0
        self.particles = []
        self.enabled = True
        self._animate()

    def start_particles(self, count=30): # Уменьшил кол-во частиц для производительности
        try:
            w = self.winfo_width() or 1200
            h = self.winfo_height() or 760
            self.particles = []
            for _ in range(count):
                self.particles.append({
                    "x": random.uniform(0, w), "y": random.uniform(0, h),
                    "vx": random.uniform(-0.2, 0.2), "vy": random.uniform(-0.2, 0.2),
                    "r": random.uniform(1.0, 2.5),
                    "c": random.choice([Palette.ACCENT, Palette.ACCENT_GLOW, Palette.CYAN, Palette.PINK]),
                })
        except Exception: pass

    def _animate(self):
        if not self.winfo_exists(): return
        if not self.enabled:
            self.after(200, self._animate)
            return
        try:
            self.delete("all")
            w = self.winfo_width() or 1200
            h = self.winfo_height() or 760
            self.phase = (self.phase + 0.3) % 360
            
            # Градиентный фон
            steps = 16
            for i in range(steps):
                r1, g1, b1 = 9, 9, 11
                r2, g2, b2 = 24, 24, 28
                wave = 0.5 + 0.5 * math.sin((self.phase + i * 12) * math.pi / 180)
                r = int(r1 + (r2 - r1) * wave)
                g = int(g1 + (g2 - g1) * wave)
                b = int(b1 + (b2 - b1) * wave)
                self.create_rectangle(0, h * i / steps, w, h * (i + 1) / steps,
                                      fill=f"#{r:02x}{g:02x}{b:02x}", outline="")
            
            # Частицы
            if not self.particles: self.start_particles(30)
            for p in self.particles:
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                if p["x"] < 0: p["x"] = w
                if p["x"] > w: p["x"] = 0
                if p["y"] < 0: p["y"] = h
                if p["y"] > h: p["y"] = 0
                self.create_oval(p["x"] - p["r"], p["y"] - p["r"],
                                 p["x"] + p["r"], p["y"] + p["r"],
                                 fill=p["c"], outline="", stipple="gray50")
        except Exception: pass
        self.after(80, self._animate)

class SidebarButton(ctk.CTkFrame):
    def __init__(self, parent, text, icon, command=None, active=False):
        super().__init__(parent, fg_color="transparent", height=48)
        self.pack_propagate(False)
        self.command = command
        self.active = active
        
        # Индикатор активной вкладки
        self.indicator = ctk.CTkFrame(self, width=4, height=24, fg_color=Palette.ACCENT, corner_radius=2)
        self.indicator.pack(side="left", padx=(0, 4))
        if not active: self.indicator.configure(fg_color="transparent")

        self.icon_label = ctk.CTkLabel(
            self, text=icon, font=ctk.CTkFont(size=18),
            text_color=Palette.ACCENT if active else Palette.TEXT_DIM, width=36)
        self.icon_label.pack(side="left")
        
        self.text_label = ctk.CTkLabel(
            self, text=text, font=ctk.CTkFont(size=13, weight="bold" if active else "normal"),
            text_color=Palette.TEXT if active else Palette.TEXT_DIM, anchor="w")
        self.text_label.pack(side="left", padx=(4, 0), fill="x", expand=True)
        
        self._set_active(active)
        for w in (self, self.icon_label, self.text_label):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_click)

    def _set_active(self, active):
        self.active = active
        if active:
            self.configure(fg_color=Palette.BG_CARD)
            self.indicator.configure(fg_color=Palette.ACCENT)
            self.icon_label.configure(text_color=Palette.ACCENT)
            self.text_label.configure(text_color=Palette.TEXT)
        else:
            self.configure(fg_color="transparent")
            self.indicator.configure(fg_color="transparent")
            self.icon_label.configure(text_color=Palette.TEXT_DIM)
            self.text_label.configure(text_color=Palette.TEXT_DIM)

    def _on_enter(self, e):
        if not self.active: self.configure(fg_color=Palette.BG_CARD)

    def _on_leave(self, e):
        if not self.active: self.configure(fg_color="transparent")

    def _on_click(self, e):
        if self.command: self.command()

# ============================================================
# ТЕРМИНАЛ (Улучшен визуал, логика та же)
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
            self, fg_color=Palette.BG_DARK, corner_radius=16,
            border_width=1, border_color=Palette.BORDER)
        self.term_container.pack(fill="both", expand=True)
        self.term_container.grid_columnconfigure(0, weight=1)
        self.term_container.grid_rowconfigure(1, weight=1)

        # Заголовок терминала
        title_bar = ctk.CTkFrame(self.term_container, fg_color=Palette.BG_PANEL,
                                  corner_radius=0, height=42)
        title_bar.grid(row=0, column=0, sticky="ew")
        title_bar.grid_propagate(False)

        self.traffic = tk.Canvas(title_bar, width=54, height=18,
                                  bg=Palette.BG_PANEL, highlightthickness=0)
        self.traffic.pack(side="left", padx=(16, 12))
        self._tc1 = self.traffic.create_oval(4, 4, 14, 14, fill="#2a2a35", outline="")
        self._tc2 = self.traffic.create_oval(22, 4, 32, 14, fill="#2a2a35", outline="")
        self._tc3 = self.traffic.create_oval(40, 4, 50, 14, fill="#2a2a35", outline="")

        self.term_title = ctk.CTkLabel(
            title_bar, text="RedSave Terminal",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=Palette.TEXT_DIM)
        self.term_title.pack(side="left", padx=8)

        self.live_btn = ctk.CTkButton(
            title_bar, text="", width=80, height=24,
            fg_color="transparent", hover_color=Palette.BG_CARD,
            text_color=Palette.ACCENT_GLOW,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._jump_to_end)
        self.live_btn.pack(side="right", padx=12)

        # Поле вывода
        self.terminal = ctk.CTkTextbox(
            self.term_container,
            font=ctk.CTkFont(family="Consolas", size=self.app.config_data.get("font_size", 13)),
            fg_color=Palette.BG_DARK, border_width=0, corner_radius=0,
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
                                        corner_radius=0, height=56)
        input_container.grid(row=2, column=0, sticky="ew")
        input_container.grid_propagate(False)

        self.prompt = ctk.CTkLabel(
            input_container, text="❯",
            font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
            text_color=Palette.ACCENT)
        self.prompt.pack(side="left", padx=(20, 8))
        self._start_prompt_pulse()

        self.entry = ctk.CTkEntry(
            input_container,
            placeholder_text="Введите команду... (например: help, ping, tex on 1h)",
            font=ctk.CTkFont(family="Consolas", size=self.app.config_data.get("font_size", 13)),
            fg_color="transparent", border_width=0,
            text_color=Palette.TEXT, placeholder_text_color=Palette.TEXT_DIM2)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=12)
        self.entry.bind("<Return>", lambda e: self.on_enter())
        self.entry.bind("<Up>", self.history_up)
        self.entry.bind("<Down>", self.history_down)
        self.entry.bind("<Tab>", self.autocomplete)
        self.entry.bind("<Control-v>", self._paste)
        self.entry.bind("<Control-V>", self._paste)
        self.entry.focus_set()

        ctk.CTkButton(
            input_container, text="Enter ⏎", width=100, height=36,
            fg_color=Palette.ACCENT, hover_color=Palette.ACCENT_HOVER,
            text_color="#ffffff", corner_radius=10,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.on_enter).pack(side="right", padx=(0, 20), pady=10)

        # Прогресс бар
        self.progress = ctk.CTkProgressBar(self.term_container, height=3,
                                            progress_color=Palette.ACCENT_GLOW)
        self.progress.grid(row=3, column=0, sticky="ew")
        self.progress.grid_remove()
        self.progress.configure(mode="indeterminate")

        # Приветственное сообщение
        self.typing_queue = [
            (f"RedSave Terminal {APP_VERSION}", "header"),
            (f"API: {API_URL}", "info"),
            (f"{random.choice(FORTUNES)}", "info"),
            ("tex on 1h / tex off — управление тех. работами", "info"),
            ("help — список доступных команд", "info"),
            ("", "normal"),
        ]
        self.after(200, self._type_next)

    def _start_prompt_pulse(self):
        def pulse(i=0):
            if not self.prompt.winfo_exists(): return
            try:
                colors = [Palette.ACCENT, Palette.ACCENT_GLOW, Palette.CYAN, Palette.ACCENT]
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
        colors = {"cmd": Palette.INFO, "ok": Palette.SUCCESS, "err": Palette.ERROR,
                  "warn": Palette.WARNING, "info": Palette.TEXT_DIM2,
                  "header": Palette.ACCENT_GLOW, "id": "#fbbf24", "date": "#a78bfa"}
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
                self.app.toast(f"Скопировано: {m.group(0)}")
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
                "ping              — проверка связи",
                "ban ID [time] [reason] — забанить пользователя",
                "unban ID          — снять бан",
                "banlist           — список забаненных",
                "checkban ID       — проверить статус бана",
                "idlist            — список всех пользователей",
                "ai вопрос         — запрос к AI",
                "data              — текущая дата и время",
                "tex on 1h         — включить тех. работы на 1 час",
                "tex off           — выключить тех. работы",
                "tex               — статус тех. работ",
                "calc выражение    — калькулятор",
                "alias name=cmd    — создать алиас",
                "config            — показать настройки",
                "color N           — сменить тему (1-8)",
                "uptime / mem      — информация о ресурсах",
                "export <path>     — сохранить лог в файл",
                "reset             — сбросить настройки",
                "clear             — очистить экран",
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
                    self.write(f"✅ Тема изменена: {COLOR_THEMES[n][3]}", "ok")
                else:
                    self.write("❌ Выберите число от 1 до 8", "err")
                self.write("")
            except Exception:
                self.write("❌ Использование: color N (1-8) или color list", "err")
            return

        if cmd == "calc":
            self.write(f"❯ {raw}", "cmd")
            try:
                allowed = set("0123456789+-*/(). %")
                if not all(c in allowed for c in arg):
                    raise ValueError("Недопустимые символы")
                result = eval(arg, {"__builtins__": {}}, {})
                self.write(f"  = {result}", "ok")
            except Exception as e:
                self.write(f"❌ Ошибка: {e}", "err")
            self.write("")
            return

        if cmd == "alias":
            if "=" in arg:
                name, cmd_val = arg.split("=", 1)
                name, cmd_val = name.strip(), cmd_val.strip()
                self.aliases[name] = cmd_val
                self.app.config_data.setdefault("aliases", {})[name] = cmd_val
                save_config(self.app.config_data)
                self.write(f"✅ Алиас создан: {name} → {cmd_val}", "ok")
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
                    self.write(f"✅ Размер шрифта: {n}", "ok")
                except Exception:
                    self.write("❌ Использование: config font N", "err")
                return
            return

        if cmd == "mute":
            self.app.config_data["sound"] = False
            save_config(self.app.config_data)
            self.write("🔇 Звук выключен", "ok")
            return

        if cmd == "unmute":
            self.app.config_data["sound"] = True
            save_config(self.app.config_data)
            self.write("🔊 Звук включён", "ok")
            play_sound("ok", True)
            return

        if cmd == "lang":
            if arg in ("ru", "en"):
                self.app.config_data["lang"] = arg
                save_config(self.app.config_data)
                self.write(f"✅ Язык изменен: {arg.upper()}", "ok")
            else:
                self.write("❌ Использование: lang ru или lang en", "err")
            return

        if cmd == "fortune":
            self.write(random.choice(FORTUNES), "info")
            return

        if cmd == "uptime":
            up = int(time.time() - self.app.start_time)
            h, rem = divmod(up, 3600)
            m, s = divmod(rem, 60)
            self.write(f"⏱ Аптайм: {h}ч {m}м {s}с", "info")
            return

        if cmd == "mem":
            try:
                import psutil
                p = psutil.Process(os.getpid())
                mb = p.memory_info().rss / 1024 / 1024
                self.write(f"💾 Использование памяти: {mb:.1f} MB", "info")
            except Exception:
                self.write("📦 Модуль psutil не установлен", "warn")
            return

        if cmd == "export":
            path = arg or "export.txt"
            try:
                text = self.terminal.get("1.0", "end")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.write(f"✅ Лог сохранен: {path}", "ok")
            except Exception as e:
                self.write(f"❌ Ошибка сохранения: {e}", "err")
            return

        if cmd == "reset":
            self.app.config_data = {
                "color": 5, "font_size": 13, "sound": True, "lang": "ru",
                "window_geometry": "1280x820", "aliases": {},
            }
            save_config(self.app.config_data)
            self.app._apply_color(5)
            self.app._apply_font_size()
            self.write("✅ Настройки сброшены до заводских", "ok")
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
                self.after(0, lambda: self.app.toast("Команда выполнена"))
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
                self.terminal.tag_config(tag, foreground="#a78bfa")
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
# ГЛАВНОЕ ОКНО (Улучшена компоновка и отступы)
# ============================================================
class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=Palette.BG_DARK)
        self.title(f"RedSave Control {APP_VERSION}")
        self.config_data = load_config()
        self.geometry(self.config_data.get("window_geometry", "1280x820"))
        self.minsize(1000, 640)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.bg_canvas = tk.Canvas(self, bg=Palette.BG_DARK, highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bg_animator = GradientBackground(self.bg_canvas)

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
        self.main_container.grid_columnconfigure(1, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_content()

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self.main_container, fg_color=Palette.BG_PANEL,
                                corner_radius=0, width=240)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        logo = ctk.CTkFrame(sidebar, fg_color="transparent", height=80)
        logo.pack(fill="x", pady=(20, 12))
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="◆", font=ctk.CTkFont(size=32, weight="bold"),
                      text_color=Palette.ACCENT).pack(side="left", padx=(24, 12))
        tf = ctk.CTkFrame(logo, fg_color="transparent")
        tf.pack(side="left", fill="y")
        ctk.CTkLabel(tf, text="RedSave", font=ctk.CTkFont(size=18, weight="bold"),
                      text_color=Palette.TEXT, anchor="w").pack(anchor="w", pady=(18, 0))
        ctk.CTkLabel(tf, text=APP_VERSION, font=ctk.CTkFont(size=10, weight="bold"),
                      text_color=Palette.TEXT_DIM2, anchor="w").pack(anchor="w")

        ctk.CTkFrame(sidebar, fg_color=Palette.BORDER, height=1).pack(fill="x", padx=20, pady=(8, 16))

        self.nav_buttons = {}
        nav = [("dashboard", "🏠", "Дашборд"),
               ("terminal", "▶", "Терминал"),
               ("bans", "🚫", "Баны"),
               ("network", "📡", "Network"),
               ("settings", "⚙", "Настройки")]
        for k, icon, lbl in nav:
            btn = SidebarButton(sidebar, lbl, icon,
                                 command=lambda kk=k: self._switch_tab(kk),
                                 active=(k == "dashboard"))
            btn.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[k] = btn

        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        status_frame = ctk.CTkFrame(sidebar, fg_color=Palette.BG_CARD, corner_radius=16)
        status_frame.pack(fill="x", padx=16, pady=16)
        inner = ctk.CTkFrame(status_frame, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)

        self.status_ring = StatusRing(inner, size=64, bg=Palette.BG_CARD)
        self.status_ring.pack()

        self.status_label = ctk.CTkLabel(inner, text="Проверка...",
                                          font=ctk.CTkFont(size=13, weight="bold"),
                                          text_color=Palette.TEXT)
        self.status_label.pack(pady=(8, 0))

        self.ping_label = ctk.CTkLabel(inner, text="— ms", font=ctk.CTkFont(size=11),
                                        text_color=Palette.TEXT_DIM2)
        self.ping_label.pack()

    def _build_content(self):
        content = ctk.CTkFrame(self.main_container, fg_color="transparent", corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(content, fg_color=Palette.BG_PANEL, corner_radius=0, height=80)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        self.header_title = ctk.CTkLabel(header, text="Дашборд",
                                          font=ctk.CTkFont(size=24, weight="bold"),
                                          text_color=Palette.TEXT)
        self.header_title.pack(side="left", padx=32)

        self.pause_btn = ctk.CTkButton(header, text="⏸  Пауза", width=140, height=40,
                                        fg_color=Palette.BG_CARD, hover_color=Palette.BG_CARD_HOVER,
                                        text_color=Palette.TEXT, corner_radius=12,
                                        font=ctk.CTkFont(size=12, weight="bold"),
                                        border_width=1, border_color=Palette.BORDER,
                                        command=self._toggle_pause)
        self.pause_btn.pack(side="right", padx=(8, 32), pady=20)

        badge_bar = ctk.CTkFrame(content, fg_color="transparent", height=44)
        badge_bar.grid(row=1, column=0, sticky="ew", padx=32, pady=(16, 0))
        badge_bar.grid_propagate(False)

        self.maintenance_badge = MaintenanceBadge(badge_bar, width=300, height=36,
                                                    bg=Palette.BG_DARK)
        self.maintenance_badge.pack(side="left")

        self.content_area = ctk.CTkFrame(content, fg_color="transparent")
        self.content_area.grid(row=2, column=0, sticky="nsew", padx=32, pady=24)
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
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="cards")
        tab.grid_rowconfigure(2, weight=1)

        self.card_users = StatCard(tab, "Пользователей", "—", Palette.INFO)
        self.card_users.grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=(0, 16))
        self.card_bans = StatCard(tab, "Банов", "—", Palette.ERROR)
        self.card_bans.grid(row=0, column=1, sticky="ew", padx=10, pady=(0, 16))
        self.card_ping = StatCard(tab, "Пинг API", "—", Palette.SUCCESS)
        self.card_ping.grid(row=0, column=2, sticky="ew", padx=10, pady=(0, 16))

        rtt_card = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=16,
                                 border_width=1, border_color=Palette.BORDER)
        rtt_card.grid(row=0, column=3, sticky="ew", padx=(10, 0), pady=(0, 16))
        rtt_inner = ctk.CTkFrame(rtt_card, fg_color="transparent")
        rtt_inner.pack(fill="both", expand=True, padx=20, pady=18)
        ctk.CTkLabel(rtt_inner, text="RTT (30 сек)",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      text_color=Palette.TEXT_DIM2).pack(anchor="w")
        self.rtt_graph = RTTGraph(rtt_inner, width=180, height=40, bg=Palette.BG_CARD)
        self.rtt_graph.pack(fill="x", pady=(6, 0))

        actions = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=16,
                                border_width=1, border_color=Palette.BORDER)
        actions.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 16))
        ctk.CTkLabel(actions, text="Быстрые действия",
                      font=ctk.CTkFont(size=15, weight="bold"),
                      text_color=Palette.TEXT).pack(anchor="w", padx=24, pady=(20, 16))
        row = ctk.CTkFrame(actions, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(0, 24))
        for text, cmd, color in [
            ("🏓  Ping", "ping", Palette.INFO),
            ("📋  Banlist", "banlist", Palette.WARNING),
            ("🔢  ID list", "idlist", Palette.ACCENT),
            ("🕒  Date", "data", Palette.ACCENT_GLOW),
            ("🔧  Tex 1h", "tex on 1h", Palette.ERROR),
            ("❓  Help", "help", Palette.TEXT_DIM),
        ]:
            ctk.CTkButton(row, text=text, width=128, height=44,
                           fg_color=Palette.BG_PANEL, hover_color=Palette.BG_CARD_HOVER,
                           text_color=color, corner_radius=12,
                           font=ctk.CTkFont(size=12, weight="bold"),
                           border_width=1, border_color=Palette.BORDER,
                           command=lambda c=cmd: self._send_to_terminal(c)
                           ).pack(side="left", padx=(0, 10))

        log_card = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=16,
                                 border_width=1, border_color=Palette.BORDER)
        log_card.grid(row=2, column=0, columnspan=4, sticky="nsew")
        ctk.CTkLabel(log_card, text="Последние события",
                      font=ctk.CTkFont(size=15, weight="bold"),
                      text_color=Palette.TEXT).pack(anchor="w", padx=24, pady=(20, 12))
        self.mini_log = ctk.CTkTextbox(log_card,
                                        font=ctk.CTkFont(family="Consolas", size=12),
                                        fg_color=Palette.BG_DARK, border_width=0, corner_radius=12,
                                        text_color=Palette.TEXT_DIM, wrap="word")
        self.mini_log.pack(fill="both", expand=True, padx=24, pady=(0, 24))
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
        actions = ctk.CTkFrame(tab, fg_color="transparent")
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        ctk.CTkButton(actions, text="🔄  Обновить", width=140, height=40,
                       fg_color=Palette.BG_CARD, hover_color=Palette.BG_CARD_HOVER,
                       text_color=Palette.TEXT, corner_radius=12,
                       font=ctk.CTkFont(size=12, weight="bold"),
                       border_width=1, border_color=Palette.BORDER,
                       command=self._load_bans).pack(side="left")
        self.bans_container = ctk.CTkScrollableFrame(tab, fg_color=Palette.BG_CARD,
                                                      corner_radius=16,
                                                      border_width=1, border_color=Palette.BORDER)
        self.bans_container.grid(row=1, column=0, sticky="nsew")
        self.bans_container.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.bans_container, text="Нажмите «Обновить» для загрузки",
                      font=ctk.CTkFont(size=13), text_color=Palette.TEXT_DIM2).pack(pady=80)
        return tab

    def _build_network_tab(self):
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        actions = ctk.CTkFrame(tab, fg_color="transparent")
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        ctk.CTkButton(actions, text="🔄  Обновить", width=140, height=40,
                       fg_color=Palette.BG_CARD, hover_color=Palette.BG_CARD_HOVER,
                       text_color=Palette.TEXT, corner_radius=12,
                       font=ctk.CTkFont(size=12, weight="bold"),
                       border_width=1, border_color=Palette.BORDER,
                       command=self._render_network).pack(side="left")
        ctk.CTkButton(actions, text="🗑  Очистить", width=140, height=40,
                       fg_color=Palette.BG_CARD, hover_color=Palette.BG_CARD_HOVER,
                       text_color=Palette.ERROR, corner_radius=12,
                       font=ctk.CTkFont(size=12, weight="bold"),
                       border_width=1, border_color=Palette.BORDER,
                       command=self._clear_network).pack(side="left", padx=(12, 0))
        self.net_stats = ctk.CTkLabel(actions, text="", font=ctk.CTkFont(size=12),
                                       text_color=Palette.TEXT_DIM)
        self.net_stats.pack(side="right", padx=12)
        self.net_container = ctk.CTkScrollableFrame(tab, fg_color=Palette.BG_CARD,
                                                     corner_radius=16,
                                                     border_width=1, border_color=Palette.BORDER)
        self.net_container.grid(row=1, column=0, sticky="nsew")
        self.net_container.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.net_container, text="Запросов пока нет",
                      font=ctk.CTkFont(size=13), text_color=Palette.TEXT_DIM2).pack(pady=80)
        return tab

    def _build_settings_tab(self):
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        info = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=16,
                             border_width=1, border_color=Palette.BORDER)
        info.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        ctk.CTkLabel(info, text="Подключение", font=ctk.CTkFont(size=16, weight="bold"),
                      text_color=Palette.TEXT).pack(anchor="w", padx=24, pady=(20, 16))
        for lbl, val in [("API URL", API_URL), ("Token", APP_TOKEN), ("Версия", APP_VERSION)]:
            r = ctk.CTkFrame(info, fg_color="transparent")
            r.pack(fill="x", padx=24, pady=6)
            ctk.CTkLabel(r, text=f"{lbl}:", width=100, anchor="w",
                          font=ctk.CTkFont(size=12, weight="bold"), text_color=Palette.TEXT_DIM).pack(side="left")
            ctk.CTkLabel(r, text=val, anchor="w",
                          font=ctk.CTkFont(family="Consolas", size=12),
                          text_color=Palette.TEXT).pack(side="left")

        colors = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=16,
                                border_width=1, border_color=Palette.BORDER)
        colors.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        ctk.CTkLabel(colors, text="Цветовая тема",
                      font=ctk.CTkFont(size=16, weight="bold"),
                      text_color=Palette.TEXT).pack(anchor="w", padx=24, pady=(20, 16))
        row = ctk.CTkFrame(colors, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(0, 24))
        for num in range(1, 9):
            bg, fg, _, name = COLOR_THEMES[num]
            ctk.CTkButton(row, text="", width=44, height=44,
                           fg_color=fg, hover_color=bg,
                           corner_radius=12, border_width=2, border_color=Palette.BORDER,
                           command=lambda n=num: self._apply_color(n)).pack(side="left", padx=6)

        maint = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=16,
                              border_width=1, border_color=Palette.BORDER)
        maint.grid(row=2, column=0, sticky="ew")
        ctk.CTkLabel(maint, text="Управление тех. работами",
                      font=ctk.CTkFont(size=16, weight="bold"),
                      text_color=Palette.TEXT).pack(anchor="w", padx=24, pady=(20, 16))
        btn_row = ctk.CTkFrame(maint, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 24))

        for text, cmd, color, hover in [
            ("🔧  30m", "tex on 30m", Palette.WARNING, "#d97706"),
            ("🔧  1h",  "tex on 1h",  Palette.WARNING, "#d97706"),
            ("🔧  3h",  "tex on 3h",  Palette.WARNING, "#d97706"),
            ("✅  Выкл", "tex off",   Palette.SUCCESS, "#16a34a"),
        ]:
            ctk.CTkButton(btn_row, text=text, width=120, height=42,
                           fg_color=color, hover_color=hover,
                           text_color="#000000" if color == Palette.WARNING else "#ffffff",
                           corner_radius=12,
                           font=ctk.CTkFont(size=12, weight="bold"),
                           command=lambda c=cmd: self._send_to_terminal(c)
                           ).pack(side="left", padx=(0, 10))
        return tab

    def _switch_tab(self, key):
        if key == self.current_tab: return
        self.current_tab = key
        for k, btn in self.nav_buttons.items():
            btn._set_active(k == key)
        for k, tab in self.tabs.items():
            if k == key:
                tab.grid(row=0, column=0, sticky="nsew")
            else:
                tab.grid_forget()
        titles = {"dashboard": "Дашборд", "terminal": "Терминал", "bans": "Баны",
                  "network": "Network Monitor", "settings": "Настройки"}
        self.header_title.configure(text=titles.get(key, ""))
        if key == "bans": self._load_bans()
        if key == "network": self._render_network()

    def _show_tab(self, key):
        self.current_tab = key
        for k, tab in self.tabs.items():
            if k == key:
                tab.grid(row=0, column=0, sticky="nsew")
            else:
                tab.grid_forget()
        titles = {"dashboard": "Дашборд", "terminal": "Терминал", "bans": "Баны",
                  "network": "Network Monitor", "settings": "Настройки"}
        self.header_title.configure(text=titles.get(key, ""))

    def _apply_color(self, num):
        if num not in COLOR_THEMES: return False
        self.current_color = num
        self.config_data["color"] = num
        save_config(self.config_data)
        bg, fg, dim, name = COLOR_THEMES[num]
        try:
            if hasattr(self, "terminal_widget"):
                self.terminal_widget.terminal.configure(fg_color=bg, text_color=fg)
                self.terminal_widget.term_title.configure(text=f"RedSave Terminal — {name}")
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
            for k, btn in self.nav_buttons.items():
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

        if paused:
            self.status_ring.set_state("paused")
            self.status_label.configure(text="Пауза", text_color=Palette.WARNING)
        elif online:
            self.status_ring.set_state("online")
            self.status_label.configure(text="Онлайн", text_color=Palette.SUCCESS)
        else:
            self.status_ring.set_state("offline")
            self.status_label.configure(text="Офлайн", text_color=Palette.ERROR)

        self.ping_label.configure(text=f"{ping} ms" if ping else "— ms")
        if ping:
            self.card_ping.set_value(f"{ping}")
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
        if self.paused:
            self.pause_btn.configure(text="▶  Возобновить",
                                      fg_color=Palette.SUCCESS, hover_color="#16a34a",
                                      text_color="#ffffff")
        else:
            self.pause_btn.configure(text="⏸  Пауза",
                                      fg_color=Palette.BG_CARD,
                                      hover_color=Palette.BG_CARD_HOVER,
                                      text_color=Palette.TEXT)

    def _toggle_pause(self):
        def task():
            if self.paused:
                data = self.api.resume()
                if "error" not in data:
                    self.paused = False
                    self.after(0, lambda: self.toast("Бот возобновлён"))
            else:
                data = self.api.pause()
                if "error" not in data:
                    self.paused = True
                    self.after(0, lambda: self.toast("Бот поставлен на паузу", "warn"))
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
                          text_color=Palette.ERROR, font=ctk.CTkFont(size=13)).pack(pady=80)
            return
        result = data.get("result", "")
        if "пуст" in result.lower():
            ctk.CTkLabel(self.bans_container, text="📋 Бан-лист пуст",
                          text_color=Palette.TEXT_DIM2,
                          font=ctk.CTkFont(size=13)).pack(pady=80)
            return
        for line in [l.strip() for l in result.split("\n") if l.strip() and not l.startswith("📋")]:
            row = ctk.CTkFrame(self.bans_container, fg_color=Palette.BG_PANEL,
                                corner_radius=12, border_width=1, border_color=Palette.BORDER)
            row.pack(fill="x", padx=8, pady=4)
            ctk.CTkLabel(row, text=line, anchor="w",
                          font=ctk.CTkFont(family="Consolas", size=12),
                          text_color=Palette.TEXT).pack(fill="x", padx=16, pady=12)

    def _render_network(self):
        for w in self.net_container.winfo_children():
            w.destroy()
        entries = NET_MONITOR.get_all()
        if not entries:
            ctk.CTkLabel(self.net_container, text="Запросов пока нет",
                          text_color=Palette.TEXT_DIM2,
                          font=ctk.CTkFont(size=13)).pack(pady=80)
            self.net_stats.configure(text="")
            return
        total = len(entries)
        errs = sum(1 for e in entries if e.get("error") or (e.get("status") or 0) >= 400)
        avg = sum(e.get("duration_ms", 0) for e in entries) / max(1, total)
        self.net_stats.configure(text=f"Всего: {total}  |  Ошибок: {errs}  |  Среднее: {int(avg)}ms")
        for e in reversed(entries[-100:]):
            row = ctk.CTkFrame(self.net_container, fg_color=Palette.BG_PANEL,
                                corner_radius=10, border_width=1, border_color=Palette.BORDER)
            row.pack(fill="x", padx=6, pady=4)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=16, pady=10)
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
                          text_color=Palette.TEXT_DIM).pack(fill="x", pady=(6, 0))
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
