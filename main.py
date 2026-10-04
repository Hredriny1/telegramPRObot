import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
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
        return

    if message.from_user.id != OWNER_ID:
        return

    text = message.text or ""
    if not text.startswith(".me"):
        return

    business_connection_id = message.business_connection_id
    if not business_connection_id:
        return

    # УДАЛЕНИЕ В ФОНЕ — не блокирует отправку ответа
    asyncio.create_task(
        bot.delete_business_messages(
            business_connection_id=business_connection_id,
            message_ids=[message.message_id],
        )
    )

    # СОБИРАЕМ ОТВЕТ
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

    # ОТПРАВЛЯЕМ ОТВЕТ СРАЗУ
    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text=response_text,
            parse_mode="HTML",
            business_connection_id=business_connection_id,
        )
        logger.info("✅ Ответ отправлен в чат: %s", message.chat.id)
    except Exception as e:
        logger.error("❌ Не удалось отправить ответ: %s", e)


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
