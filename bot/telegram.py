import os
import logging
from datetime import datetime, timedelta, timezone
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

# Parse admin users from comma-separated list
_admin_users_str = os.getenv("ADMIN_USERS", "")
ADMIN_USERS: set[int] = set()
if _admin_users_str.strip():
    ADMIN_USERS = {int(uid.strip()) for uid in _admin_users_str.split(",") if uid.strip()}

router = Router()
conversation_store = ConversationStore()


def is_user_allowed(user_id: int) -> bool:
    """Check if user is in the whitelist."""
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


def is_admin(user_id: int) -> bool:
    """Check if user is an admin."""
    return user_id in ADMIN_USERS


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
        "/report - Отчёт по активности\n"
        "/clear - Сбросить контекст диалога\n"
        "/stat - Статистика использования (админ)\n"
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


@router.message(Command("stat"))
async def stat_command(message: Message) -> None:
    """Handle /stat command - show usage statistics (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён. Команда доступна только администраторам.")
        return

    # Parse days argument: /stat 7 for 7 days, /stat 0 for all time, default 30
    args = message.text.split()
    days = 30
    if len(args) > 1:
        try:
            days = int(args[1])
        except ValueError:
            await message.answer(
                "❌ Использование: /stat [дни]\n"
                "Пример: /stat 7 — за 7 дней, /stat 0 — за всё время"
            )
            return

    if days < 0:
        await message.answer("❌ Количество дней не может быть отрицательным.")
        return

    await message.answer("📊 Загружаю статистику...")

    try:
        from supabase_client import get_qa_stats

        since_iso = None
        if days > 0:
            since_dt = datetime.now(timezone.utc) - timedelta(days=days)
            since_iso = since_dt.isoformat()

        rows = get_qa_stats(since_iso=since_iso)

        if not rows:
            period_text = f"за {days} дн." if days > 0 else "за всё время"
            await message.answer(f"📊 Нет данных {period_text}.")
            return

        # Aggregate per user
        user_stats: dict[int, dict] = {}
        for row in rows:
            uid = row["telegram_user_id"]
            if uid not in user_stats:
                user_stats[uid] = {
                    "username": row.get("telegram_username") or str(uid),
                    "count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "questions": [],
                }
            user_stats[uid]["count"] += 1
            user_stats[uid]["input_tokens"] += row.get("input_tokens") or 0
            user_stats[uid]["output_tokens"] += row.get("output_tokens") or 0
            q = row.get("question")
            if q:
                user_stats[uid]["questions"].append(q)

        # Sort by total tokens descending
        sorted_users = sorted(
            user_stats.values(),
            key=lambda u: u["input_tokens"] + u["output_tokens"],
            reverse=True,
        )

        # Build response
        period_text = f"за {days} дн." if days > 0 else "за всё время"
        lines = [f"📊 *Статистика использования* ({period_text})\n"]

        total_count = 0
        total_input = 0
        total_output = 0

        for u in sorted_users:
            total_count += u["count"]
            total_input += u["input_tokens"]
            total_output += u["output_tokens"]
            questions_list = "\n".join(
                f"   • {q}" for q in u["questions"]
            )
            lines.append(
                f"👤 *{u['username']}*\n"
                f"   Запросов: {u['count']}\n"
                f"{questions_list}\n"
                f"   Токены (входящие/исходящие): {u['input_tokens']:,} / {u['output_tokens']:,}\n"
            )

        lines.append(
            f"📈 *Итого:* {total_count} запросов, "
            f"токены: {total_input:,} / {total_output:,}"
        )

        await safe_reply(message, "\n".join(lines))

    except Exception as e:
        logger.exception("Error fetching stats: %s", e)
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(Command("report"))
async def report_command(message: Message) -> None:
    """Handle /report command - generate activity report on demand."""
    logger.info("report_command called by user %s", message.from_user.id)

    if not is_user_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    await message.answer("⏳ Генерирую отчёт по активности...")

    try:
        from queries.activity import get_all_activity_metrics
        from ai.insights import generate_activity_report

        metrics = get_all_activity_metrics()
        report = generate_activity_report(metrics)
        await safe_reply(message, report)
        logger.info("Activity report sent successfully")
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
        from supabase_client import log_qa_exchange

        result = answer_question(question, message.from_user.id, conversation_store)
        await safe_reply(message, result.answer)

        log_qa_exchange(
            telegram_user_id=message.from_user.id,
            telegram_username=message.from_user.username,
            question=question,
            generated_sql=result.generated_sql,
            answer=result.answer,
            success=result.success,
            error_message=result.error_message,
            sql_execution_time_ms=result.sql_execution_time_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
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
