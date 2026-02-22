from datetime import date, timedelta
from queries.base import execute_query


def get_last_available_date() -> date:
    """Get the most recent submission date in work_results_n."""
    query = """
    SELECT max(toDate(submission_date)) as last_date
    FROM work_results_n
    WHERE submission_date IS NOT NULL AND submission_date != ''
    """
    results = execute_query(query)
    if results and results[0]["last_date"]:
        last_date = results[0]["last_date"]
        if isinstance(last_date, date):
            return last_date
        return date.fromisoformat(str(last_date))
    return date.today() - timedelta(days=1)


def get_daily_activity(target_date: date) -> dict:
    """Core activity counts for a specific date."""
    query = f"""
    SELECT
        count() as total_submissions,
        count(DISTINCT student_id) as active_students,
        count(DISTINCT school) as active_schools,
        count(DISTINCT region) as active_regions
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
    """
    results = execute_query(query)
    if results:
        return results[0]
    return {
        "total_submissions": 0, "active_students": 0,
        "active_schools": 0, "active_regions": 0,
    }


def get_weekly_submission_trend(target_date: date) -> list[dict]:
    """Daily submission counts for the last 7 days."""
    start = target_date - timedelta(days=6)
    query = f"""
    SELECT
        toDate(submission_date) as day,
        count() as submissions,
        count(DISTINCT student_id) as students
    FROM work_results_n
    WHERE toDate(submission_date) >= '{start}'
      AND toDate(submission_date) <= '{target_date}'
    GROUP BY day
    ORDER BY day
    """
    return execute_query(query)


def get_submissions_by_parallel(target_date: date) -> list[dict]:
    """Submission counts by grade level (parallel) for a specific date."""
    query = f"""
    SELECT
        parallel,
        count() as submissions,
        count(DISTINCT student_id) as students
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
      AND parallel != ''
    GROUP BY parallel
    ORDER BY parallel
    """
    return execute_query(query)


def get_submissions_by_work_type(target_date: date) -> list[dict]:
    """Submission counts by work type for a specific date."""
    query = f"""
    SELECT
        work_type,
        count() as submissions,
        round(avg(result_percent), 1) as avg_score
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
      AND work_type != ''
    GROUP BY work_type
    ORDER BY submissions DESC
    """
    return execute_query(query)


def get_top_active_regions(target_date: date, limit: int = 10) -> list[dict]:
    """Top regions by submission count for a specific date."""
    query = f"""
    SELECT
        region,
        count() as submissions,
        count(DISTINCT school) as schools,
        count(DISTINCT student_id) as students
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
      AND region != ''
    GROUP BY region
    ORDER BY submissions DESC
    LIMIT {limit}
    """
    return execute_query(query)


def get_status_breakdown(target_date: date) -> list[dict]:
    """Submission status breakdown for a specific date."""
    query = f"""
    SELECT
        status,
        count() as cnt
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
      AND status != ''
    GROUP BY status
    ORDER BY cnt DESC
    """
    return execute_query(query)


def get_weekly_comparison(target_date: date) -> dict:
    """Compare this week vs last week submission metrics."""
    this_week_start = target_date - timedelta(days=target_date.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start - timedelta(days=1)

    query = f"""
    SELECT
        'this_week' as period,
        count() as submissions,
        count(DISTINCT school) as active_schools,
        count(DISTINCT student_id) as active_students
    FROM work_results_n
    WHERE toDate(submission_date) >= '{this_week_start}'
      AND toDate(submission_date) <= '{target_date}'

    UNION ALL

    SELECT
        'last_week' as period,
        count() as submissions,
        count(DISTINCT school) as active_schools,
        count(DISTINCT student_id) as active_students
    FROM work_results_n
    WHERE toDate(submission_date) >= '{last_week_start}'
      AND toDate(submission_date) <= '{last_week_end}'
    """
    results = execute_query(query)
    data = {}
    for row in results:
        period = row["period"]
        data[period] = {
            "submissions": row["submissions"],
            "active_schools": row["active_schools"],
            "active_students": row["active_students"],
            "start_date": str(this_week_start if period == "this_week" else last_week_start),
            "end_date": str(target_date if period == "this_week" else last_week_end),
        }
    return data


def get_all_activity_metrics(target_date: date = None) -> dict:
    """Collect all activity/engagement metrics.

    Defaults to yesterday since today's data is incomplete.
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    previous_date = target_date - timedelta(days=1)

    return {
        "date": str(target_date),
        "activity_today": get_daily_activity(target_date),
        "activity_yesterday": get_daily_activity(previous_date),
        "weekly_trend": get_weekly_submission_trend(target_date),
        "weekly_comparison": get_weekly_comparison(target_date),
        "by_parallel": get_submissions_by_parallel(target_date),
        "by_work_type": get_submissions_by_work_type(target_date),
        "top_regions": get_top_active_regions(target_date),
        "status_breakdown": get_status_breakdown(target_date),
    }
