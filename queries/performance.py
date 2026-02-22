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


def get_avg_score_by_region(target_date: date, limit: int = 10) -> list[dict]:
    """Top regions by average score for a specific date."""
    query = f"""
    SELECT
        region,
        round(avg(result_percent), 1) as avg_score,
        count() as submissions
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
      AND region != ''
    GROUP BY region
    HAVING submissions >= 10
    ORDER BY avg_score DESC
    LIMIT {limit}
    """
    return execute_query(query)


def get_bottom_regions(target_date: date, limit: int = 5) -> list[dict]:
    """Bottom regions by average score for a specific date."""
    query = f"""
    SELECT
        region,
        round(avg(result_percent), 1) as avg_score,
        count() as submissions
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
      AND region != ''
    GROUP BY region
    HAVING submissions >= 10
    ORDER BY avg_score ASC
    LIMIT {limit}
    """
    return execute_query(query)


def get_score_distribution(target_date: date) -> list[dict]:
    """Score distribution in buckets for a specific date."""
    query = f"""
    SELECT
        multiIf(
            result_percent < 20, '0-19',
            result_percent < 40, '20-39',
            result_percent < 60, '40-59',
            result_percent < 80, '60-79',
            '80-100'
        ) as score_range,
        count() as cnt
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
    GROUP BY score_range
    ORDER BY score_range
    """
    return execute_query(query)


def get_performance_by_subject(target_date: date, limit: int = 10) -> list[dict]:
    """Average score and count by subject for a specific date."""
    query = f"""
    SELECT
        subject,
        round(avg(result_percent), 1) as avg_score,
        count() as submissions
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
      AND subject != ''
    GROUP BY subject
    ORDER BY submissions DESC
    LIMIT {limit}
    """
    return execute_query(query)


def get_performance_by_parallel(target_date: date) -> list[dict]:
    """Average score by grade level (parallel) for a specific date."""
    query = f"""
    SELECT
        parallel,
        round(avg(result_percent), 1) as avg_score,
        count() as submissions
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
      AND parallel != ''
    GROUP BY parallel
    ORDER BY parallel
    """
    return execute_query(query)


def get_overall_stats(target_date: date) -> dict:
    """Overall performance stats for a specific date."""
    query = f"""
    SELECT
        count() as total_submissions,
        round(avg(result_percent), 1) as avg_score,
        round(median(result_percent), 1) as median_score,
        min(result_percent) as min_score,
        max(result_percent) as max_score,
        count(DISTINCT region) as active_regions,
        count(DISTINCT school) as active_schools,
        count(DISTINCT student_id) as active_students
    FROM work_results_n
    WHERE toDate(submission_date) = '{target_date}'
    """
    results = execute_query(query)
    if results:
        return results[0]
    return {
        "total_submissions": 0, "avg_score": 0, "median_score": 0,
        "min_score": 0, "max_score": 0, "active_regions": 0,
        "active_schools": 0, "active_students": 0,
    }


def get_all_performance_metrics(target_date: date = None) -> dict:
    """Collect all academic performance metrics.

    Defaults to yesterday since today's data is incomplete.
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    previous_date = target_date - timedelta(days=1)

    return {
        "date": str(target_date),
        "overall_today": get_overall_stats(target_date),
        "overall_yesterday": get_overall_stats(previous_date),
        "top_regions": get_avg_score_by_region(target_date),
        "bottom_regions": get_bottom_regions(target_date),
        "score_distribution": get_score_distribution(target_date),
        "by_subject": get_performance_by_subject(target_date),
        "by_parallel": get_performance_by_parallel(target_date),
    }
