import customtkinter as ctk
import requests
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

# ============ КОНФИГ ============
API_URL = "https://telegramprobot.relaxdev.ru/webhook"
APP_TOKEN = "871410danil"

# Цветовые темы терминала (фон, основной текст, приглушённый)
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

# ============ ПАЛИТРА ПРИЛОЖЕНИЯ ============
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
    HEADER_GRADIENT_1 = "#6366f1"
    HEADER_GRADIENT_2 = "#8b5cf6"

# ============ API КЛИЕНТ ============
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
            if code == 401:
                return {"error": "Неверный токен"}
            if code == 423:
                return {"error": "Бот на паузе"}
            if code == 404:
                return {"error": "RelaxDev не проксирует этот путь"}
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
    def banlist(self): return self._post("banlist")


# ============ ВСПОМОГАТЕЛЬНЫЕ ВИДЖЕТЫ ============

class AnimatedDot(tk.Canvas):
    """Пульсирующая точка статуса."""
    def __init__(self, parent, color=Palette.SUCCESS, size=14, bg=Palette.BG_PANEL):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        self.size = size
        self.color = color
        self.bg = bg
        self.phase = 0
        self.dot = self.create_oval(2, 2, size-2, size-2, fill=color, outline="")
        self._animate()

    def set_color(self, color):
        self.color = color
        self.itemconfig(self.dot, fill=color)

    def _animate(self):
        if not self.winfo_exists():
            return
        try:
            self.phase = (self.phase + 1) % 40
            # плавная пульсация размера
            import math
            scale = 1 + 0.15 * math.sin(self.phase / 40 * 2 * math.pi)
            cx, cy = self.size / 2, self.size / 2
            r = (self.size - 4) / 2 * scale
            self.coords(self.dot, cx - r, cy - r, cx + r, cy + r)
        except Exception:
            pass
        self.after(50, self._animate)


class StatCard(ctk.CTkFrame):
    """Карточка статистики."""
    def __init__(self, parent, label, value="—", accent=Palette.ACCENT):
        super().__init__(parent, fg_color=Palette.BG_CARD, corner_radius=12,
                         border_width=1, border_color=Palette.BORDER)
        self.accent = accent

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=14)

        self.value_label = ctk.CTkLabel(
            inner, text=value, font=ctk.CTkFont(size=24, weight="bold"),
            text_color=accent
        )
        self.value_label.pack(anchor="w")

        self.label_widget = ctk.CTkLabel(
            inner, text=label.upper(), font=ctk.CTkFont(size=10, weight="bold"),
            text_color=Palette.TEXT_DIM2
        )
        self.label_widget.pack(anchor="w", pady=(2, 0))

    def set_value(self, value):
        self.value_label.configure(text=value)


class SidebarButton(ctk.CTkFrame):
    """Кнопка боковой панели."""
    def __init__(self, parent, text, icon, command=None, active=False):
        super().__init__(parent, fg_color="transparent", height=42)
        self.pack_propagate(False)

        self.command = command
        self.active = active

        self.icon_label = ctk.CTkLabel(
            self, text=icon, font=ctk.CTkFont(size=16),
            text_color=Palette.ACCENT if active else Palette.TEXT_DIM,
            width=32
        )
        self.icon_label.pack(side="left", padx=(10, 0))

        self.text_label = ctk.CTkLabel(
            self, text=text, font=ctk.CTkFont(size=13),
            text_color=Palette.TEXT if active else Palette.TEXT_DIM,
            anchor="w"
        )
        self.text_label.pack(side="left", padx=(4, 0), fill="x", expand=True)

        self._set_active(active)

        # hover
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
        if self.command:
            self.command()


# ============ ГЛАВНОЕ ОКНО ============
class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=Palette.BG_DARK)
        self.title("RedSave Control")
        self.geometry("1100x720")
        self.minsize(900, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.api = BotAPI(API_URL, APP_TOKEN)
        self.paused = False
        self._status_running = True
        self.current_color = 5
        self.cmd_history = []
        self.history_index = -1
        self.current_tab = "dashboard"

        self._build_ui()
        self._apply_color(5)
        self._start_status_loop()
        self._poll_stats()

    # ================================================================
    # СБОРКА UI
    # ================================================================
    def _build_ui(self):
        # Сетка: сайдбар + контент
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, fg_color=Palette.BG_PANEL, corner_radius=0, width=220)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        # Логотип
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent", height=70)
        logo_frame.pack(fill="x", pady=(16, 8))
        logo_frame.pack_propagate(False)

        ctk.CTkLabel(
            logo_frame, text="◆", font=ctk.CTkFont(size=26, weight="bold"),
            text_color=Palette.ACCENT
        ).pack(side="left", padx=(20, 8))

        title_frame = ctk.CTkFrame(logo_frame, fg_color="transparent")
        title_frame.pack(side="left", fill="y")

        ctk.CTkLabel(
            title_frame, text="RedSave", font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Palette.TEXT, anchor="w"
        ).pack(anchor="w", pady=(14, 0))

        ctk.CTkLabel(
            title_frame, text="Control Panel", font=ctk.CTkFont(size=10),
            text_color=Palette.TEXT_DIM2, anchor="w"
        ).pack(anchor="w")

        # Разделитель
        ctk.CTkFrame(sidebar, fg_color=Palette.BORDER, height=1).pack(fill="x", padx=16, pady=(8, 12))

        # Кнопки навигации
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "🏠", "Дашборд"),
            ("terminal", "▶", "Терминал"),
            ("bans", "🚫", "Баны"),
            ("settings", "⚙", "Настройки"),
        ]

        for key, icon, label in nav_items:
            btn = SidebarButton(sidebar, label, icon, command=lambda k=key: self._switch_tab(k),
                                active=(key == "dashboard"))
            btn.pack(fill="x", padx=8, pady=2)
            self.nav_buttons[key] = btn

        # Внизу — статус
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

        self.status_label = ctk.CTkLabel(
            row, text="Проверка...", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Palette.TEXT
        )
        self.status_label.pack(side="left")

        self.ping_label = ctk.CTkLabel(
            inner, text="— ms", font=ctk.CTkFont(size=10),
            text_color=Palette.TEXT_DIM2, anchor="w"
        )
        self.ping_label.pack(anchor="w", pady=(4, 0))

    def _build_content(self):
        # Контейнер контента
        content = ctk.CTkFrame(self, fg_color=Palette.BG_DARK, corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        # Заголовок
        header = ctk.CTkFrame(content, fg_color=Palette.BG_PANEL, corner_radius=0, height=70)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        self.header_title = ctk.CTkLabel(
            header, text="Дашборд", font=ctk.CTkFont(size=20, weight="bold"),
            text_color=Palette.TEXT
        )
        self.header_title.pack(side="left", padx=24)

        # Кнопка паузы в хедере
        self.pause_btn = ctk.CTkButton(
            header, text="⏸  Пауза", width=120, height=36,
            fg_color=Palette.BG_CARD, hover_color=Palette.BG_CARD_HOVER,
            text_color=Palette.TEXT, corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._toggle_pause
        )
        self.pause_btn.pack(side="right", padx=(8, 24), pady=17)

        # Контент-область (меняется по табам)
        self.content_area = ctk.CTkFrame(content, fg_color="transparent")
        self.content_area.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

        # Создаём все вкладки, но показываем только активную
        self.tabs = {}
        self.tabs["dashboard"] = self._build_dashboard_tab()
        self.tabs["terminal"] = self._build_terminal_tab()
        self.tabs["bans"] = self._build_bans_tab()
        self.tabs["settings"] = self._build_settings_tab()

        self._show_tab("dashboard")

    # ================================================================
    # ВКЛАДКА: ДАШБОРД
    # ================================================================
    def _build_dashboard_tab(self):
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure((0, 1, 2), weight=1, uniform="cards")
        tab.grid_rowconfigure(2, weight=1)

        # Карточки статистики
        self.card_users = StatCard(tab, "Пользователей", "—", Palette.INFO)
        self.card_users.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 12))

        self.card_bans = StatCard(tab, "Банов", "—", Palette.ERROR)
        self.card_bans.grid(row=0, column=1, sticky="ew", padx=8, pady=(0, 12))

        self.card_ping = StatCard(tab, "Пинг API", "—", Palette.SUCCESS)
        self.card_ping.grid(row=0, column=2, sticky="ew", padx=(8, 0), pady=(0, 12))

        # Быстрые действия
        actions_card = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=12,
                                    border_width=1, border_color=Palette.BORDER)
        actions_card.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 12))

        ctk.CTkLabel(
            actions_card, text="Быстрые действия",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Palette.TEXT
        ).pack(anchor="w", padx=20, pady=(16, 12))

        btn_row = ctk.CTkFrame(actions_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 18))

        quick_buttons = [
            ("🏓  Ping", "ping", Palette.INFO),
            ("📋  Banlist", "banlist", Palette.WARNING),
            ("🔢  ID list", "idlist", Palette.ACCENT),
            ("🕒  Date", "data", Palette.ACCENT_GLOW),
            ("❓  Help", "help", Palette.TEXT_DIM),
        ]
        for text, cmd, color in quick_buttons:
            ctk.CTkButton(
                btn_row, text=text, width=110, height=40,
                fg_color=Palette.BG_PANEL, hover_color=Palette.BG_CARD_HOVER,
                text_color=color, corner_radius=10,
                font=ctk.CTkFont(size=12, weight="bold"),
                border_width=1, border_color=Palette.BORDER,
                command=lambda c=cmd: self._run_command(c)
            ).pack(side="left", padx=(0, 8))

        # Мини-лог событий
        log_card = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=12,
                                border_width=1, border_color=Palette.BORDER)
        log_card.grid(row=2, column=0, columnspan=3, sticky="nsew")

        header_row = ctk.CTkFrame(log_card, fg_color="transparent")
        header_row.pack(fill="x", padx=20, pady=(16, 8))

        ctk.CTkLabel(
            header_row, text="Последние события",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Palette.TEXT
        ).pack(side="left")

        self.mini_log = ctk.CTkTextbox(
            log_card, font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=Palette.BG_DARK, border_width=0, corner_radius=8,
            text_color=Palette.TEXT_DIM, wrap="word"
        )
        self.mini_log.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.mini_log.configure(state="disabled")

        return tab

    # ================================================================
    # ВКЛАДКА: ТЕРМИНАЛ
    # ================================================================
    def _build_terminal_tab(self):
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Панель быстрых команд
        quick_row = ctk.CTkFrame(tab, fg_color="transparent")
        quick_row.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        chips = [
            ("ping", Palette.INFO),
            ("banlist", Palette.WARNING),
            ("idlist", Palette.ACCENT),
            ("data", Palette.ACCENT_GLOW),
            ("help", Palette.TEXT_DIM),
            ("clear", Palette.ERROR),
        ]
        for cmd, color in chips:
            ctk.CTkButton(
                quick_row, text=cmd, width=80, height=30,
                fg_color=Palette.BG_CARD, hover_color=Palette.BG_CARD_HOVER,
                text_color=color, corner_radius=8,
                font=ctk.CTkFont(family="Consolas", size=12),
                border_width=1, border_color=Palette.BORDER,
                command=lambda c=cmd: self._run_command(c)
            ).pack(side="left", padx=(0, 6))

        # Терминал
        term_container = ctk.CTkFrame(
            tab, fg_color=Palette.BG_DARK, corner_radius=12,
            border_width=1, border_color=Palette.BORDER
        )
        term_container.grid(row=1, column=0, sticky="nsew")
        term_container.grid_columnconfigure(0, weight=1)
        term_container.grid_rowconfigure(0, weight=1)

        # Заголовок терминала (как в Windows Terminal)
        title_bar = ctk.CTkFrame(term_container, fg_color=Palette.BG_PANEL,
                                  corner_radius=0, height=36)
        title_bar.grid(row=0, column=0, sticky="ew")
        title_bar.grid_propagate(False)

        ctk.CTkLabel(
            title_bar, text="  ● ● ●", font=ctk.CTkFont(size=12),
            text_color=Palette.TEXT_DIM2
        ).pack(side="left", padx=8)

        self.term_title = ctk.CTkLabel(
            title_bar, text="RedSave Terminal",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=Palette.TEXT_DIM
        )
        self.term_title.pack(side="left", padx=8)

        # Область вывода
        self.terminal = ctk.CTkTextbox(
            term_container,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color=Palette.BG_DARK, border_width=0, corner_radius=0,
            text_color=Palette.TEXT, wrap="word"
        )
        self.terminal.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        # Блокируем редактирование
        for event in ("<Key>", "<<Paste>>", "<BackSpace>", "<Delete>", "<Control-v>", "<Control-V>"):
            self.terminal.bind(event, lambda e: "break")

        # Строка ввода (с префиксом как в терминале)
        input_container = ctk.CTkFrame(term_container, fg_color=Palette.BG_INPUT,
                                        corner_radius=0, height=48)
        input_container.grid(row=2, column=0, sticky="ew")
        input_container.grid_propagate(False)

        ctk.CTkLabel(
            input_container, text="❯",
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            text_color=Palette.ACCENT
        ).pack(side="left", padx=(14, 8))

        self.cmd_entry = ctk.CTkEntry(
            input_container,
            placeholder_text="Введите команду... (help — справка, ↑↓ — история, Tab — автодополнение)",
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color="transparent", border_width=0,
            text_color=Palette.TEXT,
            placeholder_text_color=Palette.TEXT_DIM2
        )
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=8)

        ctk.CTkButton(
            input_container, text="Enter ⏎", width=80, height=32,
            fg_color=Palette.ACCENT, hover_color=Palette.ACCENT_HOVER,
            text_color="#ffffff", corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_enter
        ).pack(side="right", padx=(0, 12), pady=8)

        # Обработчики клавиш
        self.cmd_entry.bind("<Return>", lambda e: self._on_enter())
        self.cmd_entry.bind("<Up>", self._history_up)
        self.cmd_entry.bind("<Down>", self._history_down)
        self.cmd_entry.bind("<Tab>", self._autocomplete)
        self.cmd_entry.focus_set()

        # Приветствие
        self._term_write("RedSave Terminal v2.0", "header")
        self._term_write(f"API: {API_URL}", "info")
        self._term_write("Введите 'help' для списка команд", "info")
        self._term_write("")

        return tab

    # ================================================================
    # ВКЛАДКА: БАНЫ
    # ================================================================
    def _build_bans_tab(self):
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Панель действий
        actions = ctk.CTkFrame(tab, fg_color="transparent")
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkButton(
            actions, text="🔄  Обновить", width=120, height=36,
            fg_color=Palette.BG_CARD, hover_color=Palette.BG_CARD_HOVER,
            text_color=Palette.TEXT, corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            border_width=1, border_color=Palette.BORDER,
            command=self._load_bans
        ).pack(side="left")

        # Список банов
        self.bans_container = ctk.CTkScrollableFrame(
            tab, fg_color=Palette.BG_CARD, corner_radius=12,
            border_width=1, border_color=Palette.BORDER
        )
        self.bans_container.grid(row=1, column=0, sticky="nsew")
        self.bans_container.grid_columnconfigure(0, weight=1)

        self._bans_placeholder = ctk.CTkLabel(
            self.bans_container, text="Нажмите «Обновить», чтобы загрузить список",
            font=ctk.CTkFont(size=13), text_color=Palette.TEXT_DIM2
        )
        self._bans_placeholder.pack(pady=60)

        return tab

    # ================================================================
    # ВКЛАДКА: НАСТРОЙКИ
    # ================================================================
    def _build_settings_tab(self):
        tab = ctk.CTkFrame(self.content_area, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        # Инфо о подключении
        info = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=12,
                             border_width=1, border_color=Palette.BORDER)
        info.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        ctk.CTkLabel(
            info, text="Подключение",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=Palette.TEXT
        ).pack(anchor="w", padx=20, pady=(16, 12))

        for label, value in [("API URL", API_URL), ("Token", APP_TOKEN)]:
            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(row, text=f"{label}:", width=100, anchor="w",
                          font=ctk.CTkFont(size=12), text_color=Palette.TEXT_DIM).pack(side="left")
            ctk.CTkLabel(row, text=value, anchor="w",
                          font=ctk.CTkFont(family="Consolas", size=12),
                          text_color=Palette.TEXT).pack(side="left")

        ctk.CTkFrame(info, fg_color="transparent", height=8).pack()

        # Цвета терминала
        colors = ctk.CTkFrame(tab, fg_color=Palette.BG_CARD, corner_radius=12,
                                border_width=1, border_color=Palette.BORDER)
        colors.grid(row=1, column=0, sticky="ew")

        ctk.CTkLabel(
            colors, text="Цвет терминала",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=Palette.TEXT
        ).pack(anchor="w", padx=20, pady=(16, 12))

        color_row = ctk.CTkFrame(colors, fg_color="transparent")
        color_row.pack(fill="x", padx=20, pady=(0, 20))

        for num in range(1, 9):
            bg, fg, _, name = COLOR_THEMES[num]
            btn = ctk.CTkButton(
                color_row, text="", width=36, height=36,
                fg_color=fg, hover_color=bg,
                corner_radius=8, border_width=2,
                border_color=Palette.BORDER,
                command=lambda n=num: self._set_color_from_ui(n)
            )
            btn.pack(side="left", padx=4)
            btn._color_num = num  # запоминаем для обновления активного

        return tab

    # ================================================================
    # ПЕРЕКЛЮЧЕНИЕ ВКЛАДОК
    # ================================================================
    def _switch_tab(self, key):
        if key == self.current_tab:
            return
        self.current_tab = key
        for k, btn in self.nav_buttons.items():
            btn._set_active(k == key)
        self._show_tab(key)

        titles = {
            "dashboard": "Дашборд",
            "terminal": "Терминал",
            "bans": "Баны",
            "settings": "Настройки",
        }
        self.header_title.configure(text=titles.get(key, ""))

        if key == "bans":
            self._load_bans()

    def _show_tab(self, key):
        for k, tab in self.tabs.items():
            if k == key:
                tab.grid(row=0, column=0, sticky="nsew")
            else:
                tab.grid_forget()

    # ================================================================
    # ЦВЕТА
    # ================================================================
    def _apply_color(self, num):
        if num not in COLOR_THEMES:
            return False
        self.current_color = num
        bg, fg, dim, name = COLOR_THEMES[num]
        try:
            self.terminal.configure(fg_color=bg, text_color=fg)
            self.term_title.configure(text=f"RedSave Terminal — {name}")
        except Exception:
            pass
        return True

    def _set_color_from_ui(self, num):
        self._apply_color(num)
        self._toast(f"Цвет изменён: {COLOR_THEMES[num][3]}", Palette.SUCCESS)

    # ================================================================
    # ТЕРМИНАЛ — запись
    # ================================================================
    def _term_write(self, text, kind="normal"):
        self.terminal.configure(state="normal")
        tag = f"t_{kind}_{int(time.time()*1000)}_{id(text)}"
        self.terminal.insert("end", text + "\n", tag)

        tag_colors = {
            "cmd": Palette.INFO,
            "ok": Palette.SUCCESS,
            "err": Palette.ERROR,
            "warn": Palette.WARNING,
            "info": Palette.TEXT_DIM2,
            "header": Palette.ACCENT_GLOW,
        }
        if kind in tag_colors:
            self.terminal.tag_config(tag, foreground=tag_colors[kind])
        self.terminal.see("end")
        self.terminal.configure(state="disabled")

    # ================================================================
    # ТЕРМИНАЛ — ввод
    # ================================================================
    def _on_enter(self):
        cmd = self.cmd_entry.get().strip()
        self.cmd_entry.delete(0, "end")
        if not cmd:
            return
        if not self.cmd_history or self.cmd_history[-1] != cmd:
            self.cmd_history.append(cmd)
        self.history_index = len(self.cmd_history)
        self._run_command(cmd)

    def _history_up(self, event):
        if not self.cmd_history:
            return "break"
        self.history_index = max(0, self.history_index - 1)
        self.cmd_entry.delete(0, "end")
        self.cmd_entry.insert(0, self.cmd_history[self.history_index])
        return "break"

    def _history_down(self, event):
        if not self.cmd_history:
            return "break"
        self.history_index = min(len(self.cmd_history), self.history_index + 1)
        self.cmd_entry.delete(0, "end")
        if self.history_index < len(self.cmd_history):
            self.cmd_entry.insert(0, self.cmd_history[self.history_index])
        return "break"

    def _autocomplete(self, event):
        current = self.cmd_entry.get().strip().lower()
        all_cmds = ["ping", "ban", "unban", "banlist", "checkban",
                    "idlist", "ai", "data", "help", "color", "clear"]
        matches = [c for c in all_cmds if c.startswith(current) and current]
        if len(matches) == 1:
            self.cmd_entry.delete(0, "end")
            self.cmd_entry.insert(0, matches[0] + " ")
        elif matches:
            self._term_write("  ".join(matches), "info")
        return "break"

    # ================================================================
    # ЗАПУСК КОМАНД
    # ================================================================
    def _run_command(self, raw):
        low = raw.strip().lower()

        if low == "clear":
            self.terminal.configure(state="normal")
            self.terminal.delete("1.0", "end")
            self.terminal.configure(state="disabled")
            return

        if low == "color list":
            self._term_write(f"❯ {raw}", "cmd")
            for n, (_, _, _, name) in COLOR_THEMES.items():
                marker = " ←" if n == self.current_color else ""
                self._term_write(f"  {n} — {name}{marker}", "info")
            self._term_write("")
            return

        if low.startswith("color"):
            parts = low.split()
            if len(parts) == 2 and parts[1].isdigit():
                n = int(parts[1])
                self._term_write(f"❯ {raw}", "cmd")
                if self._apply_color(n):
                    self._term_write(f"✅ Цвет изменён: {COLOR_THEMES[n][3]}", "ok")
                else:
                    self._term_write(f"❌ Неверный цвет. Доступно 1-8", "err")
                self._term_write("")
                return

        # Всё остальное — на сервер
        self._term_write(f"❯ {raw}", "cmd")

        def task():
            data = self.api.command(raw)
            if "error" in data:
                self.after(0, lambda: self._term_write(f"❌ {data['error']}", "err"))
                self.after(0, lambda: self._mini_log(f"❌ {raw}: {data['error']}", "err"))
            else:
                result = data.get("result", "")
                for line in result.split("\n"):
                    self.after(0, lambda l=line: self._term_write(l, "normal"))
                self.after(0, lambda: self._mini_log(f"✓ {raw}", "ok"))
            self.after(0, lambda: self._term_write(""))
        threading.Thread(target=task, daemon=True).start()

    # ================================================================
    # МИНИ-ЛОГ на дашборде
    # ================================================================
    def _mini_log(self, text, kind="normal"):
        if not hasattr(self, "mini_log") or not self.mini_log.winfo_exists():
            return
        self.mini_log.configure(state="normal")
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {text}\n"
        tag = f"m_{kind}_{int(time.time()*1000)}_{id(text)}"
        self.mini_log.insert("end", line, tag)
        tag_colors = {
            "ok": Palette.SUCCESS,
            "err": Palette.ERROR,
            "info": Palette.TEXT_DIM2,
        }
        if kind in tag_colors:
            self.mini_log.tag_config(tag, foreground=tag_colors[kind])
        # храним только последние 200 строк
        lines = int(self.mini_log.index("end-1c").split(".")[0])
        if lines > 200:
            self.mini_log.delete("1.0", f"{lines-200}.0")
        self.mini_log.see("end")
        self.mini_log.configure(state="disabled")

    # ================================================================
    # ЗАГРУЗКА БАНОВ
    # ================================================================
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
                          text_color=Palette.ERROR, font=ctk.CTkFont(size=13)
                          ).pack(pady=60)
            return

        result = data.get("result", "")
        if "пуст" in result.lower():
            ctk.CTkLabel(self.bans_container, text="📋 Бан-лист пуст",
                          text_color=Palette.TEXT_DIM2, font=ctk.CTkFont(size=13)
                          ).pack(pady=60)
            return

        # Парсим строки
        lines = [l.strip() for l in result.split("\n") if l.strip() and not l.startswith("📋")]

        for line in lines:
            row = ctk.CTkFrame(self.bans_container, fg_color=Palette.BG_PANEL, corner_radius=8,
                                border_width=1, border_color=Palette.BORDER)
            row.pack(fill="x", padx=4, pady=3)
            ctk.CTkLabel(
                row, text=line, anchor="w",
                font=ctk.CTkFont(family="Consolas", size=12),
                text_color=Palette.TEXT
            ).pack(fill="x", padx=14, pady=10)

    # ================================================================
    # СТАТУС / ПИНГ
    # ================================================================
    def _set_status(self, online, ping=None, paused=False):
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
                        # карточки
                        users = data.get("users_count", 0)
                        bans = data.get("bans_count", 0)
                        self.after(0, lambda u=users: self.card_users.set_value(str(u)))
                        self.after(0, lambda b=bans: self.card_bans.set_value(str(b)))
                        p = self.api.ping()
                        if "error" not in p:
                            ping_val = p.get("api_ping")
                            paused_val = self.paused
                            self.after(0, lambda pv=ping_val, pav=paused_val: self._set_status(True, pv, pav))
                except Exception:
                    pass
                time.sleep(10)
        threading.Thread(target=loop, daemon=True).start()

    def _poll_stats(self):
        # не используется отдельно, всё в _start_status_loop
        pass

    def _update_pause_button(self):
        if self.paused:
            self.pause_btn.configure(
                text="▶  Возобновить",
                fg_color=Palette.SUCCESS, hover_color="#16a34a",
                text_color="#ffffff"
            )
        else:
            self.pause_btn.configure(
                text="⏸  Пауза",
                fg_color=Palette.BG_CARD, hover_color=Palette.BG_CARD_HOVER,
                text_color=Palette.TEXT
            )

    def _toggle_pause(self):
        def task():
            if self.paused:
                data = self.api.resume()
                if "error" not in data:
                    self.paused = False
                    self.after(0, lambda: self._term_write("▶ Бот возобновлён", "ok"))
                    self.after(0, lambda: self._mini_log("▶ Бот возобновлён", "ok"))
            else:
                data = self.api.pause()
                if "error" not in data:
                    self.paused = True
                    self.after(0, lambda: self._term_write("⏸ Бот поставлен на паузу", "warn"))
                    self.after(0, lambda: self._mini_log("⏸ Пауза", "info"))
            self.after(0, self._update_pause_button)
        threading.Thread(target=task, daemon=True).start()

    # ================================================================
    # TOAST (простое уведомление в терминал)
    # ================================================================
    def _toast(self, text, color=Palette.SUCCESS):
        self._term_write(f"• {text}", "ok")

    def on_close(self):
        self._status_running = False
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
