import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

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
    if message.from_user is None:
        return

    if message.from_user.id != OWNER_ID:
        logger.debug(
            "Игнорирую сообщение от пользователя %s, ожидается %s",
            message.from_user.id,
            OWNER_ID,
        )
        return

    text = message.text or ""
    if not text.startswith(".me"):
        logger.debug("Игнорирую сообщение без команды .me: %s", text[:100])
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
        logger.info(
            "✅ Удалено исходное сообщение .me, business_connection_id=%s, message_id=%s",
            business_connection_id,
            message.message_id,
        )
    except Exception as e:
        logger.warning("⚠️ Не удалось удалить исходное сообщение: %s", e)

    response_text = " " * 12 + "*ОТВЕТ БЫЛ ЗАЦЕНТРИРОВАН И БЫЛ ТЕКСТ* ВСЕ РАБОТАЕТ"

    try:
        await bot.send_message(
            chat_id=message.chat_id,
            text=response_text,
            business_connection_id=business_connection_id,
        )
        logger.info("✅ Ответ отправлен в тот же бизнес-чат: %s", message.chat_id)
    except Exception as e:
        logger.error("❌ Не удалось отправить ответ: %s", e)


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # ОБРАБОТЧИК ДЛЯ БИЗНЕС-СООБЩЕНИЙ - ЭТО ГЛАВНОЕ ИСПРАВЛЕНИЕ
    @dp.business_message()
    async def process_business_message(message: Message) -> None:
        logger.info("📩 Получено business_message от %s", message.from_user.id if message.from_user else "unknown")
        await handle_business_message(message, bot)

    # Старый обработчик для обычных личных сообщений (не business) - можно оставить
    @dp.message(F.chat.type == "private")
    async def process_private_message(message: Message) -> None:
        logger.debug("Обычное личное сообщение, не business")
        # Не обрабатываем, чтобы не мешать

    try:
        logger.info("🚀 Запуск polling...")
        # ЯВНО УКАЗЫВАЕМ allowed_updates - ВТОРОЕ ВАЖНОЕ ИСПРАВЛЕНИЕ
        await dp.start_polling(
            bot,
            allowed_updates=["business_message", "message"],
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
