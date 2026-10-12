import asyncio
import logging
import os
import sys
import time
import re
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
logger.info("BOT_TOKEN: %s", "***" + BOT_TOKEN[-4:] if len(BOT_TOKEN) > 4 else "***")
logger.info("OWNER_ID: %s", OWNER_ID)
logger.info("SITE_API_URL: %s", SITE_API_URL if SITE_API_URL else "не задан")
logger.info("ADMIN_PASSWORD: %s", "установлен" if ADMIN_PASSWORD else "❌ НЕ УСТАНОВЛЕН")
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

BAD_WORDS = [
    "бля", "блядь", "блять", "сука", "хуй", "хуя", "пизда", "ебал", "ебать",
    "мудак", "пидор", "шлюха", "тварь", "дебил", "идиот", "кретин", "даун",
    "чмо", "уёбок", "дрочь", "манда",
]

# ============================================================
# ФУНКЦИИ
# ============================================================

def store_message(chat_id: int, message_id: int, text: str, sender_id: int) -> None:
    key = (chat_id, message_id)
    MESSAGE_STORAGE[key] = {"text": text, "sender_id": sender_id}
    while len(MESSAGE_STORAGE) > MAX_STORAGE_SIZE:
        MESSAGE_STORAGE.popitem(last=False)


def get_stored_message(chat_id: int, message_id: int) -> dict | None:
    return MESSAGE_STORAGE.get((chat_id, message_id))


def is_muted(chat_id: int) -> bool:
    if chat_id not in MUTE_STORAGE:
        return False
    mute_info = MUTE_STORAGE[chat_id]
    if mute_info["until"] is None:
        return True
    if time.time() < mute_info["until"]:
        return True
    del MUTE_STORAGE[chat_id]
    return False


def set_mute(chat_id: int, minutes: int | None) -> None:
    if minutes is None:
        MUTE_STORAGE[chat_id] = {"until": None}
    else:
        MUTE_STORAGE[chat_id] = {"until": time.time() + minutes * 60}


def clear_mute(chat_id: int) -> None:
    MUTE_STORAGE.pop(chat_id, None)


def is_antimat(chat_id: int) -> bool:
    return ANTIMAT_STORAGE.get(chat_id, False)


def set_antimat(chat_id: int, enabled: bool) -> None:
    ANTIMAT_STORAGE[chat_id] = enabled


def contains_bad_words(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    words = re.findall(r'[а-яё]+', text_lower)
    for word in words:
        for bad in BAD_WORDS:
            if bad in word:
                return True
    return False


def parse_command(text: str) -> tuple[str, str, bool]:
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
# API ДЛЯ БАНОВ
# ============================================================

async def api_check_ban(user_id: int = None, username: str = None) -> dict | None:
    if not SITE_API_URL:
        return None
    if user_id and user_id in BAN_CACHE:
        cached = BAN_CACHE[user_id]
        if time.time() - cached["cached_at"] < BAN_CACHE_TTL:
            return cached
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SITE_API_URL}/bans",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                json={"action": "check", "ban": {"id": user_id, "username": username}},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ban = data.get("ban")
                    if ban and user_id:
                        BAN_CACHE[user_id] = {**ban, "cached_at": time.time()}
                    return ban
                return None
    except Exception as e:
        logger.error("❌ Ошибка проверки бана: %s", e)
        return None


async def api_add_ban(user_id: int, username: str, time_str: str, reason: str) -> bool:
    if not SITE_API_URL:
        return False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SITE_API_URL}/bans",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                json={"action": "add", "ban": {"id": user_id, "username": username, "time": time_str, "reason": reason, "banned_at": int(time.time())}},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    BAN_CACHE.pop(user_id, None)
                    return True
                return False
    except Exception as e:
        logger.error("❌ Ошибка добавления бана: %s", e)
        return False


async def api_remove_ban(user_id: int, username: str) -> bool:
    if not SITE_API_URL:
        return False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SITE_API_URL}/bans",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                json={"action": "remove", "ban": {"id": user_id, "username": username}},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    BAN_CACHE.pop(user_id, None)
                    return True
                return False
    except Exception as e:
        logger.error("❌ Ошибка удаления бана: %s", e)
        return False


async def api_list_bans() -> list:
    if not SITE_API_URL:
        return []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SITE_API_URL}/bans",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                json={"action": "list"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("bans", [])
                return []
    except Exception as e:
        logger.error("❌ Ошибка получения банов: %s", e)
        return []


# ============================================================
# ОСНОВНАЯ ЛОГИКА
# ============================================================

async def handle_business_message(message: Message, bot: Bot) -> None:
    if message.from_user is None:
        return

    chat_id = message.chat.id
    message_id = message.message_id
    sender_id = message.from_user.id
    text = message.text or ""
    bc_id = message.business_connection_id

    # Запоминаем пользователя
    username = message.from_user.username or ""
    USER_DATABASE[sender_id] = {"username": username, "last_seen": time.time()}

    # Проверка бана
    ban_info = await api_check_ban(user_id=sender_id)
    if ban_info:
        logger.info("🚫 Забаненный %s игнорируется", sender_id)
        return

    if text:
        store_message(chat_id, message_id, text, sender_id)

    # ========== АНТИМАТ (только собеседник) ==========
    if is_antimat(chat_id) and sender_id != OWNER_ID:
        if text and contains_bad_words(text):
            try:
                await bot.delete_business_messages(
                    business_connection_id=bc_id,
                    message_ids=[message_id],
                )
                logger.info("🛡 Антимат: удалено в чате %s", chat_id)
            except Exception as e:
                logger.warning("⚠️ Антимат: %s", e)
            return

    # ========== МУТ (ТОЛЬКО ДЛЯ СОБЕСЕДНИКА!) ==========
    # ВАЖНО: sender_id != OWNER_ID — мои сообщения НЕ удаляются
    if is_muted(chat_id) and sender_id != OWNER_ID:
        try:
            await bot.delete_business_messages(
                business_connection_id=bc_id,
                message_ids=[message_id],
            )
            logger.info("🔇 Мут: удалено сообщение собеседника в чате %s", chat_id)
        except Exception as e:
            logger.warning("⚠️ Мут: %s", e)
        return

    # ========== ТОЛЬКО ОТ ВЛАДЕЛЬЦА ==========
    if sender_id != OWNER_ID:
        return

    if not bc_id:
        return

    # ========== ПРОВЕРКА: ЭТО КОМАНДА? ==========
    # Команда начинается с "." — только тогда удаляем
    if not text.startswith("."):
        # Обычное сообщение владельца — НЕ ТРОГАЕМ
        logger.info("📝 Обычное сообщение владельца, не удаляю: %s", text[:50])
        return

    cmd, arg, to_dm = parse_command(text)

    # Особые команды
    if cmd == ".nomute":
        await cmd_nomute(message, bot, bc_id)
        asyncio.create_task(bot.delete_business_messages(
            business_connection_id=bc_id,
            message_ids=[message_id],
        ))
        return
    elif cmd == ".unnomute":
        await cmd_unnomute(message, bot, bc_id)
        asyncio.create_task(bot.delete_business_messages(
            business_connection_id=bc_id,
            message_ids=[message_id],
        ))
        return

    # Удаляем ТОЛЬКО команду (в фоне)
    asyncio.create_task(bot.delete_business_messages(
        business_connection_id=bc_id,
        message_ids=[message_id],
    ))

    reply_chat_id = OWNER_ID if to_dm else chat_id

    # Роутинг
    if cmd == ".me":
        await cmd_me(message, bot, bc_id, reply_chat_id, to_dm)
    elif cmd == ".business":
        await cmd_business(message, bot, bc_id, reply_chat_id, to_dm)
    elif cmd == ".id":
        await cmd_id(message, bot, bc_id, reply_chat_id, to_dm)
    elif cmd == ".ping":
        await cmd_ping(message, bot, bc_id, reply_chat_id, to_dm)
    elif cmd == ".data":
        await cmd_data(message, bot, bc_id, reply_chat_id, to_dm)
    elif cmd == ".scan":
        await cmd_scan(message, bot, bc_id, reply_chat_id, to_dm)
    elif cmd == ".mute":
        await cmd_mute(message, bot, bc_id, reply_chat_id, to_dm, arg)
    elif cmd == ".unmute":
        await cmd_unmute(message, bot, bc_id, reply_chat_id, to_dm)
    elif cmd == ".antimat":
        await cmd_antimat(message, bot, bc_id, reply_chat_id, to_dm, arg)
    elif cmd == ".ban":
        await cmd_ban(message, bot, bc_id, reply_chat_id, to_dm, arg)
    elif cmd == ".unban":
        await cmd_unban(message, bot, bc_id, reply_chat_id, to_dm, arg)
    elif cmd == ".idlist":
        await cmd_idlist(message, bot, bc_id, reply_chat_id, to_dm, arg)
    elif cmd == ".checkban":
        await cmd_checkban(message, bot, bc_id, reply_chat_id, to_dm, arg)
    elif cmd == ".banlist":
        await cmd_banlist(message, bot, bc_id, reply_chat_id, to_dm, arg)


# ============================================================
# КОМАНДЫ
# ============================================================

async def send_reply(bot: Bot, chat_id: int, text: str, bc_id: str | None, to_dm: bool, parse_mode: str = "HTML"):
    try:
        kwargs = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if not to_dm and bc_id:
            kwargs["business_connection_id"] = bc_id
        await bot.send_message(**kwargs)
        logger.info("✅ Ответ отправлен в %s: %s", "ЛС" if to_dm else "чат", chat_id)
    except Exception as e:
        logger.error("❌ Ошибка отправки: %s", e)


async def cmd_me(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool) -> None:
    user_id = message.from_user.id
    username = message.from_user.username
    username_str = f"@{username}" if username else "не указан"
    role = "creator" if user_id == OWNER_ID else "user"
    response_text = (
        "<b>Ваш профиль</b>\n"
        "<blockquote>"
        f"ID: {user_id}\n"
        f"Ник: {username_str}\n"
        f"Роль: {role}"
        "</blockquote>"
    )
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def cmd_business(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool) -> None:
    response_text = (
        "<b>Business connection</b>\n"
        "<blockquote>"
        f"ID: {bc_id}\n"
        f"User ID: {message.from_user.id}\n"
        f"Chat ID: {message.chat.id}"
        "</blockquote>"
    )
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def cmd_id(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool) -> None:
    response_text = (
        "<b>Идентификаторы</b>\n"
        "<blockquote>"
        f"Ваш Telegram ID: {message.from_user.id}\n"
        f"ID чата: {message.chat.id}"
        "</blockquote>"
    )
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def cmd_ping(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool) -> None:
    api_ping = 0
    try:
        start = time.time()
        await bot.get_me()
        api_ping = int((time.time() - start) * 1000)
    except Exception:
        api_ping = -1
    tcp_ping = 0
    try:
        start = time.time()
        reader, writer = await asyncio.open_connection("api.telegram.org", 443)
        tcp_ping = int((time.time() - start) * 1000)
        writer.close()
        await writer.wait_closed()
    except Exception:
        tcp_ping = -1
    try:
        bot_info = await bot.get_me()
        bot_username = f"@{bot_info.username}"
    except Exception:
        bot_username = "неизвестно"
    status = "online" if api_ping >= 0 else "offline"
    response_text = (
        "<b>Ping</b>\n"
        "<blockquote>"
        f"API: {api_ping}ms\n"
        f"TCP: {tcp_ping}ms\n"
        f"Bot: {bot_username}\n"
        f"Status: {status}"
        "</blockquote>"
    )
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def cmd_data(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool) -> None:
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    months_ru = ["января", "февраля", "марта", "апреля", "мая", "июня",
                 "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    day_name = days_ru[now.weekday()]
    month_name = months_ru[now.month - 1]
    date_str = f"{day_name}, {now.day} {month_name} {now.year}."
    response_text = (
        "<b>📅 Текущая дата</b>\n"
        "<blockquote>"
        f"{date_str}\n"
        "RU: Moscow/Rostov"
        "</blockquote>"
    )
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def cmd_mute(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool, arg: str) -> None:
    chat_id = message.chat.id
    minutes = None
    if arg:
        try:
            minutes = int(arg)
            if minutes <= 0:
                minutes = None
        except ValueError:
            minutes = None
    set_mute(chat_id, minutes)
    if minutes is None:
        response_text = (
            "🔇 <b>Мут включен</b>\n"
            "<blockquote>"
            "Сообщения собеседника будут удаляться, пока не выключите.\n"
            "Выключить: .unmute"
            "</blockquote>"
        )
    else:
        response_text = (
            "🔇 <b>Мут включен</b>\n"
            "<blockquote>"
            f"Сообщения собеседника будут удаляться {minutes} мин.\n"
            "Выключить: .unmute"
            "</blockquote>"
        )
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def cmd_unmute(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool) -> None:
    clear_mute(message.chat.id)
    await send_reply(bot, reply_chat_id, "🔊 <b>Мут выключен</b>", bc_id, to_dm)


async def cmd_antimat(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool, arg: str) -> None:
    chat_id = message.chat.id
    arg = arg.lower().strip()
    if arg == "on":
        set_antimat(chat_id, True)
        response_text = (
            "🛡 <b>Антимат включён</b>\n"
            "<blockquote>Мат и оскорбления собеседника будут удаляться.</blockquote>"
        )
    elif arg == "off":
        set_antimat(chat_id, False)
        response_text = (
            "🛡 <b>Антимат выключен</b>\n"
            "<blockquote>Сообщения проходят без фильтра.</blockquote>"
        )
    else:
        response_text = "🛡 Использование: .antimat on / .antimat off"
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def cmd_nomute(message: Message, bot: Bot, bc_id: str) -> None:
    global LAST_BUSINESS_CONNECTION_ID
    chat_id = message.chat.id
    LAST_BUSINESS_CONNECTION_ID = bc_id
    PENDING_SEND[OWNER_ID] = chat_id
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="🛡 <b>Режим обхода мута включён</b>\n<blockquote>Пишите сообщения в ЛС бота.</blockquote>",
            parse_mode="HTML",
            business_connection_id=bc_id,
        )
    except Exception as e:
        logger.error("❌ .nomute: %s", e)
    try:
        await bot.send_message(
            chat_id=OWNER_ID,
            text="🛡 <b>Режим обхода мута был включен</b>\n\n⭕ <b>Пишите текст мне в ЛС.</b>\n⭕ <b>Он будет отправлен в нужный чат.</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("❌ .nomute ЛС: %s", e)


async def cmd_unnomute(message: Message, bot: Bot, bc_id: str) -> None:
    PENDING_SEND.pop(OWNER_ID, None)
    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text="🛡 <b>Режим обхода мута выключен</b>",
            parse_mode="HTML",
            business_connection_id=bc_id,
        )
    except Exception as e:
        logger.error("❌ .unnomute: %s", e)


async def cmd_scan(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool) -> None:
    pass


async def cmd_ban(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool, arg: str) -> None:
    parts = arg.split(maxsplit=2)
    if len(parts) < 1 or not parts[0]:
        await send_reply(bot, reply_chat_id,
            "❌ Использование: .ban (ID/username) (time) (reason)", bc_id, to_dm)
        return
    target = parts[0]
    time_str = parts[1] if len(parts) > 1 else "forever"
    reason = parts[2] if len(parts) > 2 else "не указана"
    target_username = target.lstrip("@")
    target_id = None
    try:
        target_id = int(target)
        if target_id in USER_DATABASE:
            target_username = USER_DATABASE[target_id]["username"] or target_username
    except ValueError:
        for uid, info in USER_DATABASE.items():
            if info["username"] == target_username:
                target_id = uid
                break
    if not target_id:
        await send_reply(bot, reply_chat_id,
            f"❌ Пользователь @{target_username} не найден в базе.", bc_id, to_dm)
        return
    success = await api_add_ban(target_id, target_username, time_str, reason)
    if success:
        response_text = (
            "🚫 <b>Пользователь заблокирован</b>\n"
            "<blockquote>"
            f"ID: {target_id}, @{target_username}.\n"
            f"Time: {time_str}.\n"
            f"Reason: {reason}."
            "</blockquote>"
        )
    else:
        response_text = "❌ Не удалось добавить бан"
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def cmd_unban(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool, arg: str) -> None:
    parts = arg.split(maxsplit=1)
    if not parts or not parts[0]:
        await send_reply(bot, reply_chat_id,
            "❌ Использование: .unban (ID/username) (reason)", bc_id, to_dm)
        return
    target = parts[0]
    reason = parts[1] if len(parts) > 1 else "не указана"
    target_username = target.lstrip("@")
    target_id = 0
    try:
        target_id = int(target)
        if target_id in USER_DATABASE:
            target_username = USER_DATABASE[target_id]["username"] or target_username
    except ValueError:
        for uid, info in USER_DATABASE.items():
            if info["username"] == target_username:
                target_id = uid
                break
    success = await api_remove_ban(target_id, target_username)
    if success:
        response_text = (
            "✅ <b>Пользователь разбанен</b>\n"
            "<blockquote>"
            f"ID: {target_id}, @{target_username}.\n"
            f"Reason: {reason}."
            "</blockquote>"
        )
    else:
        response_text = "❌ Не удалось снять бан"
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def cmd_idlist(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool, arg: str) -> None:
    page = 1
    if arg:
        try:
            page = max(1, min(10, int(arg)))
        except ValueError:
            page = 1
    users = sorted(USER_DATABASE.items(), key=lambda x: x[1]["last_seen"], reverse=True)
    total_pages = max(1, min(10, (len(users) + 4) // 5))
    page = min(page, total_pages)
    start = (page - 1) * 5
    page_users = users[start:start + 5]
    if not page_users:
        await send_reply(bot, reply_chat_id, "📋 Список пуст.", bc_id, to_dm)
        return
    lines = []
    for i, (uid, info) in enumerate(page_users, start=start + 1):
        uname = info["username"] or "нет"
        lines.append(f"{i}. ID: {uid}, @{uname}.")
    response_text = (
        "🔢 <b>Список пользователей</b>\n"
        "<blockquote>"
        + "\n".join(lines) +
        f"\n\nСтраница {page}/{total_pages}"
        "</blockquote>"
    )
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def cmd_checkban(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool, arg: str) -> None:
    if not arg:
        await send_reply(bot, reply_chat_id,
            "❌ Использование: .checkban (ID/username)", bc_id, to_dm)
        return
    target = arg.strip().lstrip("@")
    target_id = None
    try:
        target_id = int(target)
    except ValueError:
        for uid, info in USER_DATABASE.items():
            if info["username"] == target:
                target_id = uid
                break
    ban_info = await api_check_ban(user_id=target_id, username=target)
    if ban_info:
        response_text = (
            "🔰 <b>Проверка пользователя</b>\n"
            "<blockquote>"
            f"ID: {ban_info.get('id', target_id)}, @{ban_info.get('username', target)}.\n"
            f"Time: {ban_info.get('time', 'forever')}.\n"
            f"Reason: {ban_info.get('reason', 'не указана')}."
            "</blockquote>"
        )
    else:
        response_text = (
            "🔰 <b>Проверка пользователя</b>\n"
            "<blockquote>"
            f"ID: {target_id or target}, @{target}.\n"
            "Не в бане."
            "</blockquote>"
        )
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def cmd_banlist(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool, arg: str) -> None:
    page = 1
    if arg:
        try:
            page = max(1, int(arg))
        except ValueError:
            page = 1
    bans = await api_list_bans()
    if not bans:
        await send_reply(bot, reply_chat_id, "📋 Бан-лист пуст.", bc_id, to_dm)
        return
    total_pages = max(1, (len(bans) + 4) // 5)
    page = min(page, total_pages)
    start = (page - 1) * 5
    page_bans = bans[start:start + 5]
    lines = []
    for i, b in enumerate(page_bans, start=start + 1):
        lines.append(f"{i}. ID: {b.get('id', '—')}, @{b.get('username', 'нет')}. ({b.get('time', 'forever')})")
    response_text = (
        "📋 <b>Бан-лист</b>\n"
        "<blockquote>"
        + "\n".join(lines) +
        f"\n\nСтраница {page}/{total_pages}"
        "</blockquote>"
    )
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def handle_deleted_business_messages(deleted: BusinessMessagesDeleted, bot: Bot) -> None:
    chat_id = deleted.chat.id
    if is_muted(chat_id) or is_antimat(chat_id):
        return
    chat = deleted.chat
    chat_username = f"@{chat.username}" if chat.username else "не указан"
    chat_title = chat.title or chat.full_name or "неизвестно"
    my_deleted = []
    their_deleted = []
    for msg_id in deleted.message_ids:
        stored = get_stored_message(chat_id, msg_id)
        if stored:
            if stored["sender_id"] == OWNER_ID:
                my_deleted.append((msg_id, stored["text"]))
            else:
                their_deleted.append((msg_id, stored["text"]))
        else:
            their_deleted.append((msg_id, "(текст не найден)"))
    if my_deleted and not their_deleted:
        return
    if their_deleted:
        texts_block = "\n\n".join(f"<b>ID {mid}:</b>\n{text}" for mid, text in their_deleted)
        notification_text = (
            "<b>🗑️ Зафиксировано удалённое сообщение!</b>\n\n"
            f"<b>ID чата:</b> {chat_id}\n"
            f"<b>Username:</b> {chat_username}\n"
            f"<b>Название:</b> {chat_title}\n\n"
            f"<b>Содержимое:</b>\n{texts_block}"
        )
    else:
        notification_text = f"🗑️ Удалено сообщение в чате {chat_id}"
    try:
        await bot.send_message(chat_id=OWNER_ID, text=notification_text, parse_mode="HTML")
    except Exception as e:
        logger.error("❌ Уведомление: %s", e)


async def send_to_chat_from_ls(message: Message, bot: Bot, target_chat_id: int, text: str) -> None:
    global LAST_BUSINESS_CONNECTION_ID
    bc_id = LAST_BUSINESS_CONNECTION_ID
    if not bc_id:
        await bot.send_message(chat_id=OWNER_ID, text="❌ Нет бизнес-подключения.")
        return
    try:
        await bot.send_message(chat_id=target_chat_id, text=text, business_connection_id=bc_id)
        await bot.send_message(chat_id=OWNER_ID, text=f"✅ Доставлено в чат {target_chat_id}")
    except Exception as e:
        logger.error("❌ Ошибка отправки: %s", e)


# ============================================================
# ЗАПУСК
# ============================================================

async def main() -> None:
    session = AiohttpSession(
        api=TelegramAPIServer.from_base(TELEGRAM_PROXY_URL),
        limit=50,
    )
    bot = Bot(token=BOT_TOKEN, session=session, request_timeout=15)
    dp = Dispatcher()

    @dp.business_connection()
    async def on_business_connection(connection: BusinessConnection) -> None:
        global LAST_BUSINESS_CONNECTION_ID
        LAST_BUSINESS_CONNECTION_ID = connection.id
        logger.info("🔗 BUSINESS CONNECTION: id=%s, user_id=%s, is_enabled=%s",
                    connection.id, connection.user.id, connection.is_enabled)

    @dp.business_message()
    async def process_business_message(message: Message) -> None:
        await handle_business_message(message, bot)

    @dp.message()
    async def process_private_message(message: Message) -> None:
        if message.chat.id == OWNER_ID and message.text:
            if OWNER_ID in PENDING_SEND:
                target_chat_id = PENDING_SEND.get(OWNER_ID)
                if target_chat_id:
                    await send_to_chat_from_ls(message, bot, target_chat_id, message.text)

    @dp.deleted_business_messages()
    async def process_deleted_business_messages(deleted: BusinessMessagesDeleted) -> None:
        await handle_deleted_business_messages(deleted, bot)

    try:
        logger.info("🚀 Запуск polling...")
        await dp.start_polling(
            bot,
            allowed_updates=[
                "business_message",
                "business_connection",
                "deleted_business_messages",
                "message",
            ],
            polling_timeout=10,
        )
    except asyncio.CancelledError:
        logger.info("🛑 Polling отменён.")
        raise
    except Exception as e:
        logger.error("❌ Ошибка polling: %s", e, exc_info=True)
        raise
    finally:
        await bot.session.close()
        logger.info("🛑 Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем.")
    except Exception as e:
        logger.critical("💥 Критическая ошибка: %s", e, exc_info=True)
        raise
