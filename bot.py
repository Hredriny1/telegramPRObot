import logging
import os
from typing import Final

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes, MessageHandler, filters

load_dotenv()

BOT_TOKEN: Final[str] = os.getenv("BOT_TOKEN", "")
OWNER_ID: Final[int] = int(os.getenv("OWNER_ID", "0"))
PORT: Final[int] = int(os.getenv("PORT", "8080"))
WEBHOOK_URL: Final[str] = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_PATH: Final[str] = os.getenv("WEBHOOK_PATH", "/webhook")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Put it in .env or environment variables.")
if not OWNER_ID:
    raise RuntimeError("OWNER_ID is not set. Put your Telegram user ID in .env or environment variables.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def handle_business_secretary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает личные бизнес-сообщения от владельца аккаунта.

    Логика:
      - Если это сообщение от владельца и начинается с .me,
      - удаляем исходную команду через delete_business_messages,
      - сразу отвечаем в тот же чат от имени владельца через business_connection_id.
    """
    message = update.effective_message
    if message is None or message.from_user is None:
        return

    if message.from_user.id != OWNER_ID:
        logger.info("Ignoring message from user %s, expected %s", message.from_user.id, OWNER_ID)
        return

    text = message.text or ""
    if not text.startswith(".me"):
        logger.info("Ignoring non-command message from owner: %s", text)
        return

    business_connection_id = message.business_connection_id
    if not business_connection_id:
        logger.warning("Message from owner has no business_connection_id; cannot process.")
        return

    # Важно: для этого метода у бота должно быть право can_delete_all_messages.
    try:
        await context.bot.delete_business_messages(
            business_connection_id=business_connection_id,
            message_ids=[message.message_id],
        )
        logger.info(
            "Deleted .me command in business connection %s, message_id=%s",
            business_connection_id,
            message.message_id,
        )
    except Exception:
        logger.exception("Could not delete .me command. Check bot permissions and business connection settings.")

    # Для визуального центрирования в Telegram используем мягкий padding пробелами.
    # Это не настоящий центр, но создаёт эффект центрального блока.
    centered_text = " " * 12 + "*ОТВЕТ БЫЛ ЗАЦЕНТРИРОВАН И БЫЛ ТЕКСТ* ВСЕ РАБОТАЕТ"

    try:
        await context.bot.send_message(
            chat_id=message.chat_id,
            text=centered_text,
            business_connection_id=business_connection_id,
        )
        logger.info("Sent centered reply to business chat %s", message.chat_id)
    except Exception:
        logger.exception("Could not send centered reply via business_connection_id=%s", business_connection_id)


async def main() -> None:
    application: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    private_text_handler = MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE,
        handle_business_secretary,
    )
    application.add_handler(private_text_handler)

    if WEBHOOK_URL:
        await application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"{WEBHOOK_URL}{WEBHOOK_PATH}",
        )
    else:
        await application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
