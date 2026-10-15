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
from tkinter import font as tkfont

# ============================================================
# КОНФИГ
# ============================================================
API_URL = "https://telegramprobot.relaxdev.ru/webhook"
APP_TOKEN = "871410danil"
APP_VERSION = "3.1.0-visual"

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".redsave_config.json")
HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".redsave_history.json")

COLOR_THEMES = {
    1: ("#0a1929", "#4da6ff", "#2a5d8f", "Синий"),
    2: ("#0a1f0a", "#33ff33", "#1a5c1a", "Зелёный"),
    3: ("#1f0a0a", "#ff4d4d", "#8f2a2a", "Красный"),
    4: ("#1f1400", "#ffa64d", "#8f5a2a", "Оранжевый"),
    5: ("#0d0d0d", "#e0e0e0", "#666666", "Обычный"),
    6: ("#1a0a1f", "#c44dff", "#7a2a8f", "Фиолетовый"),
    7: ("#001a1a", "#4dffff", "#2a8f8f", "Бирюзовый"),
    8: ("#1a1a00", "#ffff4d", "#8f8f2a", "Жёлтый"),
}

ALIASES = {
    "cls": "clear", "q": "ping", "h": "help",
    "b": "banlist", "l": "idlist", "?": "help",
}

FORTUNES = [
    "«Код — это поэзия, только компилятор — критик.»",
    "«Преждевременная оптимизация — корень всех зол.» — Дональд Кнут",
    "«Простота — высшая форма изящества.» — Леонардо да Винчи",
    "«Работает? Не трогай!» — Народная мудрость",
    "«Программист — это машина, превращающая кофе в код.»",
    "«Хороший код — это код, который легко удалить.»",
    "«Отладка в два раза сложнее написания. Если вы пишете максимально умно — вы не сможете отлаживать.»",
    "«Сначала решите задачу. Потом пишите код.» — Джон Джонсон",
]

# ============================================================
# ПАЛИТРА
# ============================================================
class Palette:
    BG_DARK = "#0a0a0f"
    BG_PANEL = "#111118"
    BG_CARD = "#1a1a24"
    BG_CARD_HOVER = "#22222e"
    BG_INPUT = "#15151d"
    BORDER = "#252532"
    BORDER_LIGHT = "#353545"
    TEXT = "#e8e8f0"
    TEXT_DIM = "#8888a0"
    TEXT_DIM2 = "#55556a"
    ACCENT = "#6366f1"
    ACCENT_HOVER = "#7c7ff2"
    ACCENT_GLOW = "#8b5cf6"
    SUCCESS = "#22c55e"
    ERROR = "#ef4444"
    WARNING = "#f59e0b"
    INFO = "#3b82f6"

# ============================================================
# КОНФИГ / ИСТОРИЯ
# ============================================================
def load_config():
    defaults = {
        "color": 5, "font_size": 13, "sound": True, "lang": "ru",
        "window_geometry": "1100x720", "aliases": {},
        "accent_color": "#6366f1", "animations": True,
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                defaults.update(json.load(f))
        except Exception:
            pass
    return defaults

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history[-200:], f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def play_sound(kind="ok", enabled=True):
    if not enabled:
        return
    try:
        if sys.platform == "win32":
            import winsound
            if kind == "ok": winsound.MessageBeep(winsound.MB_ICONASTERISK)
            elif kind == "err": winsound.MessageBeep(winsound.MB_ICONHAND)
            elif kind == "warn": winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass

# ============================================================
# ACRYLIC BLUR (Windows 10/11)
# ============================================================
def enable_acrylic(hwnd, alpha=200):
    """Включает Acrylic blur через WinAPI. Работает только на Windows."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int),
                        ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_uint),
                        ("AnimationId", ctypes.c_int)]
        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int),
                        ("Data", ctypes.POINTER(ACCENT_POLICY)),
                        ("SizeOfData", ctypes.c_size_t)]
        # ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
        accent = ACCENT_POLICY()
        accent.AccentState = 4
        accent.GradientColor = (alpha << 24) | 0x000000
        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)
        ctypes.windll.user32.SetWindowCompositionAttribute(int(hwnd), ctypes.byref(data))
        return True
    except Exception:
        return False

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
        try:
            r = requests.post(url, headers=self.headers, json=data or {}, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code == 401: return {"error": "Неверный токен"}
            if code == 423: return {"error": "Бот на паузе"}
            if code == 404: return {"error": "RelaxDev не проксирует этот путь"}
            return {"error": f"HTTP {code}"}
        except requests.exceptions.ConnectionError:
            return {"error": "Нет соединения с ботом"}
        except requests.exceptions.Timeout:
            return {"error": "Таймаут"}
        except Exception as e:
            return {"error": str(e)}

    def ping(self): return self._post("ping")
    def status(self): return self._post("status")
    def command(self, cmd): return self._post("command", {"command": cmd})
    def pause(self): return self._post("pause")
    def resume(self): return self._post("resume")

# ============================================================
# 1. АНИМИРОВАННАЯ ТОЧКА
# ============================================================
class AnimatedDot(tk.Canvas):
    def __init__(self, parent, color=Palette.SUCCESS, size=14, bg=Palette.BG_CARD):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        self.size = size
        self.color = color
        self.phase = 0
        self.dot = self.create_oval(2, 2, size-2, size-2, fill=color, outline="")
        self._animate()

    def set_color(self, color):
        self.color = color
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

# ============================================================
# 2. ЖИВЫЕ ТОЧКИ В ЗАГОЛОВКЕ ТЕРМИНАЛА
# ============================================================
class TrafficLights(tk.Canvas):
    """Три точки как в macOS, но с реальным смыслом:
       зелёная — API OK, жёлтая — пауза, красная — нет связи."""
    def __init__(self, parent, size=(54, 18), bg=Palette.BG_PANEL):
        super().__init__(parent, width=size[0], height=size[1],
                          bg=bg, highlightthickness=0)
        self.c1 = self.create_oval(4, 4, 14, 14, fill="#2a2a35", outline="")
        self.c2 = self.create_oval(22, 4, 32, 14, fill="#2a2a35", outline="")
        self.c3 = self.create_oval(40, 4, 50, 14, fill="#2a2a35", outline="")
        self.phase = 0
        self.state = "unknown"
        self._animate()

    def set_state(self, state):
        """state: online | paused | offline | unknown"""
        self.state = state
        colors = {
            "online": ("#22c55e", "#2a2a35", "#2a2a35"),
            "paused": ("#2a2a35", "#f59e0b", "#2a2a35"),
            "offline": ("#2a2a35", "#2a2a35", "#ef4444"),
            "unknown": ("#2a2a35", "#2a2a35", "#2a2a35"),
        }
        c1, c2, c3 = colors.get(state, colors["unknown"])
        try:
            self.itemconfig(self.c1, fill=c1)
            self.itemconfig(self.c2, fill=c2)
            self.itemconfig(self.c3, fill=c3)
        except Exception: pass

    def _animate(self):
        if not self.winfo_exists(): return
        try:
            self.phase += 1
            if self.state == "online":
                alpha = 0.75 + 0.25 * math.sin(self.phase / 25)
                # плавная пульсация зелёной
                self.itemconfig(self.c1, outline="#22c55e", width=1)
        except Exception: pass
        try: self.after(60, self._animate)
        except Exception: pass

# ============================================================
# 3. МИКРО-ГРАФИК RTT (последние 30 замеров)
# ============================================================
class RTTGraph(tk.Canvas):
    def __init__(self, parent, width=180, height=32, bg=Palette.BG_CARD):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0)
        self.width = width
        self.height = height
        self.values = [0] * 30  # последние 30
        self.max_v = 200
        self._draw()

    def push(self, value):
        if value is None or value < 0:
            value = 0
        self.values.pop(0)
        self.values.append(value)
        self.max_v = max(200, max(self.values) + 20)
        self._draw()

    def _draw(self):
        try:
            self.delete("all")
            w, h = self.width, self.height
            # фоновая сетка
            for i in range(1, 4):
                y = h * i / 4
                self.create_line(0, y, w, y, fill="#1f1f2a")
            # график
            n = len(self.values)
            step = w / max(1, n - 1)
            points = []
            for i, v in enumerate(self.values):
                x = i * step
                y = h - (v / self.max_v) * h
                points.extend([x, y])
            if len(points) >= 4:
                self.create_line(*points, fill=Palette.ACCENT_GLOW, width=2, smooth=True)
                # заливка под графиком
                poly = points + [w, h, 0, h]
                self.create_polygon(*poly, fill=Palette.ACCENT, outline="")
            # текущее значение
            cur = self.values[-1]
            color = Palette.SUCCESS if cur < 100 else (Palette.WARNING if cur < 500 else Palette.ERROR)
            self.create_text(w - 4, 8, text=f"{cur}ms", anchor="e",
                             fill=color, font=("Arial", 9, "bold"))
        except Exception: pass

# ============================================================
# 4. КАРТОЧКА СТАТИСТИКИ
# ============================================================
class StatCard(ctk.CTkFrame):
    def __init__(self, parent, label, value="—", accent=Palette.ACCENT, small=False):
        super().__init__(parent, fg_color=Palette.BG_CARD, corner_radius=12,
                         border_width=1, border_color=Palette.BORDER)
        size = 18 if small else 24
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        self.value_label = ctk.CTkLabel(
            inner, text=value, font=ctk.CTkFont(size=size, weight="bold"),
            text_color=accent
        )
        self.value_label.pack(anchor="w")
        ctk.CTkLabel(
            inner, text=label.upper(), font=ctk.CTkFont(size=10, weight="bold"),
            text_color=Palette.TEXT_DIM2
        ).pack(anchor="w", pady=(2, 0))

    def set_value(self, value):
        self.value_label.configure(text=value)

# ============================================================
# 5. КНОПКА САЙДБАРА
# ============================================================
class SidebarButton(ctk.CTkFrame):
    def __init__(self, parent, text, icon, command=None, active=False):
        super().__init__(parent, fg_color="transparent", height=42)
        self.pack_propagate(False)
        self.command = command
        self.active = active
        self.icon_label = ctk.CTkLabel(
            self, text=icon, font=ctk.CTkFont(size=16),
            text_color=Palette.ACCENT if active else Palette.TEXT_DIM, width=32
        )
        self.icon_label.pack(side="left", padx=(10, 0))
        self.text_label = ctk.CTkLabel(
            self, text=text, font=ctk.CTkFont(size=13),
            text_color=Palette.TEXT if active else Palette.TEXT_DIM, anchor="w"
        )
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
            self.icon_label.configure(text_color=Palette.ACCENT)
            self.text_label.configure(text_color=Palette.TEXT)
        else:
            self.configure(fg_color="transparent")
            self.icon_label.configure(text_color=Palette.TEXT_DIM)
            self.text_label.configure(text_color=Palette.TEXT_DIM)

    def _on_enter(self, e):
        if not self.active:
            self.configure(fg_color=Palette.BG_CARD)
    def _on_leave(self, e):
        if not self.active:
            self.configure(fg_color="transparent")
    def _on_click(self, e):
        if self.command: self.command()

# ============================================================
# 6. ТЕРМИНАЛ (с sticky scroll + живыми точками)
# ============================================================
class Terminal(ctk.CTkFrame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.app = app
        self.history = load_history()
        self.history_index = len(self.history)
        self.aliases = dict(ALIASES)
        self.aliases.update(app.config.get("aliases", {}))
        self.sticky_scroll = True
        self.build()

    def build(self):
        self.term_container = ctk.CTkFrame(
            self, fg_color=Palette.BG_DARK, corner_radius=12,
            border_width=1, border_color=Palette.BORDER
        )
        self.term_container.pack(fill="both", expand=True)
        self.term_container.grid_columnconfigure(0, weight=1)
        self.term_container.grid_rowconfigure(1, weight=1)

        # Заголовок с живыми точками
        title_bar = ctk.CTkFrame(self.term_container, fg_color=Palette.BG_PANEL,
                                  corner_radius=0, height=36)
        title_bar.grid(row=0, column=0, sticky="ew")
        title_bar.grid_propagate(False)

        self.traffic = TrafficLights(title_bar, bg=Palette.BG_PANEL)
        self.traffic.pack(side="left", padx=(12, 8))

        self.term_title = ctk.CTkLabel(
            title_bar, text="RedSave Terminal",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=Palette.TEXT_DIM
        )
        self.term_title.pack(side="left", padx=8)

        # Индикатор Live OFF
        self.live_btn = ctk.CTkButton(
            title_bar, text="", width=80, height=22,
            fg_color="transparent", hover_color=Palette.BG_CARD,
            text_color=Palette.ACCENT_GLOW,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._jump_to_end
        )
        self.live_btn.pack(side="right", padx=8)

        # Область вывода
        self.terminal = ctk.CTkTextbox(
            self.term_container,
            font=ctk.CTkFont(family="Consolas", size=self.app.config.get("font_size", 13)),
            fg_color=Palette.BG_DARK, border_width=0, corner_radius=0,
            text_color=Palette.TEXT, wrap="word"
        )
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

        # Строка ввода
        input_container = ctk.CTkFrame(self.term_container, fg_color=Palette.BG_INPUT,
                                        corner_radius=0, height=48)
        input_container.grid(row=2, column=0, sticky="ew")
        input_container.grid_propagate(False)

        self.prompt = ctk.CTkLabel(
            input_container, text="❯",
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            text_color=Palette.ACCENT
        )
        self.prompt.pack(side="left", padx=(14, 8))
        self._start_prompt_pulse()

        self.entry = ctk.CTkEntry(
            input_container,
            placeholder_text="Команда... (help — справка, ↑↓ — история, Tab — автодополнение)",
            font=ctk.CTkFont(family="Consolas", size=self.app.config.get("font_size", 13)),
            fg_color="transparent", border_width=0,
            text_color=Palette.TEXT, placeholder_text_color=Palette.TEXT_DIM2
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=8)
        self.entry.bind("<Return>", lambda e: self.on_enter())
        self.entry.bind("<Up>", self.history_up)
        self.entry.bind("<Down>", self.history_down)
        self.entry.bind("<Tab>", self.autocomplete)
        self.entry.bind("<Control-v>", self._paste)
        self.entry.bind("<Control-V>", self._paste)
        self.entry.focus_set()

        ctk.CTkButton(
            input_container, text="Enter ⏎", width=80, height=32,
            fg_color=Palette.ACCENT, hover_color=Palette.ACCENT_HOVER,
            text_color="#ffffff", corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.on_enter
        ).pack(side="right", padx=(0, 12), pady=8)

        # Прогресс-бар
        self.progress = ctk.CTkProgressBar(self.term_container, height=2,
                                            progress_color=Palette.ACCENT)
        self.progress.grid(row=3, column=0, sticky="ew")
        self.progress.grid_remove()
        self.progress.configure(mode="indeterminate")

        # Приветствие
        self.typing_queue = [
            (f"RedSave Terminal {APP_VERSION}", "header"),
            (f"API: {API_URL}", "info"),
            (f"Fortune: {random.choice(FORTUNES)}", "info"),
            ("Введите 'help' для списка команд", "info"),
            ("", "normal"),
        ]
        self.after(150, self._type_next)

    # --- пульсация префикса ❯ ---
    def _start_prompt_pulse(self):
        def pulse(i=0):
            if not self.prompt.winfo_exists(): return
            try:
                t = (i % 60) / 60
                colors = [Palette.ACCENT, Palette.ACCENT_GLOW, Palette.ACCENT]
                self.prompt.configure(text_color=colors[i % 3])
            except Exception: pass
            try: self.after(400, lambda: pulse(i + 1))
            except Exception: pass
        pulse()

    # --- печатная машинка ---
    def _type_next(self):
        if not self.typing_queue:
            return
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
        colors = {
            "cmd": Palette.INFO, "ok": Palette.SUCCESS, "err": Palette.ERROR,
            "warn": Palette.WARNING, "info": Palette.TEXT_DIM2,
            "header": Palette.ACCENT_GLOW, "id": "#fbbf24", "date": "#a78bfa",
        }
        if kind in colors:
            self.terminal.tag_config(tag, foreground=colors[kind])

    def write(self, text, kind="normal"):
        # Ограничение буфера — 10 000 строк
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
        try:
            self.entry.insert("end", self.clipboard_get())
        except Exception: pass
        return "break"

    def _on_scroll(self, event):
        # Ctrl + wheel = zoom
        if event.state & 0x0004:
            delta = 1 if (getattr(event, "delta", 0) > 0 or event.num == 4) else -1
            self.app.config["font_size"] = max(8, min(24, self.app.config.get("font_size", 13) + delta))
            self.app._apply_font_size()
            return "break"
        # обычный скролл — sticky
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
                    "unmute", "lang", "reset"]
        matches = [c for c in all_cmds if c.startswith(current) and current]
        if len(matches) == 1:
            self.entry.delete(0, "end")
            self.entry.insert(0, matches[0] + " ")
        elif matches:
            self.write("  ".join(matches), "info")
        return "break"

    # ------------------------------------------------------------
    # ЗАПУСК КОМАНДЫ
    # ------------------------------------------------------------
    def run(self, raw):
        low = raw.strip().lower()
        parts = low.split(maxsplit=1)
        cmd = parts[0] if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in self.aliases:
            cmd = self.aliases[cmd]
            raw = cmd + (" " + arg if arg else "")

        if cmd == "clear":
            self._clear_terminal(); return

        if cmd == "help":
            self.write(f"❯ {raw}", "cmd")
            for line in [
                "ping              — пинг",
                "ban ID [time] [reason] — забанить",
                "unban ID          — разбанить",
                "banlist           — список банов",
                "checkban ID       — проверить бан",
                "idlist            — список пользователей",
                "ai вопрос         — спросить AI",
                "data              — текущее время",
                "calc выражение    — локальный калькулятор",
                "alias name=cmd    — создать алиас",
                "config            — показать настройки",
                "config font N     — сменить размер шрифта",
                "color N           — сменить цвет (1-8)",
                "color list        — список цветов",
                "mute / unmute     — звук вкл/выкл",
                "lang ru / en      — язык",
                "fortune           — случайная цитата",
                "uptime            — время работы",
                "mem               — потребление RAM",
                "export <path>     — сохранить вывод",
                "reset             — сброс настроек",
                "clear             — очистить",
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
                self.write(""); return
            try:
                n = int(arg)
                self.write(f"❯ {raw}", "cmd")
                if self.app._apply_color(n):
                    self.write(f"✅ Цвет изменён: {COLOR_THEMES[n][3]}", "ok")
                else:
                    self.write("❌ Неверный цвет. Доступно 1-8", "err")
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
                self.app.config.setdefault("aliases", {})[name] = cmd_val
                save_config(self.app.config)
                self.write(f"✅ Алиас: {name} → {cmd_val}", "ok")
            else:
                self.write(f"❯ {raw}", "cmd")
                for k, v in self.aliases.items():
                    self.write(f"  {k} → {v}", "info")
                self.write("")
            return

        if cmd == "config":
            if not arg:
                self.write(f"❯ {raw}", "cmd")
                for k, v in self.app.config.items():
                    self.write(f"  {k}: {v}", "info")
                self.write("")
                return
            if arg.startswith("font"):
                try:
                    n = int(arg.split()[1])
                    self.app.config["font_size"] = max(8, min(24, n))
                    save_config(self.app.config)
                    self.app._apply_font_size()
                    self.write(f"✅ Шрифт: {n}", "ok")
                except Exception:
                    self.write("❌ config font N", "err")
                return
            return

        if cmd == "mute":
            self.app.config["sound"] = False
            save_config(self.app.config)
            self.write("🔇 Звук выключен", "ok"); return

        if cmd == "unmute":
            self.app.config["sound"] = True
            save_config(self.app.config)
            self.write("🔊 Звук включён", "ok")
            play_sound("ok", True); return

        if cmd == "lang":
            if arg in ("ru", "en"):
                self.app.config["lang"] = arg
                save_config(self.app.config)
                self.write(f"✅ Язык: {arg}", "ok")
            else:
                self.write("❌ lang ru / lang en", "err")
            return

        if cmd == "fortune":
            self.write(random.choice(FORTUNES), "info"); return

        if cmd == "uptime":
            up = int(time.time() - self.app.start_time)
            h, rem = divmod(up, 3600)
            m, s = divmod(rem, 60)
            self.write(f"⏱ {h}ч {m}м {s}с", "info"); return

        if cmd == "mem":
            try:
                import psutil
                p = psutil.Process(os.getpid())
                mb = p.memory_info().rss / 1024 / 1024
                self.write(f"💾 {mb:.1f} MB", "info")
            except Exception:
                self.write("📦 psutil не установлен", "warn")
            return

        if cmd == "export":
            path = arg or "export.txt"
            try:
                text = self.terminal.get("1.0", "end")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.write(f"✅ Сохранено в {path}", "ok")
            except Exception as e:
                self.write(f"❌ {e}", "err")
            return

        if cmd == "reset":
            self.app.config = {
                "color": 5, "font_size": 13, "sound": True, "lang": "ru",
                "window_geometry": "1100x720", "aliases": {},
                "accent_color": "#6366f1", "animations": True,
            }
            save_config(self.app.config)
            self.app._apply_color(5)
            self.app._apply_font_size()
            self.write("✅ Настройки сброшены", "ok"); return

        # --- сетевые ---
        self.write(f"❯ {raw}", "cmd")
        self._progress_show()

        def task():
            data = self.app.api.command(raw)
            self.after(0, self._progress_hide)
            if "error" in data:
                self.after(0, lambda: self.write(f"❌ {data['error']}", "err"))
                self.after(0, lambda: play_sound("err", self.app.config.get("sound", True)))
                self.after(0, lambda: self.app.toast(data["error"], "err"))
            else:
                result = data.get("result", "")
                for line in result.split("\n"):
                    self.after(0, lambda l=line: self._write_highlighted(l))
                self.after(0, lambda: play_sound("ok", self.app.config.get("sound", True)))
                self.after(0, lambda: self.app.mini_log(f"✓ {cmd}", "ok"))
                self.after(0, lambda: self.app.toast("OK"))
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
# ГЛАВНОЕ ОКНО
# ============================================================
class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=Palette.BG_DARK)
        self.title(f"RedSave Control {APP_VERSION}")
        self.config_data = load_config()
        self.geometry(self.config_data.get("window_geometry", "1100x720"))
        self.minsize(900, 600)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Acrylic blur (только Windows)
        self.after(100, self._try_acrylic)

        self.api = BotAPI(API_URL, APP_TOKEN)
        self.paused = False
        self._status_running = True
        self.current_color = self.config_data.get("color", 5)
        self.current_tab = "dashboard"
        self.start_time = time.time()

        # Для микро-графика RTT
        self.rtt_values = []

        self._build_ui()
        self._apply_color(self.current_color)
        self._apply_font_size()
        self._start_status_loop()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _try_acrylic(self):
        try:
            self.update_idletasks()
            hwnd = self.winfo_id()
            # родительское окно
            import ctypes
            parent = ctypes.windll.user32.GetParent(hwnd)
            enable_acrylic(parent or hwnd, alpha=180)
        except Exception:
            pass

    # --- свойства config через self.config_data (чтобы не конфликтовать с CTk) ---
    @property
    def config(self):
        return self.config_data

    @config.setter
    def config(self, value):
        self.config_data = value

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_content()

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, fg_color=Palette.BG_PANEL, corner_radius=0, width=220)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        logo = ctk.CTkFrame(sidebar, fg_color="transparent", height=70)
        logo.pack(fill="x", pady=(16, 8))
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="◆", font=ctk.CTkFont(size=26, weight="bold"),
                      text_color=Palette.ACCENT).pack(side="left", padx=(20, 8))
        tf = ctk.CTkFrame(logo, fg_color="transparent")
        tf.pack(side="left", fill="y")
        ctk.CTkLabel(tf, text="RedSave", font=ctk.CTkFont(size=16, weight="bold"),
                      text_color=Palette.TEXT, anchor="w").pack(anchor="w", pady=(14, 0))
        ctk.CTkLabel(tf, text=APP_VERSION, font=ctk.CTkFont(size=10),
                      text_color=Palette.TEXT_DIM2, anchor="w").pack(anchor="w")

        ctk.CTkFrame(sidebar, fg_color=Palette.BORDER, height=1).pack(fill="x", padx=16, pady=(8, 12))

        self.nav_buttons = {}
        nav = [("dashboard", "🏠", "Дашборд"),
               ("terminal", "▶", "Терминал"),
               ("bans", "🚫", "Баны"),
               ("settings", "⚙", "Настройки")]
        for k, icon, lbl in nav:
            btn = SidebarButton(sidebar, lbl, icon,
                                 command=lambda kk=k: self._switch_tab(kk),
                                 active=(k == "dashboard"))
            btn.pack(fill="x", padx=8, pady=2)
            self.nav_buttons[k] = btn

        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        status_frame = ctk.CTkFrame(sidebar, fg_color=Palette.BG_CARD, corner_radius=10)
        status_frame.pack(fill="x", padx=12, pady=12)
        inner = ctk.CTkFrame(status_frame, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=12)
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")
        self.status_dot = AnimatedDot(row, color=Palette.TEXT_DIM2, bg=Palette.BG_CARD)
        self.status_dot.pack(side="left", padx=(0, 8))
        self.status_label = ctk.CTkLabel(row, text="Проверка...",
                                          font=ctk.CTkFont(size=12, weight="bold"),
                                          text_color=Palette.TEXT)
        self.status_label.pack(side="left")
        self.ping_label = ctk.CTkLabel(inner, text="— ms", font=ctk.CTkFont(size=10),
                                        text_color=Palette.TEXT_DIM2, anchor="w")
        self.ping_label.pack(anchor="w", pady=(4, 0))

    def _build_content(self):
        content = ctk.CTkFrame(self, fg_color=Palette.BG_DARK, corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(content, fg_color=Palette.BG_PANEL, corner_radius=0, height=70)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        self.header_title = ctk.CTkLabel(header, text="Дашборд",
                                          font=ctk.CTkFont(size=20, weight="bold"),
                                          text_color=Palette.TEXT)
        self.header_title.pack(side="left", padx=24)

        self.pause_btn = ctk.CTkButton(header, text="⏸  Пауза", width=120, height=36,
                                        fg_color=Palette.BG_CARD, hover_color=Palette.BG_CARD_HOVER,
                                        text_color=Palette.TEXT, corner_radius=8,
                                        font=ctk.CTkFont(size=12, weight="bold"),
                                        command=self._toggle_pause)
        self.pause_btn.pack(side="right", padx=(8, 24), pady=17)

        self.content_area = ctk.CTkFrame(content, fg_color="transparent")
        self.content_area.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

        self.tabs = {
            "dashboard": self._build_dashboard_tab(),
            "terminal": self._build_terminal_tab(),
            "bans": self._build_bans_tab(),
            "settings": self._build_settings_tab(),
        }
        self._show_tab("dashboard")

    def _build_dashboard_tab(self):
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="cards")
        tab.grid_rowconfigure(2, weight=1)

        self.card_users = StatCard(tab, "Пользователей", "—", Palette.INFO)
        self.card_users.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 12))
        self.card_bans = StatCard(tab, "Банов", "—", Palette.ERROR)
        self.card_bans.grid(row=0, column=1, sticky="ew", padx=8, pady=(0, 12))
        self.card_ping = StatCard(tab, "Пинг API", "—", Palette.SUCCESS)
        self.card_ping.grid(row=0, column=2, sticky="ew", padx=8, pady=(0, 12))

        # Карточка с микро-графиком RTT
        rtt_card = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=12,
                                 border_width=1, border_color=Palette.BORDER)
        rtt_card.grid(row=0, column=3, sticky="ew", padx=(8, 0), pady=(0, 12))
        rtt_inner = ctk.CTkFrame(rtt_card, fg_color="transparent")
        rtt_inner.pack(fill="both", expand=True, padx=12, pady=12)
        ctk.CTkLabel(rtt_inner, text="RTT",
                      font=ctk.CTkFont(size=10, weight="bold"),
                      text_color=Palette.TEXT_DIM2).pack(anchor="w")
        self.rtt_graph = RTTGraph(rtt_inner, width=170, height=36, bg=Palette.BG_CARD)
        self.rtt_graph.pack(fill="x", pady=(4, 0))

        actions = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=12,
                                border_width=1, border_color=Palette.BORDER)
        actions.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(actions, text="Быстрые действия",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      text_color=Palette.TEXT).pack(anchor="w", padx=20, pady=(16, 12))
        row = ctk.CTkFrame(actions, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 18))
        for text, cmd, color in [
            ("🏓  Ping", "ping", Palette.INFO),
            ("📋  Banlist", "banlist", Palette.WARNING),
            ("🔢  ID list", "idlist", Palette.ACCENT),
            ("🕒  Date", "data", Palette.ACCENT_GLOW),
            ("❓  Help", "help", Palette.TEXT_DIM),
        ]:
            ctk.CTkButton(row, text=text, width=110, height=40,
                           fg_color=Palette.BG_PANEL, hover_color=Palette.BG_CARD_HOVER,
                           text_color=color, corner_radius=10,
                           font=ctk.CTkFont(size=12, weight="bold"),
                           border_width=1, border_color=Palette.BORDER,
                           command=lambda c=cmd: self._send_to_terminal(c)
                           ).pack(side="left", padx=(0, 8))

        log_card = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=12,
                                 border_width=1, border_color=Palette.BORDER)
        log_card.grid(row=2, column=0, columnspan=4, sticky="nsew")
        ctk.CTkLabel(log_card, text="Последние события",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      text_color=Palette.TEXT).pack(anchor="w", padx=20, pady=(16, 8))
        self.mini_log = ctk.CTkTextbox(log_card,
                                        font=ctk.CTkFont(family="Consolas", size=12),
                                        fg_color=Palette.BG_DARK, border_width=0, corner_radius=8,
                                        text_color=Palette.TEXT_DIM, wrap="word")
        self.mini_log.pack(fill="both", expand=True, padx=20, pady=(0, 20))
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
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkButton(actions, text="🔄  Обновить", width=120, height=36,
                       fg_color=Palette.BG_CARD, hover_color=Palette.BG_CARD_HOVER,
                       text_color=Palette.TEXT, corner_radius=8,
                       font=ctk.CTkFont(size=12, weight="bold"),
                       border_width=1, border_color=Palette.BORDER,
                       command=self._load_bans).pack(side="left")
        self.bans_container = ctk.CTkScrollableFrame(tab, fg_color=Palette.BG_CARD,
                                                      corner_radius=12,
                                                      border_width=1, border_color=Palette.BORDER)
        self.bans_container.grid(row=1, column=0, sticky="nsew")
        self.bans_container.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.bans_container, text="Нажмите «Обновить»",
                      font=ctk.CTkFont(size=13), text_color=Palette.TEXT_DIM2).pack(pady=60)
        return tab

    def _build_settings_tab(self):
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        info = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=12,
                             border_width=1, border_color=Palette.BORDER)
        info.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(info, text="Подключение", font=ctk.CTkFont(size=14, weight="bold"),
                      text_color=Palette.TEXT).pack(anchor="w", padx=20, pady=(16, 12))
        for lbl, val in [("API URL", API_URL), ("Token", APP_TOKEN), ("Версия", APP_VERSION)]:
            r = ctk.CTkFrame(info, fg_color="transparent")
            r.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(r, text=f"{lbl}:", width=100, anchor="w",
                          font=ctk.CTkFont(size=12), text_color=Palette.TEXT_DIM).pack(side="left")
            ctk.CTkLabel(r, text=val, anchor="w",
                          font=ctk.CTkFont(family="Consolas", size=12),
                          text_color=Palette.TEXT).pack(side="left")

        colors = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=12,
                                border_width=1, border_color=Palette.BORDER)
        colors.grid(row=1, column=0, sticky="ew")
        ctk.CTkLabel(colors, text="Цвет терминала",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      text_color=Palette.TEXT).pack(anchor="w", padx=20, pady=(16, 12))
        row = ctk.CTkFrame(colors, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 20))
        for num in range(1, 9):
            bg, fg, _, name = COLOR_THEMES[num]
            ctk.CTkButton(row, text="", width=36, height=36,
                           fg_color=fg, hover_color=bg,
                           corner_radius=8, border_width=2, border_color=Palette.BORDER,
                           command=lambda n=num: self._apply_color(n)).pack(side="left", padx=4)
        return tab

    # --- утилиты ---
    def _switch_tab(self, key):
        if key == self.current_tab:
            return
        self.current_tab = key
        for k, btn in self.nav_buttons.items():
            btn._set_active(k == key)
        for k, tab in self.tabs.items():
            if k == key: tab.grid(row=0, column=0, sticky="nsew")
            else: tab.grid_forget()
        titles = {"dashboard": "Дашборд", "terminal": "Терминал",
                  "bans": "Баны", "settings": "Настройки"}
        self.header_title.configure(text=titles.get(key, ""))
        if key == "bans": self._load_bans()

    def _show_tab(self, key):
        self.current_tab = key
        for k, tab in self.tabs.items():
            if k == key: tab.grid(row=0, column=0, sticky="nsew")
            else: tab.grid_forget()
        titles = {"dashboard": "Дашборд", "terminal": "Терминал",
                  "bans": "Баны", "settings": "Настройки"}
        self.header_title.configure(text=titles.get(key, ""))

    def _apply_color(self, num):
        if num not in COLOR_THEMES:
            return False
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

    # --- статус ---
    def _set_status(self, online, ping=None, paused=False):
        if hasattr(self, "terminal_widget") and hasattr(self.terminal_widget, "traffic"):
            if paused:
                self.terminal_widget.traffic.set_state("paused")
            elif online:
                self.terminal_widget.traffic.set_state("online")
            else:
                self.terminal_widget.traffic.set_state("offline")

        if paused:
            self.status_dot.set_color(Palette.WARNING)
            self.status_label.configure(text="Пауза", text_color=Palette.WARNING)
        elif online:
            self.status_dot.set_color(Palette.SUCCESS)
            self.status_label.configure(text="Онлайн", text_color=Palette.SUCCESS)
        else:
            self.status_dot.set_color(Palette.ERROR)
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
                    self.after(0, lambda: self.toast("Бот на паузе", "warn"))
            self.after(0, self._update_pause_button)
        threading.Thread(target=task, daemon=True).start()

    # --- баны ---
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
                          text_color=Palette.ERROR, font=ctk.CTkFont(size=13)).pack(pady=60)
            return
        result = data.get("result", "")
        if "пуст" in result.lower():
            ctk.CTkLabel(self.bans_container, text="📋 Бан-лист пуст",
                          text_color=Palette.TEXT_DIM2,
                          font=ctk.CTkFont(size=13)).pack(pady=60)
            return
        for line in [l.strip() for l in result.split("\n") if l.strip() and not l.startswith("📋")]:
            row = ctk.CTkFrame(self.bans_container, fg_color=Palette.BG_PANEL,
                                corner_radius=8, border_width=1, border_color=Palette.BORDER)
            row.pack(fill="x", padx=4, pady=3)
            ctk.CTkLabel(row, text=line, anchor="w",
                          font=ctk.CTkFont(family="Consolas", size=12),
                          text_color=Palette.TEXT).pack(fill="x", padx=14, pady=10)

    # --- mini log / toast ---
    def mini_log(self, text, kind="normal"):
        if not hasattr(self, "mini_log") or not self.mini_log.winfo_exists():
            return
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
