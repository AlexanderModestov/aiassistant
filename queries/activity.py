from datetime import date, timedelta
from queries.base import execute_query


def get_last_available_date() -> date:
    """Get the most recent end_date in oblakoz_sending."""
    query = """
    SELECT max(end_date) as last_date
    FROM oblakoz_sending
    WHERE end_date IS NOT NULL
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
        uniqExact(s.user_id) as active_students,
        uniqExact(s.school_id) as active_schools,
        uniqExact(sch.region) as active_regions
    FROM oblakoz_sending s
    LEFT JOIN oblakoz_school sch ON s.school_id = sch.id
    WHERE s.end_date = '{target_date}'
    """
    results = execute_query(query)
    if results:
        return results[0]
    return {
        "total_submissions": 0, "active_students": 0,
        "active_schools": 0, "active_regions": 0,
    }


def get_weekly_submission_trend(target_date: date) -> list[dict]:
    """Daily submission counts for the current week (from Monday)."""
    start = target_date - timedelta(days=target_date.weekday())
    query = f"""
    SELECT
        end_date as day,
        count() as submissions,
        uniqExact(user_id) as students
    FROM oblakoz_sending
    WHERE end_date >= '{start}'
      AND end_date <= '{target_date}'
    GROUP BY day
    ORDER BY day
    """
    return execute_query(query)


def get_submissions_by_parallel(target_date: date) -> list[dict]:
    """Submission counts by grade for a specific date."""
    query = f"""
    SELECT
        grade,
        count() as submissions,
        uniqExact(user_id) as students
    FROM oblakoz_sending
    WHERE end_date = '{target_date}'
      AND grade != ''
    GROUP BY grade
    ORDER BY grade
    """
    return execute_query(query)


def get_top_active_regions(target_date: date, limit: int = 10) -> list[dict]:
    """Top regions by submission count for a specific date."""
    query = f"""
    SELECT
        sch.region as region,
        count() as submissions,
        uniqExact(s.school_id) as schools,
        uniqExact(s.user_id) as students
    FROM oblakoz_sending s
    INNER JOIN oblakoz_school sch ON s.school_id = sch.id
    WHERE s.end_date = '{target_date}'
      AND sch.region != ''
    GROUP BY sch.region
    ORDER BY submissions DESC
    LIMIT {limit}
    """
    return execute_query(query)


def get_top_active_schools(target_date: date, limit: int = 10) -> list[dict]:
    """Top schools by submission count for a specific date."""
    query = f"""
    SELECT
        sch.name as school,
        sch.region as region,
        count() as submissions,
        uniqExact(s.user_id) as students
    FROM oblakoz_sending s
    INNER JOIN oblakoz_school sch ON s.school_id = sch.id
    WHERE s.end_date = '{target_date}'
      AND sch.name != ''
    GROUP BY sch.name, sch.region
    ORDER BY submissions DESC
    LIMIT {limit}
    """
    return execute_query(query)


def get_weekly_comparison(target_date: date) -> dict:
    """Compare this week vs equivalent days of last week.

    If target_date is Wednesday, compares Mon-Wed this week
    with Mon-Wed last week (not the full last week).
    """
    this_week_start = target_date - timedelta(days=target_date.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = target_date - timedelta(days=7)

    query = f"""
    SELECT
        'this_week' as period,
        count() as submissions,
        uniqExact(school_id) as active_schools,
        uniqExact(user_id) as active_students
    FROM oblakoz_sending
    WHERE end_date >= '{this_week_start}'
      AND end_date <= '{target_date}'

    UNION ALL

    SELECT
        'last_week' as period,
        count() as submissions,
        uniqExact(school_id) as active_schools,
        uniqExact(user_id) as active_students
    FROM oblakoz_sending
    WHERE end_date >= '{last_week_start}'
      AND end_date <= '{last_week_end}'
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
        "top_schools": get_top_active_schools(target_date),
        "top_regions": get_top_active_regions(target_date),
    }
