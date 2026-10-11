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

# URL твоего сайта на Cloudflare Pages
SITE_API_URL = os.getenv("SITE_API_URL", "").strip()

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
logger.info("TELEGRAM_PROXY_URL: %s", TELEGRAM_PROXY_URL)
logger.info("SITE_API_URL: %s", SITE_API_URL if SITE_API_URL else "не задан")
logger.info("VIRUSTOTAL_API_KEY: %s",
            f"установлен (длина {len(VIRUSTOTAL_API_KEY)})" if VIRUSTOTAL_API_KEY else "❌ НЕ УСТАНОВЛЕН")
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

# Список матерных слов
BAD_WORDS = [
    "бля", "блядь", "блять", "блят", "сука", "суки", "сук", "хуй", "хуя", "хую", "хуё",
    "пизда", "пизды", "пизде", "пизду", "пизд", "ебал", "ебать", "ебёт", "ебет", "ебу",
    "еби", "ебан", "ёбан", "уеб", "уёб", "заеб", "заёб", "наеб", "наёб", "отъеб", "отъёб",
    "долбоеб", "долбоёб", "мудак", "мудила", "мразь", "гандон", "гондон", "пидор", "пидар",
    "пидорас", "шлюха", "шалава", "курва", "сучка", "мразота", "тварь",
    "дебил", "дебилоид", "идиот", "кретин", "даун", "лох", "чмо", "чмошник", "уёбок",
    "уебок", "дрочь", "дроч", "манда", "манду", "манды",
]


# ============================================================
# ФУНКЦИИ ХРАНИЛИЩ
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


def is_nomute(chat_id: int) -> bool:
    return NOMUTE_STORAGE.get(chat_id, False)


def set_nomute(chat_id: int, enabled: bool) -> None:
    NOMUTE_STORAGE[chat_id] = enabled


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
# ИНТЕГРАЦИЯ С САЙТОМ
# ============================================================

async def send_to_site(action: str, data: dict) -> dict | None:
    """Отправляет данные на сайт через API."""
    if not SITE_API_URL:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SITE_API_URL}/bot",
                json={"action": action, "data": data},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.warning("⚠️ Сайт API вернул статус %s", resp.status)
                    return None
    except Exception as e:
        logger.warning("⚠️ Ошибка связи с сайтом: %s", e)
        return None


async def notify_site_message(chat_id: int, message_id: int, text: str, sender_id: int) -> None:
    """Уведомляет сайт о новом сообщении."""
    await send_to_site("new_message", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "sender_id": sender_id,
        "timestamp": int(time.time()),
    })


async def notify_site_deletion(chat_id: int, message_ids: list, texts: list) -> None:
    """Уведомляет сайт об удалении сообщений."""
    await send_to_site("deletion", {
        "chat_id": chat_id,
        "message_ids": message_ids,
        "texts": texts,
        "timestamp": int(time.time()),
    })


async def notify_site_command(command: str, chat_id: int, arg: str = "") -> None:
    """Уведомляет сайт о выполненной команде."""
    await send_to_site("command", {
        "command": command,
        "chat_id": chat_id,
        "arg": arg,
        "timestamp": int(time.time()),
    })


# ============================================================
# ОСНОВНАЯ ЛОГИКА
# ============================================================

async def handle_business_message(message: Message, bot: Bot) -> None:
    global LAST_BUSINESS_CONNECTION_ID

    if message.from_user is None:
        return

    chat_id = message.chat.id
    message_id = message.message_id
    sender_id = message.from_user.id
    text = message.text or ""
    bc_id = message.business_connection_id

    if bc_id:
        LAST_BUSINESS_CONNECTION_ID = bc_id

    if text:
        store_message(chat_id, message_id, text, sender_id)
        # Уведомляем сайт о новом сообщении (только от собеседника)
        if sender_id != OWNER_ID:
            asyncio.create_task(notify_site_message(chat_id, message_id, text, sender_id))

    # ========== АНТИМАТ ==========
    if is_antimat(chat_id) and sender_id != OWNER_ID:
        if text and contains_bad_words(text):
            try:
                await bot.delete_business_messages(
                    business_connection_id=bc_id,
                    message_ids=[message_id],
                )
                logger.info("🛡 Антимат: удалено в чате %s", chat_id)
            except Exception as e:
                logger.warning("⚠️ Антимат: не удалось удалить: %s", e)
            return

    # ========== МУТ ==========
    if is_muted(chat_id) and sender_id != OWNER_ID:
        try:
            await bot.delete_business_messages(
                business_connection_id=bc_id,
                message_ids=[message_id],
            )
            logger.info("🔇 Мут: удалено в чате %s", chat_id)
        except Exception as e:
            logger.warning("⚠️ Мут: не удалось удалить: %s", e)
        return

    # ========== КОМАНДЫ ТОЛЬКО ОТ ВЛАДЕЛЬЦА ==========
    if sender_id != OWNER_ID:
        return

    if not bc_id:
        return

    cmd, arg, to_dm = parse_command(text)

    # .nomute / .unnomute — особые команды
    if cmd == ".nomute":
        await cmd_nomute(message, bot, bc_id)
        asyncio.create_task(
            bot.delete_business_messages(
                business_connection_id=bc_id,
                message_ids=[message_id],
            )
        )
        return
    elif cmd == ".unnomute":
        await cmd_unnomute(message, bot, bc_id)
        asyncio.create_task(
            bot.delete_business_messages(
                business_connection_id=bc_id,
                message_ids=[message_id],
            )
        )
        return

    # Удаляем команду (в фоне)
    asyncio.create_task(
        bot.delete_business_messages(
            business_connection_id=bc_id,
            message_ids=[message_id],
        )
    )

    reply_chat_id = OWNER_ID if to_dm else chat_id

    # Уведомляем сайт о команде
    asyncio.create_task(notify_site_command(cmd, chat_id, arg))

    # Роутинг команд
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


async def send_reply(bot: Bot, chat_id: int, text: str, bc_id: str | None, to_dm: bool, parse_mode: str = "HTML"):
    try:
        kwargs = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if not to_dm and bc_id:
            kwargs["business_connection_id"] = bc_id
        await bot.send_message(**kwargs)
        logger.info("✅ Ответ отправлен в %s: %s", "ЛС" if to_dm else "чат", chat_id)
    except Exception as e:
        logger.error("❌ Ошибка отправки ответа: %s", e)


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
    logger.info("🔇 Мут включён в чате %s на %s", chat_id, f"{minutes} мин" if minutes else "бессрочно")


async def cmd_unmute(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool) -> None:
    chat_id = message.chat.id
    clear_mute(chat_id)

    response_text = "🔊 <b>Мут выключен</b>"
    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)
    logger.info("🔊 Мут выключен в чате %s", chat_id)


async def cmd_antimat(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool, arg: str) -> None:
    chat_id = message.chat.id
    arg = arg.lower().strip()

    if arg == "on":
        set_antimat(chat_id, True)
        response_text = (
            "🛡 <b>Антимат включён</b>\n"
            "<blockquote>"
            "Мат и распространённые оскорбления собеседника будут автоматически удаляться."
            "</blockquote>"
        )
    elif arg == "off":
        set_antimat(chat_id, False)
        response_text = (
            "🛡 <b>Антимат выключен</b>\n"
            "<blockquote>"
            "Сообщения снова проходят без фильтра антимата."
            "</blockquote>"
        )
    else:
        response_text = (
            "🛡 <b>Антимат</b>\n"
            "<blockquote>"
            "Использование: .antimat on / .antimat off"
            "</blockquote>"
        )

    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def cmd_nomute(message: Message, bot: Bot, bc_id: str) -> None:
    global LAST_BUSINESS_CONNECTION_ID
    chat_id = message.chat.id
    LAST_BUSINESS_CONNECTION_ID = bc_id

    set_nomute(chat_id, True)
    PENDING_SEND[OWNER_ID] = chat_id

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "🛡 <b>Режим обхода мута включён</b>\n"
                "<blockquote>"
                "Пишите сообщения в ЛС бота или в этот чат."
                "</blockquote>"
            ),
            parse_mode="HTML",
            business_connection_id=bc_id,
        )
    except Exception as e:
        logger.error("❌ .nomute: не удалось отправить в чат: %s", e)

    try:
        await bot.send_message(
            chat_id=OWNER_ID,
            text=(
                "🛡 <b>Режим обхода мута был включен</b>\n\n"
                "⭕ <b>Пишите текст мне в ЛС.</b>\n"
                "⭕ <b>Он будет отправлен в нужный чат.</b>"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("❌ .nomute: не удалось отправить в ЛС: %s", e)

    logger.info("🛡 Режим обхода мута включён для чата %s", chat_id)


async def cmd_unnomute(message: Message, bot: Bot, bc_id: str) -> None:
    chat_id = message.chat.id
    set_nomute(chat_id, False)
    PENDING_SEND.pop(OWNER_ID, None)

    try:
        await bot.send_message(
            chat_id=chat_id,
            text="🛡 <b>Режим обхода мута выключен</b>",
            parse_mode="HTML",
            business_connection_id=bc_id,
        )
    except Exception as e:
        logger.error("❌ .unnomute: не удалось отправить: %s", e)

    logger.info("🛡 Режим обхода мута выключен для чата %s", chat_id)


async def cmd_scan(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool) -> None:
    if not message.reply_to_message:
        response_text = "<b>❌ Используйте команду ответом на файл.</b>"
        await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)
        return

    replied = message.reply_to_message
    file_id = None
    file_name = "неизвестный файл"
    file_size = 0

    if replied.document:
        file_id = replied.document.file_id
        file_name = replied.document.file_name or file_name
        file_size = replied.document.file_size or 0
    elif replied.photo:
        file_id = replied.photo[-1].file_id
        file_name = "photo.jpg"
        file_size = replied.photo[-1].file_size or 0
    elif replied.video:
        file_id = replied.video.file_id
        file_name = replied.video.file_name or "video.mp4"
        file_size = replied.video.file_size or 0
    elif replied.audio:
        file_id = replied.audio.file_id
        file_name = replied.audio.file_name or "audio.mp3"
        file_size = replied.audio.file_size or 0
    elif replied.voice:
        file_id = replied.voice.file_id
        file_name = "voice.ogg"
        file_size = replied.voice.file_size or 0

    if not file_id:
        response_text = "<b>❌ В ответе нет файла для проверки.</b>"
        await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)
        return

    if file_size > 524288000:
        response_text = f"<b>❌ Файл слишком большой.</b>\nРазмер: {file_size / 1024 / 1024:.1f} МБ (макс. 500 МБ)"
        await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)
        return

    if not VIRUSTOTAL_API_KEY:
        response_text = "<b>❌ VirusTotal API-ключ не настроен.</b>\nДобавьте переменную <b>API</b> с ключом."
        await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)
        return

    try:
        file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file.file_path)
        file_data = file_bytes.read()
    except Exception as e:
        logger.error("❌ Не удалось скачать файл: %s", e)
        response_text = "<b>❌ Не удалось скачать файл для проверки.</b>"
        await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)
        return

    vt_upload_url = "https://www.virustotal.com/api/v3/files"
    vt_check_url = "https://www.virustotal.com/api/v3/analyses/"

    if VIRUSTOTAL_PROXY:
        vt_upload_url = f"{VIRUSTOTAL_PROXY.rstrip('/')}/api/v3/files"
        vt_check_url = f"{VIRUSTOTAL_PROXY.rstrip('/')}/api/v3/analyses/"

    try:
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("file", file_data, filename=file_name)

            async with session.post(
                vt_upload_url,
                headers={"x-apikey": VIRUSTOTAL_API_KEY},
                data=form,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error("VirusTotal upload error: %s", error_text)
                    response_text = f"<b>❌ Ошибка VirusTotal:</b>\n{error_text[:200]}"
                    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)
                    return

                result = await resp.json()
                analysis_id = result.get("data", {}).get("id", "")

            await asyncio.sleep(5)

            async with session.get(
                f"{vt_check_url}{analysis_id}",
                headers={"x-apikey": VIRUSTOTAL_API_KEY},
            ) as resp:
                if resp.status != 200:
                    response_text = "<b>❌ Не удалось получить отчёт VirusTotal.</b>"
                    await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)
                    return

                report = await resp.json()
                stats = report.get("data", {}).get("attributes", {}).get("stats", {})
                malicious = stats.get("malicious", 0)
                suspicious = stats.get("suspicious", 0)
                undetected = stats.get("undetected", 0)
                harmless = stats.get("harmless", 0)
                total = malicious + suspicious + undetected + harmless

                if malicious > 0 or suspicious > 0:
                    verdict = f"❌ ОПАСНО: {malicious} детектов, {suspicious} подозрений из {total}"
                    verdict_short = "НЕ РЕКОМЕНДУЕТСЯ скачивать."
                else:
                    verdict = f"✅ ЧИСТО: 0 детектов из {total} антивирусов"
                    verdict_short = "Можно скачивать."

                response_text = (
                    "<b>ПРОВЕРКА НА ВИРУСЫ</b>\n\n"
                    f"<b>Цель:</b> {file_name}\n"
                    "<b>Детекты:</b>\n"
                    f"{verdict}\n\n"
                    f"<b>Итог:</b> {verdict_short}"
                )
                await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)

    except Exception as e:
        logger.error("❌ .scan ошибка: %s", e)
        response_text = f"<b>❌ Ошибка проверки:</b>\n{str(e)[:200]}"
        await send_reply(bot, reply_chat_id, response_text, bc_id, to_dm)


async def handle_deleted_business_messages(deleted: BusinessMessagesDeleted, bot: Bot) -> None:
    chat_id = deleted.chat.id

    if is_muted(chat_id) or is_antimat(chat_id):
        logger.info("🔇/🛡 Мут/Антимат активен, уведомление пропущено")
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
            their_deleted.append((msg_id, "(текст не найден в памяти)"))

    if my_deleted and not their_deleted:
        logger.info("🗑️ Удалены только мои сообщения, уведомление не отправлено")
        return

    # Уведомляем сайт об удалении
    asyncio.create_task(notify_site_deletion(
        chat_id,
        [mid for mid, _ in their_deleted],
        [text for _, text in their_deleted],
    ))

    if their_deleted:
        texts_block = "\n\n".join(
            f"<b>ID {mid}:</b>\n{text}" for mid, text in their_deleted
        )
        notification_text = (
            "<b>🗑️ Зафиксировано удалённое сообщение собеседника!</b>\n\n"
            f"<b>ID чата:</b> {chat_id}\n"
            f"<b>Username:</b> {chat_username}\n"
            f"<b>Название:</b> {chat_title}\n\n"
            "<b>Содержимое удалённого сообщения:</b>\n"
            f"{texts_block}"
        )
    else:
        notification_text = (
            "<b>🗑️ Удалено сообщение</b>\n\n"
            f"<b>ID чата:</b> {chat_id}\n"
            f"<b>Username:</b> {chat_username}\n"
            f"<b>Название:</b> {chat_title}\n\n"
            "<i>(Сообщение удалено, но чьё — не определено)</i>"
        )

    try:
        await bot.send_message(chat_id=OWNER_ID, text=notification_text, parse_mode="HTML")
        logger.info("✅ Уведомление об удалении отправлено владельцу")
    except Exception as e:
        logger.error("❌ Не удалось отправить уведомление: %s", e)


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


async def send_to_chat_from_ls(message: Message, bot: Bot, target_chat_id: int, text: str) -> None:
    """Отправляет текст из ЛС в целевой чат от лица владельца."""
    global LAST_BUSINESS_CONNECTION_ID

    bc_id = LAST_BUSINESS_CONNECTION_ID
    if not bc_id:
        await bot.send_message(chat_id=OWNER_ID, text="❌ Нет бизнес-подключения.")
        return

    try:
        await bot.send_message(
            chat_id=target_chat_id,
            text=text,
            business_connection_id=bc_id,
        )
        await bot.send_message(
            chat_id=OWNER_ID,
            text=f"✅ Доставлено в
