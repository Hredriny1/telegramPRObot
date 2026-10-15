import customtkinter as ctk
import requests
import threading
import time
import json
import os

# ============ КОНФИГ ============
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "api_url": "https://telegramprobot.relaxdev.ru",
    "token": "change-me-secret-token",
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

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
        self.geometry("850x650")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.config_data = load_config()
        self.api = BotAPI(self.config_data["api_url"], self.config_data["token"])
        self.paused = False
        self._status_running = True

        self._build_ui()
        self._start_status_loop()

    def _build_ui(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=10)

        self.status_dot = ctk.CTkLabel(top, text="●", font=("Arial", 22), text_color="gray")
        self.status_dot.pack(side="left", padx=(10, 5))

        self.status_label = ctk.CTkLabel(top, text="Проверка...", font=("Arial", 14))
        self.status_label.pack(side="left")

        self.ping_label = ctk.CTkLabel(top, text="", font=("Arial", 12))
        self.ping_label.pack(side="right", padx=10)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(btn_frame, text="🏓 Пинг", width=110, command=self._do_ping).pack(side="left", padx=5)
        self.pause_btn = ctk.CTkButton(btn_frame, text="⏸ Пауза", width=130, command=self._toggle_pause)
        self.pause_btn.pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="📋 Баны", width=110, command=self._show_bans).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🗑 Очистить лог", width=130, command=self._clear_log).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="⚙ Настройки", width=110, command=self._open_settings).pack(side="right", padx=5)

        chips_label = ctk.CTkLabel(self, text="Быстрые команды:", font=("Arial", 12), anchor="w")
        chips_label.pack(fill="x", padx=15, pady=(10, 0))

        chips_frame = ctk.CTkFrame(self)
        chips_frame.pack(fill="x", padx=10, pady=5)

        cmds = [".ping", ".me", ".id", ".idlist", ".banlist", ".data", ".business"]
        for c in cmds:
            ctk.CTkButton(chips_frame, text=c, width=90, height=28,
                          command=lambda cmd=c: self._send_command(cmd)).pack(side="left", padx=3, pady=5)

        input_frame = ctk.CTkFrame(self)
        input_frame.pack(fill="x", padx=10, pady=5)

        self.cmd_entry = ctk.CTkEntry(input_frame, placeholder_text="Введите команду (.ping, .ban 123, .ai ...)")
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(0, 5), pady=5)
        self.cmd_entry.bind("<Return>", lambda e: self._send_command())

        ctk.CTkButton(input_frame, text="▶ Отправить", width=120, command=self._send_command).pack(side="right", padx=(5, 0), pady=5)

        log_label = ctk.CTkLabel(self, text="Лог:", font=("Arial", 12), anchor="w")
        log_label.pack(fill="x", padx=15, pady=(10, 0))

        self.log_box = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        self.log_box.configure(state="normal")

    def _log(self, text):
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{timestamp}] {text}\n")
        self.log_box.see("end")

    def _clear_log(self):
        self.log_box.delete("1.0", "end")

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

    def _do_ping(self):
        self._log("> Измерение пинга...")
        def task():
            data = self.api.ping()
            if "error" in data:
                self._log(f"❌ {data['error']}")
            else:
                self._log(f"✅ API: {data.get('api_ping')}ms | TCP: {data.get('tcp_ping')}ms | {data.get('status')}")
        threading.Thread(target=task, daemon=True).start()

    def _toggle_pause(self):
        def task():
            if self.paused:
                data = self.api.resume()
                if "error" not in data:
                    self.paused = False
                    self._log("▶ Бот возобновлён")
            else:
                data = self.api.pause()
                if "error" not in data:
                    self.paused = True
                    self._log("⏸ Бот поставлен на паузу")
            self.after(0, self._update_pause_button)
        threading.Thread(target=task, daemon=True).start()

    def _send_command(self, cmd=None):
        if cmd is None:
            cmd = self.cmd_entry.get().strip()
            self.cmd_entry.delete(0, "end")
        if not cmd:
            return
        self._log(f"> {cmd}")

        def task():
            data = self.api.command(cmd)
            if "error" in data:
                self._log(f"❌ {data['error']}")
            else:
                result = data.get("result", "")
                for line in result.split("\n"):
                    self._log(f"   {line}")
        threading.Thread(target=task, daemon=True).start()

    def _show_bans(self):
        def task():
            data = self.api.banlist()
            if "error" in data:
                self._log(f"❌ {data['error']}")
                return
            bans = data.get("bans", [])
            if not bans:
                self._log("📋 Бан-лист пуст")
                return
            self._log(f"📋 Баны ({len(bans)}):")
            for b in bans[:30]:
                self._log(f"   • ID: {b.get('id')} | @{b.get('username', '—')} | {b.get('time', 'forever')} | {b.get('reason', '')}")
        threading.Thread(target=task, daemon=True).start()

    def _open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Настройки")
        win.geometry("450x280")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="API URL:", font=("Arial", 13)).pack(pady=(20, 5))
        url_entry = ctk.CTkEntry(win, width=380)
        url_entry.insert(0, self.config_data["api_url"])
        url_entry.pack()

        ctk.CTkLabel(win, text="APP_TOKEN:", font=("Arial", 13)).pack(pady=(15, 5))
        token_entry = ctk.CTkEntry(win, width=380, show="•")
        token_entry.insert(0, self.config_data["token"])
        token_entry.pack()

        def save():
            self.config_data["api_url"] = url_entry.get().strip()
            self.config_data["token"] = token_entry.get().strip()
            save_config(self.config_data)
            self.api = BotAPI(self.config_data["api_url"], self.config_data["token"])
            self._log("✅ Настройки сохранены")
            win.destroy()

        ctk.CTkButton(win, text="Сохранить", width=200, command=save).pack(pady=25)

    def on_close(self):
        self._status_running = False
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
