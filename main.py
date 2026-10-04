import asyncio
import logging
import os
import sys
from typing import Final

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message

# ============================================================================
# Конфигурация логирования
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ============================================================================
# Переменные окружения
# ============================================================================
BOT_TOKEN: Final[str] = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID_STR: Final[str] = os.getenv("OWNER_ID", "").strip()

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен. Установите переменную окружения BOT_TOKEN")
    sys.exit(1)

if not OWNER_ID_STR:
    logger.error("❌ OWNER_ID не установлен. Установите переменную окружения OWNER_ID")
    sys.exit(1)

try:
    OWNER_ID: Final[int] = int(OWNER_ID_STR)
except ValueError:
    logger.error("❌ OWNER_ID должно быть числом. Получено значение: %s", OWNER_ID_STR)
    sys.exit(1)

logger.info("=" * 70)
logger.info("🤖 Запуск Telegram бота (long polling mode)")
logger.info("BOT_TOKEN: %s", "***" + BOT_TOKEN[-4:] if len(BOT_TOKEN) > 4 else "***")
logger.info("OWNER_ID: %d", OWNER_ID)
logger.info("=" * 70)

# ============================================================================
# Обработчики сообщений
# ============================================================================


async def handle_business_message(message: Message, bot: Bot) -> None:
    """Обрабатывает сообщения из личных чатов (.me команда)."""

    # Проверка: сообщение от владельца
    if message.from_user.id != OWNER_ID:
        logger.debug(
            "Сообщение от пользователя %d, ожидается %d. Игнорирую.",
            message.from_user.id,
            OWNER_ID,
        )
        return

    # Проверка: текст есть
    text = message.text or ""
    if not text.startswith(".me"):
        logger.debug(
            "Сообщение от владельца без команды .me: %s...",
            text[:50],
        )
        return

    # Проверка: есть business_connection_id
    business_connection_id = message.business_connection_id
    if not business_connection_id:
        logger.warning(
            "⚠️ Сообщение от владельца без business_connection_id. Сообщение: %s",
            text[:100],
        )
        return

    logger.info(
        "📨 Получена команда .me от владельца. "
        "business_connection_id=%s, message_id=%d",
        business_connection_id,
        message.message_id,
    )

    # Попытка удалить исходное сообщение
    try:
        await bot.delete_business_messages(
            business_connection_id=business_connection_id,
            message_ids=[message.message_id],
        )
        logger.info(
            "✅ Удалено исходное сообщение .me. message_id=%d",
            message.message_id,
        )
    except Exception as e:
        logger.warning(
            "⚠️ Не удалось удалить сообщение .me: %s",
            e,
        )

    # Формируем ответ
    response_text = " " * 12 + "*ОТВЕТ БЫЛ ЗАЦЕНТРИРОВАН И БЫЛ ТЕКСТ* ВСЕ РАБОТАЕТ"

    # Отправляем ответ
    try:
        await bot.send_message(
            chat_id=message.chat_id,
            text=response_text,
            business_connection_id=business_connection_id,
        )
        logger.info(
            "✅ Отправлен ответ в чат %d",
            message.chat_id,
        )
    except Exception as e:
        logger.error(
            "❌ Не удалось отправить ответ: %s",
            e,
        )


# ============================================================================
# Главная функция
# ============================================================================


async def main() -> None:
    """Запуск бота в режиме long polling."""

    # Инициализация бота и dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Регистрируем обработчик для всех текстовых сообщений из личных чатов
    @dp.message(F.chat.type == "private")
    async def process_private_message(message: Message) -> None:
        await handle_business_message(message, bot)

    logger.info("🚀 Запуск long polling...")
    logger.info("Бот готов принимать сообщения")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            skip_updates=False,
        )
    except asyncio.CancelledError:
        logger.info("🛑 Polling отменён")
        raise
    except Exception as e:
        logger.error("❌ Ошибка в polling: %s", e, exc_info=True)
        raise
    finally:
        await bot.session.close()
        logger.info("🛑 Бот остановлен")


# ============================================================================
# Точка входа
# ============================================================================


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.critical("💥 Критическая ошибка: %s", e, exc_info=True)
        sys.exit(1)
