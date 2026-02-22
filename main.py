import os
import asyncio
import logging
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from bot.telegram import create_bot, create_dispatcher, send_report
from queries.activity import get_all_activity_metrics
from ai.insights import generate_activity_report

load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)


async def scheduled_report(bot) -> None:
    """Generate and send the daily activity report."""
    logger.info("Starting scheduled report generation")
    try:
        metrics = get_all_activity_metrics()
        report = generate_activity_report(metrics)
        await send_report(bot, report)
        logger.info("Activity report sent successfully")
    except Exception as e:
        logger.exception(f"Failed to generate/send report: {e}")


async def main() -> None:
    """Main entry point."""
    # Parse schedule config
    report_time = os.getenv("REPORT_TIME", "09:00")
    timezone = os.getenv("TIMEZONE", "Europe/Moscow")
    hour, minute = map(int, report_time.split(":"))

    logger.info("Starting AI Analyst Bot")
    logger.info(f"Daily report scheduled at {report_time} ({timezone})")

    # Create bot and dispatcher
    bot = create_bot()
    dp = create_dispatcher()

    # Set up scheduler
    scheduler = AsyncIOScheduler(timezone=pytz.timezone(timezone))
    scheduler.add_job(
        scheduled_report,
        CronTrigger(hour=hour, minute=minute),
        args=[bot],
        id="daily_report",
        name="Daily Activity Report",
    )
    scheduler.start()

    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
