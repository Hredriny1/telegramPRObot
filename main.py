import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.types import Message, BusinessConnection, BusinessMessagesDeleted, Update

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID_RAW = os.getenv("OWNER_ID", "").strip()
VIRUSTOTAL_API_KEY = os.getenv("API", "").strip()

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
logger.info("🤖 Запуск Telegram бота в режиме long polling")
logger.info("BOT_TOKEN: %s", "***" + BOT_TOKEN[-4:] if len(BOT_TOKEN) > 4 else "***")
logger.info("OWNER_ID: %s", OWNER_ID)
logger.info("VIRUSTOTAL_API_KEY (переменная API): %s",
            f"установлен (длина {len(VIRUSTOTAL_API_KEY)})" if VIRUSTOTAL_API_KEY else "❌ НЕ УСТАНОВЛЕН")
logger.info("=" * 70)


async def handle_business_message(message: Message, bot: Bot) -> None:
    if message.from_user is None:
        return
    if message.from_user.id != OWNER_ID:
        return

    text = message.text or ""
    business_connection_id = message.business_connection_id
    if not business_connection_id:
        return

    if text.startswith(".me"):
        await cmd_me(message, bot, business_connection_id)
    elif text.startswith(".business"):
        await cmd_business(message, bot, business_connection_id)
    elif text.startswith(".id"):
        await cmd_id(message, bot, business_connection_id)
    elif text.startswith(".ping"):
        await cmd_ping(message, bot, business_connection_id)
    elif text.startswith(".data"):
        await cmd_data(message, bot, business_connection_id)
    elif text.startswith(".scan"):
        await cmd_scan(message, bot, business_connection_id)


async def cmd_me(message: Message, bot: Bot, business_connection_id: str) -> None:
    asyncio.create_task(
        bot.delete_business_messages(
            business_connection_id=business_connection_id,
            message_ids=[message.message_id],
        )
    )

    user_id = message.from_user.id
    username = message.from_user.username
    username_str = f"@{username}" if username else "не указан"

    response_text = (
        "<b>Ваш профиль</b>\n"
        "<blockquote>"
        f"ID: {user_id}\n"
        f"Ник: {username_str}\n"
        "Роль: user"
        "</blockquote>"
    )

    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text=response_text,
            parse_mode="HTML",
            business_connection_id=business_connection_id,
        )
        logger.info("✅ .me ответ отправлен в чат: %s", message.chat.id)
    except Exception as e:
        logger.error("❌ .me ошибка: %s", e)


async def cmd_business(message: Message, bot: Bot, business_connection_id: str) -> None:
    asyncio.create_task(
        bot.delete_business_messages(
            business_connection_id=business_connection_id,
            message_ids=[message.message_id],
        )
    )

    response_text = (
        "<b>Business connection</b>\n"
        "<blockquote>"
        f"ID: {business_connection_id}\n"
        f"User ID: {message.from_user.id}\n"
        f"Chat ID: {message.chat.id}"
        "</blockquote>"
    )

    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text=response_text,
            parse_mode="HTML",
            business_connection_id=business_connection_id,
        )
        logger.info("✅ .business ответ отправлен в чат: %s", message.chat.id)
    except Exception as e:
        logger.error("❌ .business ошибка: %s", e)


async def cmd_id(message: Message, bot: Bot, business_connection_id: str) -> None:
    asyncio.create_task(
        bot.delete_business_messages(
            business_connection_id=business_connection_id,
            message_ids=[message.message_id],
        )
    )

    response_text = (
        "<b>Идентификаторы</b>\n"
        "<blockquote>"
        f"Ваш Telegram ID: {message.from_user.id}\n"
        f"ID чата: {message.chat.id}"
        "</blockquote>"
    )

    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text=response_text,
            parse_mode="HTML",
            business_connection_id=business_connection_id,
        )
        logger.info("✅ .id ответ отправлен в чат: %s", message.chat.id)
    except Exception as e:
        logger.error("❌ .id ошибка: %s", e)


async def cmd_ping(message: Message, bot: Bot, business_connection_id: str) -> None:
    asyncio.create_task(
        bot.delete_business_messages(
            business_connection_id=business_connection_id,
            message_ids=[message.message_id],
        )
    )

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

    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text=response_text,
            parse_mode="HTML",
            business_connection_id=business_connection_id,
        )
        logger.info("✅ .ping ответ отправлен в чат: %s", message.chat.id)
    except Exception as e:
        logger.error("❌ .ping ошибка: %s", e)


async def cmd_data(message: Message, bot: Bot, business_connection_id: str) -> None:
    asyncio.create_task(
        bot.delete_business_messages(
            business_connection_id=business_connection_id,
            message_ids=[message.message_id],
        )
    )

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

    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text=response_text,
            parse_mode="HTML",
            business_connection_id=business_connection_id,
        )
        logger.info("✅ .data ответ отправлен в чат: %s", message.chat.id)
    except Exception as e:
        logger.error("❌ .data ошибка: %s", e)


async def cmd_scan(message: Message, bot: Bot, business_connection_id: str) -> None:
    asyncio.create_task(
        bot.delete_business_messages(
            business_connection_id=business_connection_id,
            message_ids=[message.message_id],
        )
    )

    if not message.reply_to_message:
        response_text = "<b>❌ Используйте команду ответом на файл.</b>"
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=response_text,
                parse_mode="HTML",
                business_connection_id=business_connection_id,
            )
        except Exception as e:
            logger.error("❌ .scan ошибка: %s", e)
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
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=response_text,
                parse_mode="HTML",
                business_connection_id=business_connection_id,
            )
        except Exception as e:
            logger.error("❌ .scan ошибка: %s", e)
        return

    if file_size > 524288000:
        response_text = f"<b>❌ Файл слишком большой.</b>\nРазмер: {file_size / 1024 / 1024:.1f} МБ (макс. 500 МБ)"
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=response_text,
                parse_mode="HTML",
                business_connection_id=business_connection_id,
            )
        except Exception as e:
            logger.error("❌ .scan ошибка: %s", e)
        return

    if not VIRUSTOTAL_API_KEY:
        logger.error("❌ .scan: VIRUSTOTAL_API_KEY пустой. Переменная API не читается.")
        response_text = "<b>❌ VirusTotal API-ключ не настроен.</b>\nДобавьте переменную <b>API</b> с ключом."
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=response_text,
                parse_mode="HTML",
                business_connection_id=business_connection_id,
            )
        except Exception as e:
            logger.error("❌ .scan ошибка: %s", e)
        return

    try:
        file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file.file_path)
        file_data = file_bytes.read()
    except Exception as e:
        logger.error("❌ Не удалось скачать файл: %s", e)
        response_text = "<b>❌ Не удалось скачать файл для проверки.</b>"
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=response_text,
                parse_mode="HTML",
                business_connection_id=business_connection_id,
            )
        except Exception:
            pass
        return

    try:
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("file", file_data, filename=file_name)

            async with session.post(
                "https://www.virustotal.com/api/v3/files",
                headers={"x-apikey": VIRUSTOTAL_API_KEY},
                data=form,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error("VirusTotal upload error: %s", error_text)
                    response_text = f"<b>❌ Ошибка VirusTotal:</b>\n{error_text[:200]}"
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text=response_text,
                        parse_mode="HTML",
                        business_connection_id=business_connection_id,
                    )
                    return

                result = await resp.json()
                analysis_id = result.get("data", {}).get("id", "")

            await asyncio.sleep(5)

            async with session.get(
                f"https://www.virustotal.com/api/v3/analyses/{analysis_id}",
                headers={"x-apikey": VIRUSTOTAL_API_KEY},
            ) as resp:
                if resp.status != 200:
                    response_text = "<b>❌ Не удалось получить отчёт VirusTotal.</b>"
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text=response_text,
                        parse_mode="HTML",
                        business_connection_id=business_connection_id,
                    )
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

                await bot.send_message(
                    chat_id=message.chat.id,
                    text=response_text,
                    parse_mode="HTML",
                    business_connection_id=business_connection_id,
                )
                logger.info("✅ .scan отчёт отправлен для %s", file_name)

    except Exception as e:
        logger.error("❌ .scan ошибка: %s", e)
        response_text = f"<b>❌ Ошибка проверки:</b>\n{str(e)[:200]}"
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=response_text,
                parse_mode="HTML",
                business_connection_id=business_connection_id,
            )
        except Exception:
            pass


async def handle_deleted_business_messages(deleted: BusinessMessagesDeleted, bot: Bot) -> None:
    """Обработка удалённых сообщений в бизнес-аккаунте."""
    logger.info(
        "🗑️ Удалены сообщения: connection_id=%s, chat_id=%s, message_ids=%s",
        deleted.business_connection_id,
        deleted.chat.id,
        deleted.message_ids,
    )

    # Отправляем уведомление в ЛС владельцу
    # ВАЖНО: Telegram не присылает текст удалённого сообщения, только его ID
    try:
        chat = deleted.chat
        chat_username = f"@{chat.username}" if chat.username else "не указан"
        chat_title = chat.title or chat.full_name or "неизвестно"

        # Формируем список удалённых ID
        ids_str = ", ".join(str(mid) for mid in deleted.message_ids)

        notification_text = (
            "<b>Зафиксировано удалённое сообщение!</b>\n\n"
            f"<b>ID чата:</b> {chat.id}\n"
            f"<b>Username:</b> {chat_username}\n"
            f"<b>Название:</b> {chat_title}\n\n"
            f"<b>ID удалённых сообщений:</b> {ids_str}\n\n"
            "<i>Содержимое удалённого сообщения недоступно: Telegram не передаёт текст удалённых сообщений.</i>"
        )

        await bot.send_message(
            chat_id=OWNER_ID,
            text=notification_text,
            parse_mode="HTML",
        )
        logger.info("✅ Уведомление об удалении отправлено владельцу")
    except Exception as e:
        logger.error("❌ Не удалось отправить уведомление об удалении: %s", e)


async def main() -> None:
    bot = Bot(token=BOT_TOKEN, request_timeout=60)
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
        logger.info("🚀 Запуск polling...")
        await dp.start_polling(
            bot,
            allowed_updates=[
                "business_message",
                "business_connection",
                "deleted_business_messages",
            ],
            polling_timeout=30,
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
