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
