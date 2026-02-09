# AI Analyst Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python application that sends daily growth insight reports via Telegram and supports interactive Q&A about educational platform data.

**Architecture:** Single Python process with APScheduler for daily jobs and python-telegram-bot for delivery. ClickHouse queries feed data to Claude API which generates natural language insights.

**Tech Stack:** Python 3.11+, clickhouse-connect, anthropic, python-telegram-bot, apscheduler, python-dotenv

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Modify: `.env` (update format)

**Step 1: Create requirements.txt**

```txt
clickhouse-connect==0.7.0
anthropic==0.39.0
python-telegram-bot==21.0
apscheduler==3.10.4
python-dotenv==1.0.0
```

**Step 2: Update .env with proper format**

```env
# ClickHouse
CLICKHOUSE_HOST=http://91.236.197.14:8123
CLICKHOUSE_DATABASE=cok_db
CLICKHOUSE_USER=clickhouse_admin
CLICKHOUSE_PASSWORD=et1aeh0EQu2johh2

# Telegram (user to fill)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Anthropic (user to fill)
ANTHROPIC_API_KEY=

# Schedule
REPORT_TIME=09:00
TIMEZONE=Europe/Moscow
```

**Step 3: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully

**Step 4: Commit**

```bash
git init
git add requirements.txt .env
git commit -m "chore: initial project setup with dependencies"
```

---

## Task 2: ClickHouse Connection

**Files:**
- Create: `queries/__init__.py`
- Create: `queries/base.py`

**Step 1: Create queries package**

Create empty `queries/__init__.py`:
```python
```

**Step 2: Write ClickHouse connection module**

Create `queries/base.py`:
```python
import os
from dotenv import load_dotenv
import clickhouse_connect

load_dotenv()


def get_client():
    """Create and return a ClickHouse client."""
    host = os.getenv("CLICKHOUSE_HOST", "http://localhost:8123")
    # Extract host and port from URL
    host_clean = host.replace("http://", "").replace("https://", "")
    if ":" in host_clean:
        host_part, port_part = host_clean.split(":")
        port = int(port_part)
    else:
        host_part = host_clean
        port = 8123

    return clickhouse_connect.get_client(
        host=host_part,
        port=port,
        database=os.getenv("CLICKHOUSE_DATABASE", "default"),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
    )


def execute_query(query: str) -> list[dict]:
    """Execute a query and return results as list of dicts."""
    client = get_client()
    result = client.query(query)
    columns = result.column_names
    rows = result.result_rows
    return [dict(zip(columns, row)) for row in rows]
```

**Step 3: Test connection manually**

Run: `python -c "from queries.base import execute_query; print(execute_query('SELECT 1 as test'))"`
Expected: `[{'test': 1}]`

**Step 4: Commit**

```bash
git add queries/
git commit -m "feat: add ClickHouse connection module"
```

---

## Task 3: Growth Queries

**Files:**
- Create: `queries/growth.py`

**Step 1: Write growth queries module**

Create `queries/growth.py`:
```python
from datetime import date, timedelta
from queries.base import execute_query


def get_daily_views(target_date: date) -> dict:
    """Get view counts for a specific date, broken down by role."""
    query = f"""
    SELECT
        role,
        sum(total_view) as views
    FROM school_work
    WHERE date = '{target_date}'
    GROUP BY role
    """
    results = execute_query(query)
    return {row["role"]: row["views"] for row in results}


def get_daily_submissions(target_date: date) -> int:
    """Get count of work submissions for a specific date."""
    query = f"""
    SELECT count() as cnt
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
    """
    results = execute_query(query)
    return results[0]["cnt"] if results else 0


def get_weekly_comparison() -> dict:
    """Compare this week vs last week metrics."""
    today = date.today()
    this_week_start = today - timedelta(days=today.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start - timedelta(days=1)

    query = f"""
    SELECT
        'this_week' as period,
        sum(total_view) as views,
        count(DISTINCT school) as active_schools
    FROM school_work
    WHERE date >= '{this_week_start}' AND date <= '{today}'

    UNION ALL

    SELECT
        'last_week' as period,
        sum(total_view) as views,
        count(DISTINCT school) as active_schools
    FROM school_work
    WHERE date >= '{last_week_start}' AND date <= '{last_week_end}'
    """
    results = execute_query(query)
    return {row["period"]: {"views": row["views"], "active_schools": row["active_schools"]} for row in results}


def get_top_regions(target_date: date, limit: int = 5) -> list[dict]:
    """Get top regions by activity for a specific date."""
    query = f"""
    SELECT
        region,
        sum(total_view) as views,
        count(DISTINCT school) as schools
    FROM school_work
    WHERE date = '{target_date}'
    GROUP BY region
    ORDER BY views DESC
    LIMIT {limit}
    """
    return execute_query(query)


def get_submission_stats(target_date: date) -> dict:
    """Get submission statistics for a specific date."""
    query = f"""
    SELECT
        count() as total_submissions,
        avg(result_percent) as avg_score,
        countIf(status = 'completed') as completed,
        count(DISTINCT region) as active_regions
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
    """
    results = execute_query(query)
    if results:
        return results[0]
    return {"total_submissions": 0, "avg_score": 0, "completed": 0, "active_regions": 0}


def get_all_daily_metrics(target_date: date = None) -> dict:
    """Collect all metrics for daily report."""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    previous_date = target_date - timedelta(days=1)

    return {
        "date": str(target_date),
        "views_today": get_daily_views(target_date),
        "views_yesterday": get_daily_views(previous_date),
        "submissions_today": get_daily_submissions(target_date),
        "submissions_yesterday": get_daily_submissions(previous_date),
        "weekly": get_weekly_comparison(),
        "top_regions": get_top_regions(target_date),
        "submission_stats": get_submission_stats(target_date),
    }
```

**Step 2: Test queries manually**

Run: `python -c "from queries.growth import get_all_daily_metrics; import json; print(json.dumps(get_all_daily_metrics(), indent=2, ensure_ascii=False, default=str))"`
Expected: JSON output with views, submissions, regions data

**Step 3: Commit**

```bash
git add queries/growth.py
git commit -m "feat: add growth metric queries"
```

---

## Task 4: AI Insights Module

**Files:**
- Create: `ai/__init__.py`
- Create: `ai/insights.py`

**Step 1: Create ai package**

Create empty `ai/__init__.py`:
```python
```

**Step 2: Write insights generation module**

Create `ai/insights.py`:
```python
import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

DAILY_REPORT_PROMPT = """Ты аналитик образовательной платформы в России.

Вот данные за {date}:

📊 ПРОСМОТРЫ:
- Сегодня: Ученики - {student_views}, Учителя - {teacher_views}
- Вчера: Ученики - {student_views_yesterday}, Учителя - {teacher_views_yesterday}

📝 СДАННЫЕ РАБОТЫ:
- Сегодня: {submissions_today}
- Вчера: {submissions_yesterday}
- Средний балл: {avg_score}%
- Завершено: {completed}

📈 НЕДЕЛЯ:
- Эта неделя: {this_week_views} просмотров, {this_week_schools} активных школ
- Прошлая неделя: {last_week_views} просмотров, {last_week_schools} активных школ

🏆 ТОП-5 РЕГИОНОВ:
{top_regions}

Напиши краткий отчёт для Telegram (3-5 пунктов):
1. Главные изменения по сравнению со вчера/прошлой неделей
2. Лучшие регионы
3. Аномалии, если есть
4. Одно полезное наблюдение

Формат:
📊 **Сводка за {date}**
[краткое резюме в 1-2 предложения]

📈 **Динамика**
[пункты об изменениях]

🏆 **Топ регионы**
[список]

💡 **Наблюдение**
[одна мысль]

Пиши кратко и по делу. Используй emoji умеренно.
"""


def generate_daily_report(metrics: dict) -> str:
    """Generate daily insight report from metrics."""
    # Extract data
    views_today = metrics.get("views_today", {})
    views_yesterday = metrics.get("views_yesterday", {})
    weekly = metrics.get("weekly", {})
    top_regions = metrics.get("top_regions", [])
    stats = metrics.get("submission_stats", {})

    # Format top regions
    regions_text = "\n".join(
        f"  {i+1}. {r['region']}: {r['views']} просмотров, {r['schools']} школ"
        for i, r in enumerate(top_regions)
    )

    # Build prompt
    prompt = DAILY_REPORT_PROMPT.format(
        date=metrics.get("date", ""),
        student_views=views_today.get("Ученик", 0),
        teacher_views=views_today.get("Учитель", 0),
        student_views_yesterday=views_yesterday.get("Ученик", 0),
        teacher_views_yesterday=views_yesterday.get("Учитель", 0),
        submissions_today=metrics.get("submissions_today", 0),
        submissions_yesterday=metrics.get("submissions_yesterday", 0),
        avg_score=round(stats.get("avg_score", 0) or 0, 1),
        completed=stats.get("completed", 0),
        this_week_views=weekly.get("this_week", {}).get("views", 0),
        this_week_schools=weekly.get("this_week", {}).get("active_schools", 0),
        last_week_views=weekly.get("last_week", {}).get("views", 0),
        last_week_schools=weekly.get("last_week", {}).get("active_schools", 0),
        top_regions=regions_text,
    )

    # Call Claude
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text
```

**Step 3: Test with mock data (no API call yet)**

Run: `python -c "from ai.insights import DAILY_REPORT_PROMPT; print('Prompt template loaded OK')"`
Expected: `Prompt template loaded OK`

**Step 4: Commit**

```bash
git add ai/
git commit -m "feat: add Claude insights generation module"
```

---

## Task 5: Telegram Bot

**Files:**
- Create: `bot/__init__.py`
- Create: `bot/telegram.py`

**Step 1: Create bot package**

Create empty `bot/__init__.py`:
```python
```

**Step 2: Write Telegram bot module**

Create `bot/telegram.py`:
```python
import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def send_report(application: Application, report: str) -> None:
    """Send a report to the configured chat."""
    if not CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID not configured")
        return

    await application.bot.send_message(
        chat_id=CHAT_ID,
        text=report,
        parse_mode="Markdown",
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"Привет! Я AI Analyst бот.\n\n"
        f"Ваш Chat ID: `{chat_id}`\n\n"
        f"Добавьте его в .env как TELEGRAM_CHAT_ID для получения отчётов.",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
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
    await update.message.reply_text("⏳ Генерирую отчёт...")

    try:
        from queries.growth import get_all_daily_metrics
        from ai.insights import generate_daily_report

        metrics = get_all_daily_metrics()
        report = generate_daily_report(metrics)
        await update.message.reply_text(report, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Error generating report")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-form questions (Phase 2)."""
    await update.message.reply_text(
        "🚧 Функция вопросов в разработке.\n"
        "Пока используйте /report для получения отчёта."
    )


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
```

**Step 3: Verify module loads**

Run: `python -c "from bot.telegram import create_application; print('Bot module loaded OK')"`
Expected: `Bot module loaded OK` (may warn about missing token, that's fine)

**Step 4: Commit**

```bash
git add bot/
git commit -m "feat: add Telegram bot module"
```

---

## Task 6: Main Entry Point with Scheduler

**Files:**
- Create: `main.py`

**Step 1: Write main entry point**

Create `main.py`:
```python
import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from bot.telegram import create_application, send_report
from queries.growth import get_all_daily_metrics
from ai.insights import generate_daily_report

load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def scheduled_report(application) -> None:
    """Generate and send the daily report."""
    logger.info("Starting scheduled report generation")
    try:
        metrics = get_all_daily_metrics()
        report = generate_daily_report(metrics)
        await send_report(application, report)
        logger.info("Daily report sent successfully")
    except Exception as e:
        logger.exception(f"Failed to generate/send report: {e}")


def main() -> None:
    """Main entry point."""
    # Parse schedule config
    report_time = os.getenv("REPORT_TIME", "09:00")
    timezone = os.getenv("TIMEZONE", "Europe/Moscow")
    hour, minute = map(int, report_time.split(":"))

    logger.info(f"Starting AI Analyst Bot")
    logger.info(f"Daily reports scheduled at {report_time} ({timezone})")

    # Create Telegram application
    application = create_application()

    # Set up scheduler
    scheduler = AsyncIOScheduler(timezone=pytz.timezone(timezone))
    scheduler.add_job(
        scheduled_report,
        CronTrigger(hour=hour, minute=minute),
        args=[application],
        id="daily_report",
        name="Daily Growth Report",
    )

    # Start scheduler and bot
    scheduler.start()
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
```

**Step 2: Add pytz to requirements**

Update `requirements.txt`:
```txt
clickhouse-connect==0.7.0
anthropic==0.39.0
python-telegram-bot==21.0
apscheduler==3.10.4
python-dotenv==1.0.0
pytz==2024.1
```

**Step 3: Install pytz**

Run: `pip install pytz==2024.1`
Expected: Successfully installed

**Step 4: Verify main loads**

Run: `python -c "import main; print('Main module loaded OK')"`
Expected: `Main module loaded OK` (may error on missing tokens, that's expected)

**Step 5: Commit**

```bash
git add main.py requirements.txt
git commit -m "feat: add main entry point with scheduler"
```

---

## Task 7: Integration Test

**Files:**
- None (manual testing)

**Step 1: Create Telegram bot**

1. Open Telegram and message @BotFather
2. Send `/newbot`
3. Follow prompts to name your bot
4. Copy the token to `.env` as `TELEGRAM_BOT_TOKEN`

**Step 2: Get your Chat ID**

1. Run: `python main.py`
2. In Telegram, send `/start` to your new bot
3. Bot will reply with your Chat ID
4. Copy it to `.env` as `TELEGRAM_CHAT_ID`
5. Stop the bot (Ctrl+C)

**Step 3: Add Anthropic API key**

1. Go to console.anthropic.com
2. Create or copy an API key
3. Add to `.env` as `ANTHROPIC_API_KEY`

**Step 4: Test full flow**

1. Run: `python main.py`
2. In Telegram, send `/report` to your bot
3. Bot should respond with a generated insight report

Expected: A formatted report in Russian with growth metrics

**Step 5: Commit**

```bash
git add .env
git commit -m "chore: configure bot tokens (gitignore sensitive data)"
```

---

## Task 8: Add .gitignore

**Files:**
- Create: `.gitignore`

**Step 1: Create .gitignore**

Create `.gitignore`:
```
# Environment
.env

# Python
__pycache__/
*.py[cod]
*$py.class
.Python
venv/
.venv/
env/

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore"
```

---

## Task 9: Phase 2 - Interactive Q&A

**Files:**
- Create: `ai/qa.py`
- Modify: `bot/telegram.py`

**Step 1: Create Q&A module**

Create `ai/qa.py`:
```python
import os
from dotenv import load_dotenv
from anthropic import Anthropic
from queries.base import execute_query

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

QUERY_SELECTION_PROMPT = """Ты помощник для анализа данных образовательной платформы.

Доступные таблицы:
1. school_work - активность (date, region, role, school, subject, total_view)
   - role: "Ученик" или "Учитель"
2. work_results_n - сданные работы (submission_date, region, school, student_id, result_percent, status)

Пользователь спрашивает: {question}

Напиши SELECT запрос для ClickHouse, который ответит на вопрос.
Правила:
- Только SELECT (никаких INSERT/UPDATE/DELETE)
- Используй актуальные даты (сегодня: {today})
- Лимитируй результаты до 20 строк
- Возвращай только SQL запрос, без пояснений

SQL:
"""

ANSWER_PROMPT = """Ты аналитик образовательной платформы.

Вопрос пользователя: {question}

Результат запроса:
{results}

Ответь кратко и понятно на русском языке. Если данных нет или запрос не вернул результатов, скажи об этом.
"""


def answer_question(question: str) -> str:
    """Answer a user question about the data."""
    from datetime import date

    # Step 1: Generate SQL query
    query_prompt = QUERY_SELECTION_PROMPT.format(
        question=question,
        today=date.today(),
    )

    query_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": query_prompt}],
    )

    sql_query = query_response.content[0].text.strip()

    # Clean up query (remove markdown code blocks if present)
    if sql_query.startswith("```"):
        sql_query = sql_query.split("\n", 1)[1]
    if sql_query.endswith("```"):
        sql_query = sql_query.rsplit("```", 1)[0]
    sql_query = sql_query.strip()

    # Safety check
    sql_upper = sql_query.upper()
    if any(keyword in sql_upper for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"]):
        return "❌ Извините, этот запрос не разрешён."

    # Step 2: Execute query
    try:
        results = execute_query(sql_query)
    except Exception as e:
        return f"❌ Ошибка выполнения запроса: {str(e)}"

    # Step 3: Generate answer
    results_text = str(results[:20]) if results else "Нет данных"

    answer_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": ANSWER_PROMPT.format(
            question=question,
            results=results_text,
        )}],
    )

    return answer_response.content[0].text
```

**Step 2: Update Telegram handler**

Modify `bot/telegram.py`, replace `handle_message` function:
```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-form questions."""
    question = update.message.text
    await update.message.reply_text("🤔 Думаю...")

    try:
        from ai.qa import answer_question
        answer = answer_question(question)
        await update.message.reply_text(answer, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Error answering question")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
```

**Step 3: Test Q&A**

1. Run: `python main.py`
2. In Telegram, ask: "Сколько просмотров было вчера?"
3. Bot should query data and respond with an answer

Expected: Natural language answer based on actual data

**Step 4: Commit**

```bash
git add ai/qa.py bot/telegram.py
git commit -m "feat: add interactive Q&A (Phase 2)"
```

---

## Summary

| Task | Description | Status |
|------|-------------|--------|
| 1 | Project setup | Pending |
| 2 | ClickHouse connection | Pending |
| 3 | Growth queries | Pending |
| 4 | AI insights module | Pending |
| 5 | Telegram bot | Pending |
| 6 | Main entry point | Pending |
| 7 | Integration test | Pending |
| 8 | Add .gitignore | Pending |
| 9 | Phase 2 - Q&A | Pending |

Total: 9 tasks

After completion, run `python main.py` to start the bot. It will:
- Send daily reports at 09:00 Moscow time
- Respond to /report for on-demand reports
- Answer questions about data in free-form
