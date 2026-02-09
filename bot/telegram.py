import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

logger = logging.getLogger(__name__)


async def safe_reply(message, text: str) -> None:
    """Send message with Markdown, fallback to plain text if parsing fails."""
    try:
        logger.debug("Attempting to send with Markdown...")
        await message.reply_text(text, parse_mode="Markdown")
        logger.debug("Sent with Markdown successfully")
    except Exception as e:
        logger.warning("Failed to send with Markdown: %s", e)
        if "parse entities" in str(e).lower() or "can't parse" in str(e).lower():
            logger.info("Retrying without Markdown...")
            await message.reply_text(text)
            logger.info("Sent as plain text")
        else:
            raise

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Parse allowed users from comma-separated list
_allowed_users_str = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = set()
if _allowed_users_str.strip():
    ALLOWED_USERS = {int(uid.strip()) for uid in _allowed_users_str.split(",") if uid.strip()}


def is_user_allowed(user_id: int) -> bool:
    """Check if user is in the whitelist."""
    if not ALLOWED_USERS:
        # If no whitelist configured, allow all (for initial setup)
        return True
    return user_id in ALLOWED_USERS


async def send_report(application: Application, report: str) -> None:
    """Send a report to the configured chat."""
    if not CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID not configured")
        return

    try:
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text=report,
            parse_mode="Markdown",
        )
    except Exception as e:
        if "parse entities" in str(e).lower() or "can't parse" in str(e).lower():
            logger.warning("Markdown parsing failed in send_report, sending as plain text: %s", e)
            await application.bot.send_message(chat_id=CHAT_ID, text=report)
        else:
            raise


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if is_user_allowed(user_id):
        await update.message.reply_text(
            f"Привет! Я AI Analyst бот.\n\n"
            f"Ваш User ID: `{user_id}`\n"
            f"Ваш Chat ID: `{chat_id}`\n\n"
            f"Добавьте Chat ID в .env как TELEGRAM_CHAT_ID для получения отчётов.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"⛔ Доступ запрещён.\n\n"
            f"Ваш User ID: `{user_id}`\n\n"
            f"Обратитесь к администратору для получения доступа.",
            parse_mode="Markdown",
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not is_user_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    await update.message.reply_text(
        "📊 **AI Analyst Bot**\n\n"
        "Команды:\n"
        "/start - Получить Chat ID\n"
        "/report - Получить отчёт сейчас\n"
        "/help - Эта справка\n\n"
        "Также вы можете задать вопрос о данных в свободной форме.",
        parse_mode="Markdown",
    )


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /report command - generate report on demand."""
    logger.info("report_command called by user %s", update.effective_user.id)

    if not is_user_allowed(update.effective_user.id):
        logger.warning("User %s not allowed", update.effective_user.id)
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    await update.message.reply_text("⏳ Генерирую отчёт...")
    logger.info("Fetching metrics...")

    try:
        from queries.growth import get_all_daily_metrics
        from ai.insights import generate_daily_report

        logger.info("Calling get_all_daily_metrics...")
        metrics = get_all_daily_metrics()
        logger.info("Metrics received: %s", list(metrics.keys()))

        logger.info("Generating report with AI...")
        report = generate_daily_report(metrics)
        logger.info("Report generated, length: %d chars", len(report))

        await safe_reply(update.message, report)
        logger.info("Report sent successfully")
    except Exception as e:
        logger.exception("Error generating report: %s", e)
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-form questions."""
    if not is_user_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    question = update.message.text
    await update.message.reply_text("🤔 Думаю...")

    try:
        from ai.qa import answer_question
        answer = answer_question(question)
        await safe_reply(update.message, answer)
    except Exception as e:
        logger.exception("Error answering question")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


def create_application() -> Application:
    """Create and configure the Telegram application."""
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not configured in .env")

    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return application
