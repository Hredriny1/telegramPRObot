import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BusinessConnection, BusinessMessagesDeleted, Update

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID_RAW = os.getenv("OWNER_ID", "").strip()

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен. Установите переменную окружения BOT_TOKEN.")
    raise SystemExit(1)

if not OWNER_ID_RAW:
    logger.error("❌ OWNER_ID не установлен. Установите переменную окружения OWNER_ID.")
    raise SystemExit(1)

try:
    OWNER_ID = int(OWNER_ID_RAW)
except ValueError:
    logger.error("❌ OWNER_ID должен быть целым числом. Проверьте переменную окружения OWNER_ID.")
    raise SystemExit(1)

logger.info("=" * 70)
logger.info("🤖 Запуск Telegram бота в режиме long polling")
logger.info("BOT_TOKEN: %s", "***" + BOT_TOKEN[-4:] if len(BOT_TOKEN) > 4 else "***")
logger.info("OWNER_ID: %s", OWNER_ID)
logger.info("=" * 70)


async def handle_business_message(message: Message, bot: Bot) -> None:
    logger.info("🔍 handle_business_message вызван для message_id=%s", message.message_id)
    logger.info("   from_user.id=%s (ожидается %s)", 
                message.from_user.id if message.from_user else "None", OWNER_ID)
    logger.info("   chat.id=%s, chat.type=%s", message.chat.id, message.chat.type)
    logger.info("   business_connection_id=%s", message.business_connection_id)
    logger.info("   text=%r", (message.text or "")[:100])

    if message.from_user is None:
        logger.warning("⚠️ from_user is None, пропускаю")
        return

    if message.from_user.id != OWNER_ID:
        logger.warning("⚠️ Сообщение от %s, а ожидается %s. Пропускаю.",
                       message.from_user.id, OWNER_ID)
        return

    text = message.text or ""
    if not text.startswith(".me"):
        logger.info("ℹ️ Сообщение не начинается с .me: %r", text[:50])
        return

    business_connection_id = message.business_connection_id
    if not business_connection_id:
        logger.warning("⚠️ У сообщения нет business_connection_id, обработка невозможна.")
        return

    try:
        await bot.delete_business_messages(
            business_connection_id=business_connection_id,
            message_ids=[message.message_id],
        )
        logger.info("✅ Удалено исходное сообщение .me, message_id=%s", message.message_id)
    except Exception as e:
        logger.warning("⚠️ Не удалось удалить исходное сообщение: %s", e)

    response_text = " " * 12 + "*ОТВЕТ БЫЛ ЗАЦЕНТРИРОВАН И БЫЛ ТЕКСТ* ВСЕ РАБОТАЕТ"

    try:
        await bot.send_message(
            chat_id=message.chat.id,  # ← ИСПРАВЛЕНО: chat.id вместо chat_id
            text=response_text,
            business_connection_id=business_connection_id,
        )
        logger.info("✅ Ответ отправлен в тот же бизнес-чат: %s", message.chat.id)
    except Exception as e:
        logger.error("❌ Не удалось отправить ответ: %s", e)


async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        request_timeout=60,  # ← ИСПРАВЛЕНО: таймаут 60 сек
    )
    dp = Dispatcher()

    @dp.update()
    async def log_all_updates(update: Update) -> None:
        logger.info("📥 Получен апдейт: update_id=%s", update.update_id)
        if update.business_connection:
            logger.info("   🔗 business_connection: id=%s, user_id=%s, is_enabled=%s",
                        update.business_connection.id,
                        update.business_connection.user.id,
                        update.business_connection.is_enabled)
        if update.business_message:
            logger.info("   💬 business_message: message_id=%s, from=%s, text=%r",
                        update.business_message.message_id,
                        update.business_message.from_user.id if update.business_message.from_user else "None",
                        (update.business_message.text or "")[:50])
        if update.message:
            logger.info("   ✉️ message: message_id=%s, chat.type=%s",
                        update.message.message_id,
                        update.message.chat.type)

    @dp.business_connection()
    async def on_business_connection(connection: BusinessConnection) -> None:
        logger.info("🔗 BUSINESS CONNECTION: id=%s, user_id=%s, is_enabled=%s, rights=%s",
                    connection.id, connection.user.id,
                    connection.is_enabled, connection.rights)

    @dp.business_messages_deleted()
    async def on_business_messages_deleted(deleted: BusinessMessagesDeleted) -> None:
        logger.info("🗑️ BUSINESS MESSAGES DELETED: connection_id=%s, chat_id=%s, message_ids=%s",
                    deleted.business_connection_id, deleted.chat.id, deleted.message_ids)

    @dp.business_message()
    async def process_business_message(message: Message) -> None:
        logger.info("📩 ПОЛУЧЕНО business_message от %s", 
                    message.from_user.id if message.from_user else "unknown")
        await handle_business_message(message, bot)

    @dp.message(F.chat.type == "private")
    async def process_private_message(message: Message) -> None:
        logger.info("✉️ Обычное личное сообщение (не business) от %s: %r",
                    message.from_user.id if message.from_user else "unknown",
                    (message.text or "")[:50])

    try:
        logger.info("🚀 Запуск polling...")
        logger.info("📋 Разрешённые типы апдейтов: business_message, message, business_connection, business_messages_deleted")
        await dp.start_polling(
            bot,
            allowed_updates=[
                "business_message",
                "message",
                "business_connection",
                "business_messages_deleted",
            ],
            polling_timeout=30,  # ← ИСПРАВЛЕНО: таймаут getUpdates 30 сек
        )
    except asyncio.CancelledError:
        logger.info("🛑 Polling был отменён.")
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
