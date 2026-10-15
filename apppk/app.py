import customtkinter as ctk
import requests
import threading
import time

# ============ КОНФИГ ============
API_URL = "https://telegramprobot.relaxdev.ru/webhook"
APP_TOKEN = "871410danil"

# Цвета терминала: (фон, текст)
COLOR_THEMES = {
    1: ("#001a33", "#4da6ff"),  # синий
    2: ("#001a00", "#33ff33"),  # зелёный
    3: ("#1a0000", "#ff4d4d"),  # красный
    4: ("#1a0f00", "#ffa64d"),  # оранжевый
    5: ("#0a0a0a", "#e0e0e0"),  # обычный
}

COLOR_NAMES = {
    1: "Синий",
    2: "Зелёный",
    3: "Красный",
    4: "Оранжевый",
    5: "Обычный (белый)",
}

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
            if e.response.status_code == 401:
                return {"error": "Неверный токен"}
            if e.response.status_code == 423:
                return {"error": "Бот на паузе"}
            if e.response.status_code == 404:
                return {"error": "404 — RelaxDev не проксирует этот путь"}
            return {"error": f"HTTP {e.response.status_code}"}
        except requests.exceptions.ConnectionError:
            return {"error": "Нет соединения с ботом"}
        except requests.exceptions.Timeout:
            return {"error": "Таймаут"}
        except Exception as e:
            return {"error": str(e)}

    def ping(self):
        return self._post("ping")

    def status(self):
        return self._post("status")

    def command(self, cmd):
        return self._post("command", {"command": cmd})

    def pause(self):
        return self._post("pause")

    def resume(self):
        return self._post("resume")

    def banlist(self):
        return self._post("banlist")

# ============ GUI ============
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("RedSave Control")
        self.geometry("900x680")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.api = BotAPI(API_URL, APP_TOKEN)
        self.paused = False
        self._status_running = True
        self.current_color = 5

        self._build_ui()
        self._apply_color(5)
        self._start_status_loop()

    def _build_ui(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=(10, 5))

        self.status_dot = ctk.CTkLabel(top, text="●", font=("Arial", 22), text_color="gray")
        self.status_dot.pack(side="left", padx=(10, 5))

        self.status_label = ctk.CTkLabel(top, text="Проверка...", font=("Arial", 14))
        self.status_label.pack(side="left")

        self.ping_label = ctk.CTkLabel(top, text="", font=("Arial", 12))
        self.ping_label.pack(side="right", padx=10)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(btn_frame, text="🏓 Пинг", width=100, command=lambda: self._send_command("ping")).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="📋 Баны", width=100, command=lambda: self._send_command("banlist")).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="🔢 ID", width=100, command=lambda: self._send_command("idlist")).pack(side="left", padx=4)
        self.pause_btn = ctk.CTkButton(btn_frame, text="⏸ Пауза", width=120, command=self._toggle_pause)
        self.pause_btn.pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="❓ help", width=80, command=lambda: self._send_command("help")).pack(side="right", padx=4)
        ctk.CTkButton(btn_frame, text="🗑 clear", width=80, command=self._clear_log).pack(side="right", padx=4)

        input_frame = ctk.CTkFrame(self)
        input_frame.pack(fill="x", padx=10, pady=5)

        self.cmd_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Введите команду (ping, ban 123, ai вопрос, color 2 ...)",
            font=("Consolas", 13)
        )
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(0, 5), pady=5)
        self.cmd_entry.bind("<Return>", lambda e: self._on_enter())

        ctk.CTkButton(input_frame, text="▶ Отправить", width=120, command=self._on_enter).pack(side="right", padx=(5, 0), pady=5)

        term_label = ctk.CTkLabel(self, text="Терминал:", font=("Arial", 12), anchor="w")
        term_label.pack(fill="x", padx=15, pady=(10, 0))

        self.terminal = ctk.CTkTextbox(self, font=("Consolas", 13), wrap="word")
        self.terminal.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        # Только для чтения
        self.terminal.bind("<Key>", lambda e: "break")
        self.terminal.bind("<<Paste>>", lambda e: "break")
        self.terminal.bind("<BackSpace>", lambda e: "break")
        self.terminal.bind("<Delete>", lambda e: "break")

        self._term_line("RedSave Control", "header")
        self._term_line(f"API: {API_URL}")
        self._term_line("Введите help для списка команд")
        self._term_line("")

    def _apply_color(self, color_num):
        if color_num not in COLOR_THEMES:
            return False
        self.current_color = color_num
        bg, fg = COLOR_THEMES[color_num]
        try:
            self.terminal.configure(
                fg_color=bg,
                text_color=fg,
                border_color=fg,
            )
        except Exception:
            pass
        return True

    def _term_line(self, text, kind="normal"):
        tag = f"tag_{kind}_{int(time.time()*1000)}_{id(text)}"
        self.terminal.insert("end", text + "\n", tag)

        if kind == "cmd":
            self.terminal.tag_config(tag, foreground="#66ccff")
        elif kind == "ok":
            self.terminal.tag_config(tag, foreground="#33ff33")
        elif kind == "err":
            self.terminal.tag_config(tag, foreground="#ff4d4d")
        elif kind == "warn":
            self.terminal.tag_config(tag, foreground="#ffaa33")
        elif kind == "info":
            self.terminal.tag_config(tag, foreground="#aaaaaa")
        elif kind == "header":
            self.terminal.tag_config(tag, foreground="#ff66cc", underline=True)

        self.terminal.see("end")

    def _clear_log(self):
        self.terminal.delete("1.0", "end")

    def _set_status(self, online, ping=None, paused=False):
        if paused:
            self.status_dot.configure(text_color="orange")
            self.status_label.configure(text="На паузе")
        elif online:
            self.status_dot.configure(text_color="green")
            self.status_label.configure(text="Онлайн")
        else:
            self.status_dot.configure(text_color="red")
            self.status_label.configure(text="Офлайн")
        self.ping_label.configure(text=f"{ping} ms" if ping is not None else "")

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
                        p = self.api.ping()
                        if "error" not in p:
                            ping_val = p.get("api_ping")
                            paused_val = self.paused
                            self.after(0, lambda pv=ping_val, pav=paused_val: self._set_status(True, pv, pav))
                except Exception:
                    pass
                time.sleep(10)
        threading.Thread(target=loop, daemon=True).start()

    def _update_pause_button(self):
        if self.paused:
            self.pause_btn.configure(text="▶ Возобновить")
        else:
            self.pause_btn.configure(text="⏸ Пауза")

    def _toggle_pause(self):
        def task():
            if self.paused:
                data = self.api.resume()
                if "error" not in data:
                    self.paused = False
                    self.after(0, lambda: self._term_line("▶ Бот возобновлён", "ok"))
            else:
                data = self.api.pause()
                if "error" not in data:
                    self.paused = True
                    self.after(0, lambda: self._term_line("⏸ Бот поставлен на паузу", "warn"))
            self.after(0, self._update_pause_button)
        threading.Thread(target=task, daemon=True).start()

    def _on_enter(self):
        cmd = self.cmd_entry.get().strip()
        self.cmd_entry.delete(0, "end")
        if not cmd:
            return
        self._run_command(cmd)

    def _run_command(self, raw: str):
        low = raw.strip().lower()

        # color list
        if low == "color list":
            self._term_line("> color list", "cmd")
            self._term_line("Доступные цвета:", "info")
            for num, name in COLOR_NAMES.items():
                marker = " ← текущий" if num == self.current_color else ""
                self._term_line(f"  {num} — {name}{marker}", "info")
            self._term_line("")
            return

        # color N
        if low.startswith("color"):
            parts = low.split()
            if len(parts) == 2 and parts[1].isdigit():
                num = int(parts[1])
                self._term_line(f"> color {num}", "cmd")
                if num in COLOR_THEMES:
                    self._apply_color(num)
                    self._term_line(f"✅ Цвет изменён: {COLOR_NAMES[num]}", "ok")
                else:
                    self._term_line(f"❌ Неверный цвет. Доступно: 1-5 (color list)", "err")
                self._term_line("")
                return

        # clear
        if low == "clear":
            self._clear_log()
            return

        # всё остальное — на сервер
        self._term_line(f"> {raw}", "cmd")

        def task():
            data = self.api.command(raw)
            if "error" in data:
                self.after(0, lambda: self._term_line(f"❌ {data['error']}", "err"))
            else:
                result = data.get("result", "")
                for line in result.split("\n"):
                    self.after(0, lambda l=line: self._term_line(l, "normal"))
            self.after(0, lambda: self._term_line("", "normal"))
        threading.Thread(target=task, daemon=True).start()

    def _send_command(self, cmd):
        self._run_command(cmd)

    def on_close(self):
        self._status_running = False
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
