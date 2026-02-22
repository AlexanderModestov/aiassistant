import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

_client = None


def _get_client() -> Anthropic:
    """Lazy initialization of Anthropic client."""
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client

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
- Эта неделя ({this_week_dates}): {this_week_views} просмотров, {this_week_schools} активных школ
- Прошлая неделя ({last_week_dates}): {last_week_views} просмотров, {last_week_schools} активных школ

🏆 ТОП-5 РЕГИОНОВ:
{top_regions}

Напиши краткий отчёт для Telegram (3-5 пунктов):
1. Главные изменения по сравнению со вчера/прошлой неделей
2. Лучшие регионы
3. Аномалии, если есть
4. Одно полезное наблюдение

ВАЖНО: Всегда указывай точные даты в ответе (за какой день/период данные).

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

    # Build week date ranges
    this_week = weekly.get("this_week", {})
    last_week = weekly.get("last_week", {})
    this_week_dates = f"{this_week.get('start_date', '?')} — {this_week.get('end_date', '?')}"
    last_week_dates = f"{last_week.get('start_date', '?')} — {last_week.get('end_date', '?')}"

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
        this_week_views=this_week.get("views", 0),
        this_week_schools=this_week.get("active_schools", 0),
        this_week_dates=this_week_dates,
        last_week_views=last_week.get("views", 0),
        last_week_schools=last_week.get("active_schools", 0),
        last_week_dates=last_week_dates,
        top_regions=regions_text,
    )

    # Call Claude
    message = _get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


PERFORMANCE_REPORT_PROMPT = """Ты аналитик образовательной платформы в России.

Вот данные об академической успеваемости за {date}:

📊 ОБЩАЯ СТАТИСТИКА:
- Сегодня: {total_submissions} работ, средний балл {avg_score}%, медиана {median_score}%
- Активных: {active_regions} регионов, {active_schools} школ, {active_students} учеников
- Вчера: {total_submissions_yesterday} работ, средний балл {avg_score_yesterday}%

📈 РАСПРЕДЕЛЕНИЕ БАЛЛОВ:
{score_distribution}

🏆 ТОП РЕГИОНОВ ПО УСПЕВАЕМОСТИ:
{top_regions}

📉 ОТСТАЮЩИЕ РЕГИОНЫ:
{bottom_regions}

📚 УСПЕВАЕМОСТЬ ПО ПРЕДМЕТАМ:
{by_subject}

🎓 УСПЕВАЕМОСТЬ ПО КЛАССАМ (параллелям):
{by_parallel}

Напиши краткий аналитический отчёт для Telegram (4-6 пунктов):
1. Общая картина успеваемости и изменения по сравнению со вчера
2. Распределение баллов — есть ли перекос
3. Лучшие и отстающие регионы
4. Какие предметы даются лучше/хуже
5. Разница между классами
6. Аномалии или важные наблюдения

ВАЖНО: Всегда указывай точные даты.

Формат:
📊 **Успеваемость за {date}**
[краткое резюме в 1-2 предложения]

📈 **Распределение баллов**
[анализ]

🏆 **Лидеры и отстающие**
[регионы]

📚 **По предметам**
[анализ]

🎓 **По классам**
[анализ]

💡 **Наблюдение**
[одна ключевая мысль]

Пиши кратко и по делу. Используй emoji умеренно.
"""

ACTIVITY_REPORT_PROMPT = """Ты аналитик образовательной платформы в России.

Вот данные об активности и вовлечённости за {date}:

📊 АКТИВНОСТЬ СЕГОДНЯ:
- Сдано работ: {submissions_today}
- Активных учеников: {students_today}
- Активных школ: {schools_today}
- Активных регионов: {regions_today}

📊 АКТИВНОСТЬ ВЧЕРА:
- Сдано работ: {submissions_yesterday}
- Активных учеников: {students_yesterday}
- Активных школ: {schools_yesterday}
- Активных регионов: {regions_yesterday}

📈 ТРЕНД ЗА НЕДЕЛЮ (по дням):
{weekly_trend}

📈 НЕДЕЛЯ vs ПРОШЛАЯ НЕДЕЛЯ:
- Эта неделя ({this_week_dates}): {this_week_submissions} работ, {this_week_schools} школ, {this_week_students} учеников
- Прошлая неделя ({last_week_dates}): {last_week_submissions} работ, {last_week_schools} школ, {last_week_students} учеников

🎓 ПО КЛАССАМ (параллелям):
{by_parallel}

📝 ПО ТИПАМ РАБОТ:
{by_work_type}

🏆 ТОП РЕГИОНОВ ПО АКТИВНОСТИ:
{top_regions}

📋 СТАТУСЫ РАБОТ:
{status_breakdown}

Напиши краткий аналитический отчёт для Telegram (4-6 пунктов):
1. Динамика активности по сравнению со вчера и прошлой неделей
2. Тренд за неделю — рост или падение
3. Какие классы наиболее активны
4. Популярные типы работ
5. Самые активные регионы
6. Аномалии или важные наблюдения

ВАЖНО: Всегда указывай точные даты.

Формат:
📊 **Активность за {date}**
[краткое резюме в 1-2 предложения]

📈 **Динамика**
[сравнение со вчера и прошлой неделей]

📅 **Тренд недели**
[анализ по дням]

🎓 **По классам и типам**
[анализ]

🏆 **Топ регионы**
[список]

💡 **Наблюдение**
[одна ключевая мысль]

Пиши кратко и по делу. Используй emoji умеренно.
"""


def generate_performance_report(metrics: dict) -> str:
    """Generate academic performance report from metrics."""
    overall = metrics.get("overall_today", {})
    overall_yesterday = metrics.get("overall_yesterday", {})

    # Format score distribution
    dist_text = "\n".join(
        f"  {d['score_range']}%: {d['cnt']} работ"
        for d in metrics.get("score_distribution", [])
    )

    # Format top regions
    top_text = "\n".join(
        f"  {i+1}. {r['region']}: {r['avg_score']}% (n={r['submissions']})"
        for i, r in enumerate(metrics.get("top_regions", []))
    )

    # Format bottom regions
    bottom_text = "\n".join(
        f"  {i+1}. {r['region']}: {r['avg_score']}% (n={r['submissions']})"
        for i, r in enumerate(metrics.get("bottom_regions", []))
    )

    # Format by subject
    subject_text = "\n".join(
        f"  {s['subject']}: {s['avg_score']}% ({s['submissions']} работ)"
        for s in metrics.get("by_subject", [])
    )

    # Format by parallel
    parallel_text = "\n".join(
        f"  {p['parallel']} класс: {p['avg_score']}% ({p['submissions']} работ)"
        for p in metrics.get("by_parallel", [])
    )

    prompt = PERFORMANCE_REPORT_PROMPT.format(
        date=metrics.get("date", ""),
        total_submissions=overall.get("total_submissions", 0),
        avg_score=overall.get("avg_score", 0),
        median_score=overall.get("median_score", 0),
        active_regions=overall.get("active_regions", 0),
        active_schools=overall.get("active_schools", 0),
        active_students=overall.get("active_students", 0),
        total_submissions_yesterday=overall_yesterday.get("total_submissions", 0),
        avg_score_yesterday=overall_yesterday.get("avg_score", 0),
        score_distribution=dist_text or "  Нет данных",
        top_regions=top_text or "  Нет данных",
        bottom_regions=bottom_text or "  Нет данных",
        by_subject=subject_text or "  Нет данных",
        by_parallel=parallel_text or "  Нет данных",
    )

    message = _get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def generate_activity_report(metrics: dict) -> str:
    """Generate activity/engagement report from metrics."""
    today = metrics.get("activity_today", {})
    yesterday = metrics.get("activity_yesterday", {})
    weekly = metrics.get("weekly_comparison", {})
    this_week = weekly.get("this_week", {})
    last_week = weekly.get("last_week", {})

    # Format weekly trend
    trend_text = "\n".join(
        f"  {d['day']}: {d['submissions']} работ, {d['students']} учеников"
        for d in metrics.get("weekly_trend", [])
    )

    # Format by parallel
    parallel_text = "\n".join(
        f"  {p['parallel']} класс: {p['submissions']} работ, {p['students']} учеников"
        for p in metrics.get("by_parallel", [])
    )

    # Format by work type
    wt_text = "\n".join(
        f"  {w['work_type']}: {w['submissions']} работ (ср. балл {w['avg_score']}%)"
        for w in metrics.get("by_work_type", [])
    )

    # Format top regions
    regions_text = "\n".join(
        f"  {i+1}. {r['region']}: {r['submissions']} работ, {r['schools']} школ, {r['students']} учеников"
        for i, r in enumerate(metrics.get("top_regions", []))
    )

    # Format status breakdown
    status_text = "\n".join(
        f"  {s['status']}: {s['cnt']}"
        for s in metrics.get("status_breakdown", [])
    )

    this_week_dates = f"{this_week.get('start_date', '?')} — {this_week.get('end_date', '?')}"
    last_week_dates = f"{last_week.get('start_date', '?')} — {last_week.get('end_date', '?')}"

    prompt = ACTIVITY_REPORT_PROMPT.format(
        date=metrics.get("date", ""),
        submissions_today=today.get("total_submissions", 0),
        students_today=today.get("active_students", 0),
        schools_today=today.get("active_schools", 0),
        regions_today=today.get("active_regions", 0),
        submissions_yesterday=yesterday.get("total_submissions", 0),
        students_yesterday=yesterday.get("active_students", 0),
        schools_yesterday=yesterday.get("active_schools", 0),
        regions_yesterday=yesterday.get("active_regions", 0),
        weekly_trend=trend_text or "  Нет данных",
        this_week_dates=this_week_dates,
        this_week_submissions=this_week.get("submissions", 0),
        this_week_schools=this_week.get("active_schools", 0),
        this_week_students=this_week.get("active_students", 0),
        last_week_dates=last_week_dates,
        last_week_submissions=last_week.get("submissions", 0),
        last_week_schools=last_week.get("active_schools", 0),
        last_week_students=last_week.get("active_students", 0),
        by_parallel=parallel_text or "  Нет данных",
        by_work_type=wt_text or "  Нет данных",
        top_regions=regions_text or "  Нет данных",
        status_breakdown=status_text or "  Нет данных",
    )

    message = _get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text
