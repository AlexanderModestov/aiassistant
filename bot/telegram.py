import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from conversation import ConversationStore

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Parse chat IDs from comma-separated list
_chat_ids_str = os.getenv("TELEGRAM_CHAT_ID", "")
CHAT_IDS: set[int] = set()
if _chat_ids_str.strip():
    CHAT_IDS = {int(cid.strip()) for cid in _chat_ids_str.split(",") if cid.strip()}

# Parse allowed users from comma-separated list
_allowed_users_str = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = set()
if _allowed_users_str.strip():
    ALLOWED_USERS = {int(uid.strip()) for uid in _allowed_users_str.split(",") if uid.strip()}

router = Router()
conversation_store = ConversationStore()


def is_user_allowed(user_id: int) -> bool:
    """Check if user is in the whitelist."""
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


async def safe_reply(message: Message, text: str) -> None:
    """Send message with Markdown, fallback to plain text if parsing fails."""
    try:
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.warning("Failed to send with Markdown: %s", e)
        await message.answer(text, parse_mode=None)


async def send_report(bot: Bot, report: str) -> None:
    """Send a report to all configured chats."""
    if not CHAT_IDS:
        logger.error("TELEGRAM_CHAT_ID not configured")
        return

    for chat_id in CHAT_IDS:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=report,
                parse_mode=ParseMode.MARKDOWN,
            )
            logger.info("Report sent to chat %s", chat_id)
        except Exception as e:
            if "parse" in str(e).lower():
                logger.warning("Markdown parsing failed for chat %s, sending as plain text", chat_id)
                await bot.send_message(chat_id=chat_id, text=report, parse_mode=None)
            else:
                logger.error("Failed to send report to chat %s: %s", chat_id, e)


@router.message(Command("start"))
async def start_command(message: Message) -> None:
    """Handle /start command."""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if is_user_allowed(user_id):
        await message.answer(
            f"Привет! Я AI Analyst бот.\n\n"
            f"Ваш User ID: `{user_id}`\n"
            f"Ваш Chat ID: `{chat_id}`\n\n"
            f"Добавьте Chat ID в .env как TELEGRAM_CHAT_ID для получения отчётов.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await message.answer(
            f"⛔ Доступ запрещён.\n\n"
            f"Ваш User ID: `{user_id}`\n\n"
            f"Обратитесь к администратору для получения доступа.",
            parse_mode=ParseMode.MARKDOWN,
        )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    """Handle /help command."""
    if not is_user_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    await message.answer(
        "📊 *AI Analyst Bot*\n\n"
        "Команды:\n"
        "/start - Получить Chat ID\n"
        "/report - Получить отчёт сейчас\n"
        "/clear - Сбросить контекст диалога\n"
        "/help - Эта справка\n\n"
        "Также вы можете задать вопрос о данных в свободной форме.\n"
        "Бот помнит контекст диалога для уточняющих вопросов.",
        parse_mode=ParseMode.MARKDOWN,
    )


@router.message(Command("clear"))
async def clear_command(message: Message) -> None:
    """Handle /clear command - reset conversation context."""
    if not is_user_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    conversation_store.clear(message.from_user.id)
    await message.answer("🔄 Контекст диалога сброшен.")


@router.message(Command("report"))
async def report_command(message: Message) -> None:
    """Handle /report command - generate report on demand."""
    logger.info("report_command called by user %s", message.from_user.id)

    if not is_user_allowed(message.from_user.id):
        logger.warning("User %s not allowed", message.from_user.id)
        await message.answer("⛔ Доступ запрещён.")
        return

    await message.answer("⏳ Генерирую отчёт...")
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

        await safe_reply(message, report)
        logger.info("Report sent successfully")
    except Exception as e:
        logger.exception("Error generating report: %s", e)
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(F.text)
async def handle_message(message: Message) -> None:
    """Handle free-form questions."""
    if not is_user_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    question = message.text
    await message.answer("🤔 Думаю...")

    try:
        from ai.qa import answer_question
        answer = answer_question(question, message.from_user.id, conversation_store)
        await safe_reply(message, answer)
    except Exception as e:
        logger.exception("Error answering question")
        await message.answer(f"❌ Ошибка: {str(e)}")


def create_bot() -> Bot:
    """Create the bot instance."""
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not configured in .env")
    return Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))


def create_dispatcher() -> Dispatcher:
    """Create and configure the dispatcher."""
    dp = Dispatcher()
    dp.include_router(router)
    return dp
