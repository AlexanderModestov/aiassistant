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
