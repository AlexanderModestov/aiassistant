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
    level=logging.DEBUG,
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
