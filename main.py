import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta
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

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID_RAW = os.getenv("OWNER_ID", "").strip()
VIRUSTOTAL_API_KEY = os.getenv("API", "").strip()
VIRUSTOTAL_PROXY = os.getenv("VT_PROXY", "").strip()

TELEGRAM_PROXY_URL = "https://lively-brook-2aa0tg-proxy.kichuk2027.workers.dev"

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
logger.info("🤖 Запуск Telegram бота через Cloudflare Worker")
logger.info("BOT_TOKEN: %s", "***" + BOT_TOKEN[-4:] if len(BOT_TOKEN) > 4 else "***")
logger.info("OWNER_ID: %s", OWNER_ID)
logger.info("TELEGRAM_PROXY_URL: %s", TELEGRAM_PROXY_URL)
logger.info("VIRUSTOTAL_API_KEY (API): %s",
            f"установлен (длина {len(VIRUSTOTAL_API_KEY)})" if VIRUSTOTAL_API_KEY else "❌ НЕ УСТАНОВЛЕН")
logger.info("=" * 70)

# ============================================================
# ХРАНИЛИЩА
# ============================================================

# Сообщения: ключ (chat_id, message_id) -> {"text": str, "sender_id": int}
MESSAGE_STORAGE = OrderedDict()
MAX_STORAGE_SIZE = 2000

# Муты: ключ chat_id -> {"until": float или None}  (None = бессрочно)
MUTE_STORAGE = {}


def store_message(chat_id: int, message_id: int, text: str, sender_id: int) -> None:
    key = (chat_id, message_id)
    MESSAGE_STORAGE[key] = {"text": text, "sender_id": sender_id}
    while len(MESSAGE_STORAGE) > MAX_STORAGE_SIZE:
        MESSAGE_STORAGE.popitem(last=False)


def get_stored_message(chat_id: int, message_id: int) -> dict | None:
    return MESSAGE_STORAGE.get((chat_id, message_id))


def is_muted(chat_id: int) -> bool:
    """Проверяет, активен ли мут в чате. Если время вышло — удаляет мут."""
    if chat_id not in MUTE_STORAGE:
        return False
    mute_info = MUTE_STORAGE[chat_id]
    if mute_info["until"] is None:
        return True
    if time.time() < mute_info["until"]:
        return True
    # Время вышло — выключаем мут
    del MUTE_STORAGE[chat_id]
    return False


def set_mute(chat_id: int, minutes: int | None) -> None:
    if minutes is None:
        MUTE_STORAGE[chat_id] = {"until": None}
    else:
        MUTE_STORAGE[chat_id] = {"until": time.time() + minutes * 60}


def clear_mute(chat_id: int) -> None:
    MUTE_STORAGE.pop(chat_id, None)


# ============================================================
# ПАРСИНГ КОМАНД
# ============================================================

def parse_command(text: str) -> tuple[str, str, bool]:
    """
    Возвращает (команда, аргумент, to_dm).
    to_dm = True, если команда заканчивается на ' -s'.
    """
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
# ОСНОВНАЯ ЛОГИКА
# ============================================================

async def handle_business_message(message: Message, bot: Bot) -> None:
    if message.from_user is None:
        return

    chat_id = message.chat.id
    message_id = message.message_id
    sender_id = message.from_user.id
    text = message.text or ""

    # Сохраняем КАЖДОЕ сообщение (и своё, и собеседника) для отслеживания удалений
    if text:
        store_message(chat_id, message_id, text, sender_id)

    # ========== ПРОВЕРКА МУТА ==========
    # Если мут активен и сообщение от СОБЕСЕДНИКА (не от владельца) — удаляем
    if is_muted(chat_id) and sender_id != OWNER_ID:
        try:
            await bot.delete_business_messages(
                business_connection_id=message.business_connection_id,
                message_ids=[message_id],
            )
            logger.info("🔇 Мут: удалено сообщение собеседника в чате %s", chat_id)
        except Exception as e:
            logger.warning("⚠️ Не удалось удалить сообщение (мут): %s", e)
        return  # Не обрабатываем дальше

    # ========== КОМАНДЫ ТОЛЬКО ОТ ВЛАДЕЛЬЦА ==========
    if sender_id != OWNER_ID:
        return

    business_connection_id = message.business_connection_id
    if not business_connection_id:
        return

    cmd, arg, to_dm = parse_command(text)

    # Удаляем команду (в фоне)
    asyncio.create_task(
        bot.delete_business_messages(
            business_connection_id=business_connection_id,
            message_ids=[message_id],
        )
    )

    # Определяем, куда отправлять ответ
    reply_chat_id = OWNER_ID if to_dm else chat_id

    # ========== РОУТИНГ КОМАНД ==========
    if cmd == ".me":
        await cmd_me(message, bot, business_connection_id, reply_chat_id, to_dm)
    elif cmd == ".business":
        await cmd_business(message, bot, business_connection_id, reply_chat_id, to_dm)
    elif cmd == ".id":
        await cmd_id(message, bot, business_connection_id, reply_chat_id, to_dm)
    elif cmd == ".ping":
        await cmd_ping(message, bot, business_connection_id, reply_chat_id, to_dm)
    elif cmd == ".data":
        await cmd_data(message, bot, business_connection_id, reply_chat_id, to_dm)
    elif cmd == ".scan":
        await cmd_scan(message, bot, business_connection_id, reply_chat_id, to_dm)
    elif cmd == ".mute":
        await cmd_mute(message, bot, business_connection_id, reply_chat_id, to_dm, arg)
    elif cmd == ".unmute":
        await cmd_unmute(message, bot, business_connection_id, reply_chat_id, to_dm)


async def send_reply(bot: Bot, chat_id: int, text: str, business_connection_id: str | None, to_dm: bool, parse_mode: str = "HTML"):
    """Отправляет ответ либо в бизнес-чат, либо в ЛС с ботом."""
    try:
        kwargs = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if not to_dm and business_connection_id:
            kwargs["business_connection_id"] = business_connection_id
        await bot.send_message(**kwargs)
        logger.info("✅ Ответ отправлен в %s: %s", "ЛС" if to_dm else "чат", chat_id)
    except Exception as e:
        logger.error("❌ Ошибка отправки ответа: %s", e)


async def cmd_me(message: Message, bot: Bot, bc_id: str, reply_chat_id: int, to_dm: bool) -> None:
    user_id = message.from_user.id
    username = message.from_user.username
    username_str = f"@{username}" if username else "не указан"

    # Роль: creator для владельца, user для остальных
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

    # Если мут активен — не отправляем уведомления об удалении
    if is_muted(chat_id):
        logger.info("🔇 Мут активен, уведомление об удалении в чате %s пропущено", chat_id)
        return

    chat = deleted.chat
    chat_username = f"@{chat.username}" if chat.username else "не указан"
    chat_title = chat.title or chat.full_name or "неизвестно"

    # Разделяем удалённые сообщения на "мои" и "собеседника"
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
            # Неизвестно, чьё — считаем собеседника
            their_deleted.append((msg_id, "(текст не найден в памяти)"))

    # Если удалил ТОЛЬКО я — не пишем уведомление
    if my_deleted and not their_deleted:
        logger.info("🗑️ Удалены только мои сообщения в чате %s, уведомление не отправлено", chat_id)
        return

    # Если удалил собеседник — формируем уведомление
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
        # Только мои, но с unknown
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
        logger.error("❌ Не удалось отправить уведомление об удалении: %s", e)


async def main() -> None:
    session = AiohttpSession(
        api=TelegramAPIServer.from_base(TELEGRAM_PROXY_URL),
        limit=50,
    )
    bot = Bot(token=BOT_TOKEN, session=session, request_timeout=15)
    dp = Dispatcher()

    @dp.business_connection()
    async def on_business_connection(connection: BusinessConnection) -> None:
        logger.info("🔗 BUSINESS CONNECTION: id=%s, user_id=%s, is_enabled=%s",
                    connection.id, connection.user.id, connection.is_enabled)

    @dp.business_message()
    async def process_business_message(message: Message) -> None:
        await handle_business_message(message, bot)

    @dp.deleted_business_messages()
    async def process_deleted_business_messages(deleted: BusinessMessagesDeleted) -> None:
        await handle_deleted_business_messages(deleted, bot)

    try:
        logger.info("🚀 Запуск polling через Cloudflare Worker...")
        await dp.start_polling(
            bot,
            allowed_updates=[
                "business_message",
                "business_connection",
                "deleted_business_messages",
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
