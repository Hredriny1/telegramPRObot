import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BusinessConnection, Update

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID_RAW = os.getenv("OWNER_ID", "").strip()

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
logger.info("=" * 70)


async def handle_business_message(message: Message, bot: Bot) -> None:
    if message.from_user is None:
        logger.warning("⚠️ from_user is None, пропускаю")
        return

    if message.from_user.id != OWNER_ID:
        logger.warning("⚠️ Сообщение от %s, ожидается %s. Пропускаю.",
                       message.from_user.id, OWNER_ID)
        return

    text = message.text or ""
    if not text.startswith(".me"):
        logger.info("ℹ️ Не команда .me: %r", text[:50])
        return

    business_connection_id = message.business_connection_id
    if not business_connection_id:
        logger.warning("⚠️ Нет business_connection_id, пропускаю.")
        return

    try:
        await bot.delete_business_messages(
            business_connection_id=business_connection_id,
            message_ids=[message.message_id],
        )
        logger.info("✅ Удалено сообщение .me, message_id=%s", message.message_id)
    except Exception as e:
        logger.warning("⚠️ Не удалось удалить сообщение: %s", e)

    response_text = " " * 12 + "*ОТВЕТ БЫЛ ЗАЦЕНТРИРОВАН И БЫЛ ТЕКСТ* ВСЕ РАБОТАЕТ"

    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text=response_text,
            business_connection_id=business_connection_id,
        )
        logger.info("✅ Ответ отправлен в чат: %s", message.chat.id)
    except Exception as e:
        logger.error("❌ Не удалось отправить ответ: %s", e)


async def main() -> None:
    bot = Bot(token=BOT_TOKEN, request_timeout=60)
    dp = Dispatcher()

    @dp.update()
    async def log_all_updates(update: Update) -> None:
        if update.business_connection:
            logger.info("🔗 business_connection: id=%s, user_id=%s, is_enabled=%s",
                        update.business_connection.id,
                        update.business_connection.user.id,
                        update.business_connection.is_enabled)
        if update.business_message:
            logger.info("📩 business_message: message_id=%s, from=%s, text=%r",
                        update.business_message.message_id,
                        update.business_message.from_user.id if update.business_message.from_user else "None",
                        (update.business_message.text or "")[:50])
        if update.deleted_business_messages:
            logger.info("🗑️ deleted_business_messages: connection_id=%s, chat_id=%s, message_ids=%s",
                        update.deleted_business_messages.business_connection_id,
                        update.deleted_business_messages.chat.id,
                        update.deleted_business_messages.message_ids)

    @dp.business_connection()
    async def on_business_connection(connection: BusinessConnection) -> None:
        logger.info("🔗 BUSINESS CONNECTION: id=%s, user_id=%s, is_enabled=%s",
                    connection.id, connection.user.id, connection.is_enabled)

    @dp.business_message()
    async def process_business_message(message: Message) -> None:
        logger.info("📩 ПОЛУЧЕНО business_message от %s",
                    message.from_user.id if message.from_user else "unknown")
        await handle_business_message(message, bot)

    @dp.message(F.chat.type == "private")
    async def process_private_message(message: Message) -> None:
        logger.info("✉️ Обычное личное сообщение от %s: %r",
                    message.from_user.id if message.from_user else "unknown",
                    (message.text or "")[:50])

    try:
        logger.info("🚀 Запуск polling...")
        await dp.start_polling(
            bot,
            allowed_updates=[
                "business_message",
                "message",
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
