import asyncio
import logging
import os
import sys
import time
import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import OrderedDict

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.types import Message, BusinessConnection, BusinessMessagesDeleted
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ============================================================
# КОНФИГ
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID_RAW = os.getenv("OWNER_ID", "").strip()
VIRUSTOTAL_API_KEY = os.getenv("API", "").strip()
VIRUSTOTAL_PROXY = os.getenv("VT_PROXY", "").strip()

TELEGRAM_PROXY_URL = "https://lively-brook-2aa0tg-proxy.kichuk2027.workers.dev"
SITE_API_URL = os.getenv("SITE_API_URL", "").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = "openai/gpt-oss-120b"

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен.")
    raise SystemExit(1)
if not OWNER_ID_RAW:
    logger.error("❌ OWNER_ID не установлен.")
    raise SystemExit(1)

try:
    OWNER_ID = int(OWNER_ID_RAW)
except ValueError:
    logger.error("❌ OWNER_ID должен быть целым числом.")
    raise SystemExit(1)

logger.info("=" * 70)
logger.info("🤖 Запуск Telegram бота")
logger.info("OWNER_ID: %s", OWNER_ID)
logger.info("SITE_API_URL: %s", SITE_API_URL if SITE_API_URL else "не задан")
logger.info("GROQ_API_KEY: %s", "установлен" if GROQ_API_KEY else "❌ НЕ УСТАНОВЛЕН")
logger.info("=" * 70)

# ============================================================
# ХРАНИЛИЩА
# ============================================================

MESSAGE_STORAGE = OrderedDict()
MAX_STORAGE_SIZE = 2000
MUTE_STORAGE = {}
NOMUTE_STORAGE = {}
PENDING_SEND = {}
ANTIMAT_STORAGE = {}
LAST_BUSINESS_CONNECTION_ID = None
USER_DATABASE = {}
BAN_CACHE = {}
BAN_CACHE_TTL = 60
TRACE_BUFFER = {}  # request_id -> list of steps (последние 100)

BAD_WORDS = [
    "бля", "блядь", "блять", "сука", "хуй", "хуя", "пизда", "ебал", "ебать",
    "мудак", "пидор", "шлюха", "тварь", "дебил", "идиот", "кретин", "даун",
    "чмо", "уёбок", "дрочь", "манда",
]

def store_message(chat_id, message_id, text, sender_id):
    key = (chat_id, message_id)
    MESSAGE_STORAGE[key] = {"text": text, "sender_id": sender_id}
    while len(MESSAGE_STORAGE) > MAX_STORAGE_SIZE:
        MESSAGE_STORAGE.popitem(last=False)

def get_stored_message(chat_id, message_id):
    return MESSAGE_STORAGE.get((chat_id, message_id))

def is_muted(chat_id):
    if chat_id not in MUTE_STORAGE:
        return False
    mi = MUTE_STORAGE[chat_id]
    if mi["until"] is None:
        return True
    if time.time() < mi["until"]:
        return True
    del MUTE_STORAGE[chat_id]
    return False

def set_mute(chat_id, minutes):
    if minutes is None:
        MUTE_STORAGE[chat_id] = {"until": None}
    else:
        MUTE_STORAGE[chat_id] = {"until": time.time() + minutes * 60}

def clear_mute(chat_id):
    MUTE_STORAGE.pop(chat_id, None)

def is_antimat(chat_id):
    return ANTIMAT_STORAGE.get(chat_id, False)

def set_antimat(chat_id, enabled):
    ANTIMAT_STORAGE[chat_id] = enabled

def contains_bad_words(text):
    if not text:
        return False
    words = re.findall(r'[а-яё]+', text.lower())
    return any(bad in word for word in words for bad in BAD_WORDS)

def parse_command(text):
    text = text.strip()
    to_dm = False
    if text.endswith(" -s"):
        to_dm = True
        text = text[:-3].strip()
    parts = text.split(maxsplit=1)
    cmd = parts[0] if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""
    return cmd, arg, to_dm

# ============================================================
# ТРАССИРОВКА
# ============================================================

def add_trace_step(request_id: str, step: str):
    """Добавляет шаг в трассировку запроса."""
    if not request_id:
        return
    if request_id not in TRACE_BUFFER:
        TRACE_BUFFER[request_id] = []
    TRACE_BUFFER[request_id].append({
        "step": step,
        "timestamp": int(time.time() * 1000),
    })
    # Ограничиваем буфер
    while len(TRACE_BUFFER) > 100:
        oldest = next(iter(TRACE_BUFFER))
        del TRACE_BUFFER[oldest]

# ============================================================
# API ДЛЯ САЙТА
# ============================================================

async def api_check_ban(user_id=None, username=None):
    if not SITE_API_URL:
        return None
    if user_id and user_id in BAN_CACHE:
        cached = BAN_CACHE[user_id]
        if time.time() - cached["cached_at"] < BAN_CACHE_TTL:
            return cached
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{SITE_API_URL}/bans",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                json={"action": "check", "ban": {"id": user_id, "username": username}},
                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ban = data.get("ban")
                    if ban and user_id:
                        BAN_CACHE[user_id] = {**ban, "cached_at": time.time()}
                    return ban
                return None
    except Exception as e:
        logger.error("❌ check_ban: %s", e)
        return None

async def api_add_ban(user_id, username, time_str, reason):
    if not SITE_API_URL:
        return False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{SITE_API_URL}/bans",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                json={"action": "add", "ban": {"id": user_id, "username": username, "time": time_str, "reason": reason, "banned_at": int(time.time())}},
                timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    BAN_CACHE.pop(user_id, None)
                    return True
                return False
    except Exception as e:
        logger.error("❌ add_ban: %s", e)
        return False

async def api_remove_ban(user_id, username):
    if not SITE_API_URL:
        return False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{SITE_API_URL}/bans",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                json={"action": "remove", "ban": {"id": user_id, "username": username}},
                timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    BAN_CACHE.pop(user_id, None)
                    return True
                return False
    except Exception as e:
        logger.error("❌ remove_ban: %s", e)
        return False

async def api_list_bans():
    if not SITE_API_URL:
        return []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{SITE_API_URL}/bans",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                json={"action": "list"},
                timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("bans", [])
                return []
    except Exception as e:
        logger.error("❌ list_bans: %s", e)
        return []

async def api_send_heartbeat(ping=None, healthcheck_ok=True, api_ping=None, site_ping=None):
    """Отправляет heartbeat с полным статусом здоровья."""
    if not SITE_API_URL:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{SITE_API_URL}/bot",
                headers={"Content-Type": "application/json"},
                json={
                    "action": "heartbeat",
                    "data": {
                        "ping": ping,
                        "healthcheck_ok": healthcheck_ok,
                        "api_ping": api_ping,
                        "site_ping": site_ping,
                        "last_heartbeat": int(time.time() * 1000),
                    }
                },
                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                pass
    except Exception as e:
        logger.warning("⚠️ heartbeat: %s", e)

async def api_send_alert(alert_type: str, message: str):
    """Отправляет алерт на сайт (сайт решит, куда его переслать)."""
    if not SITE_API_URL:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{SITE_API_URL}/alerts",
                headers={"Content-Type": "application/json", "X-Admin-Password": ADMIN_PASSWORD},
                json={"type": alert_type, "message": message, "timestamp": int(time.time() * 1000)},
                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                pass
    except Exception:
        pass

async def api_get_pending_command():
    if not SITE_API_URL:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{SITE_API_URL}/pending",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("command")
                return None
    except Exception:
        return None

async def api_set_command_result(result, status="ok"):
    if not SITE_API_URL:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{SITE_API_URL}/pending",
                headers={"Content-Type": "application/json", "X-Admin-Password": ADMIN_PASSWORD},
                json={"result": result, "status": status},
                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                pass
    except Exception:
        pass

async def api_send_trace(request_id: str, trace_data: list):
    """Отправляет трассировку на сайт."""
    if not SITE_API_URL:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{SITE_API_URL}/trace",
                headers={"Content-Type": "application/json", "X-Admin-Password": ADMIN_PASSWORD},
                json={"request_id": request_id, "steps": trace_data, "timestamp": int(time.time() * 1000)},
                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                pass
    except Exception:
        pass

# ============================================================
# HEARTBEAT + HEALTHCHECK
# ============================================================

async def heartbeat_task(bot: Bot):
    """Каждые 30 секунд: heartbeat + healthcheck + проверка алертов."""
    last_alert_time = 0
    consecutive_failures = 0

    while True:
        try:
            # 1. API ping
            start = time.time()
            await bot.get_me()
            api_ping = int((time.time() - start) * 1000)

            # 2. Site ping
            site_ping = None
            if SITE_API_URL:
                try:
                    start = time.time()
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{SITE_API_URL}/status",
                            headers={"X-Admin-Password": ADMIN_PASSWORD},
                            timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            pass
                    site_ping = int((time.time() - start) * 1000)
                except Exception:
                    site_ping = -1

            healthcheck_ok = api_ping < 3000 and (site_ping is None or site_ping < 3000)

            if healthcheck_ok:
                consecutive_failures = 0
            else:
                consecutive_failures += 1

            # 3. Отправляем heartbeat
            await api_send_heartbeat(
                ping=api_ping,
                healthcheck_ok=healthcheck_ok,
                api_ping=api_ping,
                site_ping=site_ping,
            )

            # 4. Алерт при деградации
            if consecutive_failures >= 2 and time.time() - last_alert_time > 600:
                await api_send_alert(
                    "degradation",
                    f"⚠️ Бот деградирует: API ping {api_ping}ms, Site ping {site_ping}ms"
                )
                last_alert_time = time.time()

        except Exception as e:
            logger.warning("⚠️ heartbeat error: %s", e)

        await asyncio.sleep(30)

# ============================================================
# POLL КОМАНД
# ============================================================

async def command_poll_task(bot: Bot):
    while True:
        try:
            cmd = await api_get_pending_command()
            if cmd:
                logger.info("📥 Команда из консоли: %s", cmd)
                result = await execute_site_command(cmd, bot)
                await api_set_command_result(result, status="ok")
        except Exception as e:
            logger.error("❌ command_poll: %s", e)
        await asyncio.sleep(5)

async def execute_site_command(cmd: str, bot: Bot) -> str:
    cmd = cmd.strip()
    if not cmd.startswith("."):
        return f"❌ Неизвестная команда: {cmd}"

    parts = cmd.split(maxsplit=1)
    command = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    try:
        if command == ".ping":
            start = time.time()
            await bot.get_me()
            ping = int((time.time() - start) * 1000)
            return f"✅ Ping API: {ping}ms"

        elif command == ".ban":
            p = arg.split(maxsplit=2)
            if len(p) < 1:
                return "❌ .ban (ID) (time) (reason)"
            target = p[0]
            ts = p[1] if len(p) > 1 else "forever"
            reason = p[2] if len(p) > 2 else "не указана"
            tid = None
            try:
                tid = int(target)
            except ValueError:
                for uid, info in USER_DATABASE.items():
                    if info["username"] == target.lstrip("@"):
                        tid = uid
                        break
            if not tid:
                return f"❌ Не найден {target}"
            ok = await api_add_ban(tid, target.lstrip("@"), ts, reason)
            return f"✅ Забанен {tid}" if ok else "❌ Ошибка"

        elif command == ".unban":
            target = arg.strip().lstrip("@")
            tid = 0
            try:
                tid = int(target)
            except ValueError:
                for uid, info in USER_DATABASE.items():
                    if info["username"] == target:
                        tid = uid
                        break
            ok = await api_remove_ban(tid, target)
            return f"✅ Разбанен {tid}" if ok else "❌ Ошибка"

        elif command == ".banlist":
            bans = await api_list_bans()
            if not bans:
                return "📋 Бан-лист пуст"
            lines = [f"{i+1}. ID: {b.get('id')}, @{b.get('username', 'нет')} ({b.get('time', 'forever')})"
                     for i, b in enumerate(bans[:20])]
            return "📋 Бан-лист:\n" + "\n".join(lines)

        elif command == ".idlist":
            if not USER_DATABASE:
                return "📋 Список пуст"
            lines = [f"{i+1}. ID: {uid}, @{info['username'] or 'нет'}"
                     for i, (uid, info) in enumerate(list(USER_DATABASE.items())[:20])]
            return "🔢 Пользователи:\n" + "\n".join(lines)

        elif command == ".mute":
            m = None
            if arg:
                try:
                    m = int(arg)
                except ValueError:
                    pass
            if m:
                return f"✅ Мут на {m} мин. (применяется через бота в чате)"
            return "✅ Мут бессрочный (применяется через бота в чате)"

        elif command == ".unmute":
            return "✅ Мут выключен (применяется через бота в чате)"

        elif command == ".ai":
            if not arg:
                return "❌ .ai (вопрос)"
            if not GROQ_API_KEY:
                return "❌ Groq не настроен"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post("https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                        json={"model": GROQ_MODEL, "messages": [
                            {"role": "system", "content": "Отвечай на русском кратко."},
                            {"role": "user", "content": arg}], "max_tokens": 500},
                        timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data["choices"][0]["message"]["content"]
                        return f"❌ Ошибка API: {resp.status}"
            except Exception as e:
                return f"❌ Ошибка: {e}"

        else:
            return f"❌ Команда {command} не поддерживается из консоли"

    except Exception as e:
        return f"❌ Ошибка: {e}"

# ============================================================
# ОСНОВНАЯ ЛОГИКА
# ============================================================

async def handle_business_message(message: Message, bot: Bot):
    if message.from_user is None:
        return

    request_id = str(uuid.uuid4())[:8]
    chat_id = message.chat.id
    message_id = message.message_id
    sender_id = message.from_user.id
    text = message.text or ""
    bc_id = message.business_connection_id

    add_trace_step(request_id, f"📥 Получено сообщение в чате {chat_id}")

    USER_DATABASE[sender_id] = {"username": message.from_user.username or "", "last_seen": time.time()}

    # Проверка бана
    t0 = time.time()
    ban = await api_check_ban(user_id=sender_id)
    add_trace_step(request_id, f"🔍 Проверка бана ({int((time.time()-t0)*1000)}ms)")
    if ban:
        add_trace_step(request_id, "🚫 Пользователь в бане")
        asyncio.create_task(api_send_trace(request_id, TRACE_BUFFER.get(request_id, [])))
        return

    if text:
        store_message(chat_id, message_id, text, sender_id)

    # Антимат
    if is_antimat(chat_id) and sender_id != OWNER_ID and text and contains_bad_words(text):
        try:
            await bot.delete_business_messages(business_connection_id=bc_id, message_ids=[message_id])
            add_trace_step(request_id, "🛡 Антимат: удалено")
        except Exception:
            pass
        asyncio.create_task(api_send_trace(request_id, TRACE_BUFFER.get(request_id, [])))
        return

    # Мут
    if is_muted(chat_id) and sender_id != OWNER_ID:
        try:
            await bot.delete_business_messages(business_connection_id=bc_id, message_ids=[message_id])
            add_trace_step(request_id, "🔇 Мут: удалено")
        except Exception:
            pass
        asyncio.create_task(api_send_trace(request_id, TRACE_BUFFER.get(request_id, [])))
        return

    # Только от владельца
    if sender_id != OWNER_ID or not bc_id:
        add_trace_step(request_id, "✅ Пропущено (не владелец)")
        asyncio.create_task(api_send_trace(request_id, TRACE_BUFFER.get(request_id, [])))
        return

    if not text.startswith("."):
        add_trace_step(request_id, "📝 Обычное сообщение владельца")
        asyncio.create_task(api_send_trace(request_id, TRACE_BUFFER.get(request_id, [])))
        return

    cmd, arg, to_dm = parse_command(text)
    add_trace_step(request_id, f"⌨️ Команда: {cmd}")

    if cmd == ".nomute":
        await cmd_nomute(message, bot, bc_id)
        asyncio.create_task(bot.delete_business_messages(business_connection_id=bc_id, message_ids=[message_id]))
        asyncio.create_task(api_send_trace(request_id, TRACE_BUFFER.get(request_id, [])))
        return
    if cmd == ".unnomute":
        await cmd_unnomute(message, bot, bc_id)
        asyncio.create_task(bot.delete_business_messages(business_connection_id=bc_id, message_ids=[message_id]))
        asyncio.create_task(api_send_trace(request_id, TRACE_BUFFER.get(request_id, [])))
        return

    asyncio.create_task(bot.delete_business_messages(business_connection_id=bc_id, message_ids=[message_id]))
    add_trace_step(request_id, "🗑️ Команда удалена")

    reply_chat_id = OWNER_ID if to_dm else chat_id

    if cmd == ".ai":
        t0 = time.time()
        await cmd_ai(message, bot, bc_id, reply_chat_id, to_dm, arg)
        add_trace_step(request_id, f"🧠 AI ответ ({int((time.time()-t0)*1000)}ms)")
    elif cmd == ".me":
        await cmd_me(message, bot, bc_id, reply_chat_id, to_dm)
        add_trace_step(request_id, "👤 Профиль отправлен")
    elif cmd == ".ping":
        await cmd_ping(message, bot, bc_id, reply_chat_id, to_dm)
        add_trace_step(request_id, "🏓 Ping отправлен")
    elif cmd == ".ban":
        await cmd_ban(message, bot, bc_id, reply_chat_id, to_dm, arg)
        add_trace_step(request_id, "🚫 Бан обработан")
    elif cmd == ".unban":
        await cmd_unban(message, bot, bc_id, reply_chat_id, to_dm, arg)
        add_trace_step(request_id, "✅ Разбан обработан")
    elif cmd == ".idlist":
        await cmd_idlist(message, bot, bc_id, reply_chat_id, to_dm, arg)
        add_trace_step(request_id, "🔢 IDlist отправлен")
    elif cmd == ".checkban":
        await cmd_checkban(message, bot, bc_id, reply_chat_id, to_dm, arg)
        add_trace_step(request_id, "🔰 Checkban отправлен")
    elif cmd == ".banlist":
        await cmd_banlist(message, bot, bc_id, reply_chat_id, to_dm, arg)
        add_trace_step(request_id, "📋 Banlist отправлен")
    elif cmd == ".mute":
        await cmd_mute(message, bot, bc_id, reply_chat_id, to_dm, arg)
        add_trace_step(request_id, "🔇 Mute обработан")
    elif cmd == ".unmute":
        await cmd_unmute(message, bot, bc_id, reply_chat_id, to_dm)
        add_trace_step(request_id, "🔊 Unmute обработан")
    elif cmd == ".antimat":
        await cmd_antimat(message, bot, bc_id, reply_chat_id, to_dm, arg)
        add_trace_step(request_id, "🛡 Antimat обработан")
    elif cmd == ".id":
        await cmd_id(message, bot, bc_id, reply_chat_id, to_dm)
        add_trace_step(request_id, "🆔 ID отправлен")
    elif cmd == ".business":
        await cmd_business(message, bot, bc_id, reply_chat_id, to_dm)
        add_trace_step(request_id, "🔗 Business отправлен")
    elif cmd == ".data":
        await cmd_data(message, bot, bc_id, reply_chat_id, to_dm)
        add_trace_step(request_id, "📅 Data отправлен")

    asyncio.create_task(api_send_trace(request_id, TRACE_BUFFER.get(request_id, [])))

# ============================================================
# КОМАНДЫ
# ============================================================

async def send_reply(bot, chat_id, text, bc_id, to_dm, parse_mode="HTML"):
    try:
        kw = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if not to_dm and bc_id:
            kw["business_connection_id"] = bc_id
        await bot.send_message(**kw)
    except Exception as e:
        logger.error("send_reply: %s", e)

async def cmd_ai(message, bot, bc_id, reply_chat_id, to_dm, arg):
    if not arg or not GROQ_API_KEY:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": GROQ_MODEL, "messages": [
                    {"role": "system", "content": "Отвечай только на русском языке. Кратко."},
                    {"role": "user", "content": arg}], "max_tokens": 500},
                timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    await send_reply(bot, reply_chat_id, data["choices"][0]["message"]["content"], bc_id, to_dm)
    except Exception as e:
        logger.error("ai: %s", e)

async def cmd_me(message, bot, bc_id, reply_chat_id, to_dm):
    u = message.from_user
    await send_reply(bot, reply_chat_id,
        f"<b>Ваш профиль</b>\n<blockquote>ID: {u.id}\nНик: @{u.username or 'нет'}\nРоль: creator</blockquote>",
        bc_id, to_dm)

async def cmd_business(message, bot, bc_id, reply_chat_id, to_dm):
    await send_reply(bot, reply_chat_id,
        f"<b>Business connection</b>\n<blockquote>ID: {bc_id}\nChat ID: {message.chat.id}</blockquote>",
        bc_id, to_dm)

async def cmd_id(message, bot, bc_id, reply_chat_id, to_dm):
    await send_reply(bot, reply_chat_id,
        f"<b>ID</b>\n<blockquote>User: {message.from_user.id}\nChat: {message.chat.id}</blockquote>",
        bc_id, to_dm)

async def cmd_ping(message, bot, bc_id, reply_chat_id, to_dm):
    start = time.time()
    await bot.get_me()
    api_ping = int((time.time() - start) * 1000)

    site_ping = -1
    if SITE_API_URL:
        try:
            start = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{SITE_API_URL}/status",
                    headers={"X-Admin-Password": ADMIN_PASSWORD},
                    timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    pass
            site_ping = int((time.time() - start) * 1000)
        except Exception:
            site_ping = -1

    txt = (
        f"<b>🏓 Ping</b>\n"
        f"<blockquote>"
        f"TG API: {api_ping}ms\n"
        f"Site API: {site_ping}ms"
        f"</blockquote>"
    )
    await send_reply(bot, reply_chat_id, txt, bc_id, to_dm)

async def cmd_data(message, bot, bc_id, reply_chat_id, to_dm):
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    await send_reply(bot, reply_chat_id, f"<b>📅 Дата</b>\n<blockquote>{now.strftime('%d.%m.%Y %H:%M')} MSK</blockquote>", bc_id, to_dm)

async def cmd_mute(message, bot, bc_id, reply_chat_id, to_dm, arg):
    m = None
    if arg:
        try:
            m = int(arg)
        except ValueError:
            m = None
    set_mute(message.chat.id, m)
    txt = f"🔇 <b>Мут</b>\n<blockquote>На {m} мин.</blockquote>" if m else "🔇 <b>Мут бессрочно</b>"
    await send_reply(bot, reply_chat_id, txt, bc_id, to_dm)

async def cmd_unmute(message, bot, bc_id, reply_chat_id, to_dm):
    clear_mute(message.chat.id)
    await send_reply(bot, reply_chat_id, "🔊 <b>Мут выключен</b>", bc_id, to_dm)

async def cmd_antimat(message, bot, bc_id, reply_chat_id, to_dm, arg):
    a = arg.lower().strip()
    if a == "on":
        set_antimat(message.chat.id, True)
        await send_reply(bot, reply_chat_id, "🛡 <b>Антимат вкл</b>", bc_id, to_dm)
    elif a == "off":
        set_antimat(message.chat.id, False)
        await send_reply(bot, reply_chat_id, "🛡 <b>Антимат выкл</b>", bc_id, to_dm)

async def cmd_nomute(message, bot, bc_id):
    global LAST_BUSINESS_CONNECTION_ID
    LAST_BUSINESS_CONNECTION_ID = bc_id
    PENDING_SEND[OWNER_ID] = message.chat.id
    await send_reply(bot, message.chat.id, "🛡 <b>Обход мута вкл</b>", bc_id, False)
    await bot.send_message(OWNER_ID, "🛡 Пишите текст в ЛС бота.")

async def cmd_unnomute(message, bot, bc_id):
    PENDING_SEND.pop(OWNER_ID, None)
    await send_reply(bot, message.chat.id, "🛡 <b>Обход мута выкл</b>", bc_id, False)

async def cmd_ban(message, bot, bc_id, reply_chat_id, to_dm, arg):
    p = arg.split(maxsplit=2)
    if not p or not p[0]:
        await send_reply(bot, reply_chat_id, "❌ .ban (ID/username) (time) (reason)", bc_id, to_dm)
        return
    target = p[0]
    ts = p[1] if len(p) > 1 else "forever"
    reason = p[2] if len(p) > 2 else "не указана"
    tid = None
    try:
        tid = int(target)
    except ValueError:
        for uid, info in USER_DATABASE.items():
            if info["username"] == target.lstrip("@"):
                tid = uid
                break
    if not tid:
        await send_reply(bot, reply_chat_id, f"❌ Не найден {target}", bc_id, to_dm)
        return
    ok = await api_add_ban(tid, target.lstrip("@"), ts, reason)
    txt = f"🚫 <b>Забанен</b>\n<blockquote>ID: {tid}\nTime: {ts}\nReason: {reason}</blockquote>" if ok else "❌ Ошибка"
    await send_reply(bot, reply_chat_id, txt, bc_id, to_dm)

async def cmd_unban(message, bot, bc_id, reply_chat_id, to_dm, arg):
    p = arg.split(maxsplit=1)
    if not p or not p[0]:
        await send_reply(bot, reply_chat_id, "❌ .unban (ID/username) (reason)", bc_id, to_dm)
        return
    target = p[0].lstrip("@")
    reason = p[1] if len(p) > 1 else "не указана"
    tid = 0
    try:
        tid = int(target)
    except ValueError:
        for uid, info in USER_DATABASE.items():
            if info["username"] == target:
                tid = uid
                break
    ok = await api_remove_ban(tid, target)
    txt = f"✅ <b>Разбанен</b>\n<blockquote>ID: {tid}\nReason: {reason}</blockquote>" if ok else "❌ Ошибка"
    await send_reply(bot, reply_chat_id, txt, bc_id, to_dm)

async def cmd_idlist(message, bot, bc_id, reply_chat_id, to_dm, arg):
    page = 1
    if arg:
        try:
            page = max(1, min(10, int(arg)))
        except ValueError:
            page = 1
    users = sorted(USER_DATABASE.items(), key=lambda x: x[1]["last_seen"], reverse=True)
    tp = max(1, min(10, (len(users) + 4) // 5))
    page = min(page, tp)
    start = (page - 1) * 5
    pu = users[start:start + 5]
    if not pu:
        await send_reply(bot, reply_chat_id, "📋 Пусто", bc_id, to_dm)
        return
    lines = [f"{i}. ID: {uid}, @{info['username'] or 'нет'}" for i, (uid, info) in enumerate(pu, start=start + 1)]
    await send_reply(bot, reply_chat_id, f"🔢 <b>Пользователи</b>\n<blockquote>{chr(10).join(lines)}\n\nСтр {page}/{tp}</blockquote>", bc_id, to_dm)

async def cmd_checkban(message, bot, bc_id, reply_chat_id, to_dm, arg):
    if not arg:
        await send_reply(bot, reply_chat_id, "❌ .checkban (ID)", bc_id, to_dm)
        return
    t = arg.strip().lstrip("@")
    tid = None
    try:
        tid = int(t)
    except ValueError:
        for uid, info in USER_DATABASE.items():
            if info["username"] == t:
                tid = uid
                break
    ban = await api_check_ban(user_id=tid, username=t)
    if ban:
        txt = f"🔰 <b>В бане</b>\n<blockquote>ID: {ban.get('id')}\nTime: {ban.get('time')}\nReason: {ban.get('reason')}</blockquote>"
    else:
        txt = f"🔰 <b>Не в бане</b>\n<blockquote>ID: {tid or t}</blockquote>"
    await send_reply(bot, reply_chat_id, txt, bc_id, to_dm)

async def cmd_banlist(message, bot, bc_id, reply_chat_id, to_dm, arg):
    page = 1
    if arg:
        try:
            page = max(1, int(arg))
        except ValueError:
            page = 1
    bans = await api_list_bans()
    if not bans:
        await send_reply(bot, reply_chat_id, "📋 Бан-лист пуст", bc_id, to_dm)
        return
    tp = max(1, (len(bans) + 4) // 5)
    page = min(page, tp)
    pb = bans[(page - 1) * 5:page * 5]
    lines = [f"{i}. ID: {b.get('id')}, @{b.get('username', 'нет')} ({b.get('time', 'forever')})"
             for i, b in enumerate(pb, start=(page - 1) * 5 + 1)]
    await send_reply(bot, reply_chat_id, f"📋 <b>Бан-лист</b>\n<blockquote>{chr(10).join(lines)}\n\nСтр {page}/{tp}</blockquote>", bc_id, to_dm)

async def handle_deleted_business_messages(deleted, bot):
    cid = deleted.chat.id
    if is_muted(cid) or is_antimat(cid):
        return
    chat = deleted.chat
    my_d, their_d = [], []
    for mid in deleted.message_ids:
        s = get_stored_message(cid, mid)
        if s:
            (my_d if s["sender_id"] == OWNER_ID else their_d).append((mid, s["text"]))
        else:
            their_d.append((mid, "(не найдено)"))
    if my_d and not their_d:
        return
    if their_d:
        block = "\n\n".join(f"<b>ID {m}:</b>\n{t}" for m, t in their_d)
        txt = f"<b>🗑️ Удалено</b>\n<blockquote>Чат: {cid}\n\n{block}</blockquote>"
    else:
        txt = f"🗑️ Удалено в чате {cid}"
    try:
        await bot.send_message(OWNER_ID, txt, parse_mode="HTML")
    except Exception:
        pass

async def send_to_chat_from_ls(message, bot, target_chat_id, text):
    bc_id = LAST_BUSINESS_CONNECTION_ID
    if not bc_id:
        await bot.send_message(OWNER_ID, "❌ Нет подключения")
        return
    try:
        await bot.send_message(target_chat_id, text, business_connection_id=bc_id)
        await bot.send_message(OWNER_ID, f"✅ Доставлено в {target_chat_id}")
    except Exception as e:
        logger.error("send_ls: %s", e)

# ============================================================
# ПРИВЕТСТВИЕ
# ============================================================

async def startup_greeting(bot: Bot):
    api_status = "❌"
    try:
        bans = await api_list_bans()
        api_status = f"✅ ({len(bans)} банов)" if SITE_API_URL else "⚠️ не задан"
    except Exception:
        api_status = "❌"

    ai_status = f"✅ Groq" if GROQ_API_KEY else "❌"
    vt_status = "✅" if VIRUSTOTAL_API_KEY else "❌"

    text = (
        "🤖 <b>Бот запущен!</b>\n\n"
        "<b>Статус систем:</b>\n"
        "<blockquote>"
        f"🌐 Site API: {api_status}\n"
        f"🛡 VirusTotal: {vt_status}\n"
        f"🧠 Groq AI: {ai_status}\n"
        f"👥 Пользователей: {len(USER_DATABASE)}\n"
        f"🆔 Owner ID: {OWNER_ID}"
        "</blockquote>\n\n"
        "<b>Мониторинг:</b>\n"
        "<blockquote>"
        "✅ Healthcheck каждые 30 сек\n"
        "✅ Алерты при деградации\n"
        "✅ Трассировка запросов"
        "</blockquote>"
    )
    try:
        await bot.send_message(chat_id=OWNER_ID, text=text, parse_mode="HTML")
    except Exception as e:
        logger.error("❌ greeting: %s", e)

# ============================================================
# ЗАПУСК
# ============================================================

async def main():
    session = AiohttpSession(api=TelegramAPIServer.from_base(TELEGRAM_PROXY_URL), limit=50)
    bot = Bot(token=BOT_TOKEN, session=session, request_timeout=15)
    dp = Dispatcher()

    @dp.business_connection()
    async def on_bc(conn: BusinessConnection):
        global LAST_BUSINESS_CONNECTION_ID
        LAST_BUSINESS_CONNECTION_ID = conn.id
        logger.info("🔗 BC: %s", conn.id)

    @dp.business_message()
    async def on_bm(msg: Message):
        await handle_business_message(msg, bot)

    @dp.message()
    async def on_pm(msg: Message):
        if msg.chat.id == OWNER_ID and msg.text and OWNER_ID in PENDING_SEND:
            await send_to_chat_from_ls(msg, bot, PENDING_SEND[OWNER_ID], msg.text)

    @dp.deleted_business_messages()
    async def on_dbm(d: BusinessMessagesDeleted):
        await handle_deleted_business_messages(d, bot)

    await startup_greeting(bot)

    # Фоновые таски
    asyncio.create_task(heartbeat_task(bot))
    asyncio.create_task(command_poll_task(bot))

    logger.info("🚀 Запуск polling...")
    try:
        await dp.start_polling(bot, allowed_updates=[
            "business_message", "business_connection", "deleted_business_messages", "message"
        ], polling_timeout=10)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
