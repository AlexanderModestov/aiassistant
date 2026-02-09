from datetime import date, timedelta
from queries.base import execute_query


def get_last_available_date() -> date:
    """Get the most recent date with data in school_work table."""
    query = """
    SELECT max(date) as last_date
    FROM school_work
    """
    results = execute_query(query)
    if results and results[0]["last_date"]:
        last_date = results[0]["last_date"]
        # Handle if it's already a date object or string
        if isinstance(last_date, date):
            return last_date
        return date.fromisoformat(str(last_date))
    # Fallback to yesterday if no data
    return date.today() - timedelta(days=1)


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
    """Compare this week vs last week metrics.

    Note: Only uses fully loaded data (up to yesterday).
    """
    yesterday = date.today() - timedelta(days=1)
    this_week_start = yesterday - timedelta(days=yesterday.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start - timedelta(days=1)

    query = f"""
    SELECT
        'this_week' as period,
        sum(total_view) as views,
        count(DISTINCT school) as active_schools
    FROM school_work
    WHERE date >= '{this_week_start}' AND date <= '{yesterday}'

    UNION ALL

    SELECT
        'last_week' as period,
        sum(total_view) as views,
        count(DISTINCT school) as active_schools
    FROM school_work
    WHERE date >= '{last_week_start}' AND date <= '{last_week_end}'
    """
    results = execute_query(query)
    return {
        row["period"]: {
            "views": row["views"],
            "active_schools": row["active_schools"],
            "start_date": str(this_week_start if row["period"] == "this_week" else last_week_start),
            "end_date": str(yesterday if row["period"] == "this_week" else last_week_end),
        }
        for row in results
    }


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
    """Collect all metrics for daily report.

    Uses the last available date in the database if target_date is not specified.
    """
    if target_date is None:
        target_date = get_last_available_date()

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
