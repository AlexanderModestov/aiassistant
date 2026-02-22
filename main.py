import os
import asyncio
import logging
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from bot.telegram import create_bot, create_dispatcher, send_report
from queries.growth import get_all_daily_metrics
from queries.activity import get_all_activity_metrics
from ai.insights import generate_daily_report, generate_activity_report

load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)


async def scheduled_report(bot) -> None:
    """Generate and send the daily report."""
    logger.info("Starting scheduled report generation")
    try:
        metrics = get_all_daily_metrics()
        report = generate_daily_report(metrics)
        await send_report(bot, report)
        logger.info("Daily report sent successfully")
    except Exception as e:
        logger.exception(f"Failed to generate/send report: {e}")


async def scheduled_activity_report(bot) -> None:
    """Generate and send the daily activity report."""
    logger.info("Starting scheduled activity report generation")
    try:
        metrics = get_all_activity_metrics()
        report = generate_activity_report(metrics)
        await send_report(bot, report)
        logger.info("Activity report sent successfully")
    except Exception as e:
        logger.exception(f"Failed to generate/send activity report: {e}")


async def main() -> None:
    """Main entry point."""
    # Parse schedule config
    report_time = os.getenv("REPORT_TIME", "09:00")
    timezone = os.getenv("TIMEZONE", "Europe/Moscow")
    hour, minute = map(int, report_time.split(":"))
    activity_hour, activity_minute = divmod(hour * 60 + minute + 5, 60)

    logger.info("Starting AI Analyst Bot")
    logger.info(f"Daily reports scheduled at {report_time} ({timezone})")
    logger.info(f"Activity report scheduled at {activity_hour:02d}:{activity_minute:02d}")

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
        name="Daily Growth Report",
    )
    scheduler.add_job(
        scheduled_activity_report,
        CronTrigger(hour=activity_hour, minute=activity_minute),
        args=[bot],
        id="daily_activity_report",
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
