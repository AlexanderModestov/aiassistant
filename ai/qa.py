import os
import logging
from dotenv import load_dotenv
from anthropic import Anthropic
from queries.base import execute_query

load_dotenv()

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> Anthropic:
    """Lazy initialization of Anthropic client."""
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client

DATABASE_SCHEMA = """
## Таблица work_results_n — Результаты работ
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UInt64 | Уникальный ID |
| region | String | Регион |
| district | String | Район |
| school | String | Школа |
| class | String | Класс |
| class_teacher | String | Классный руководитель |
| student_id | String | ID ученика |
| student_full_name | String | ФИО ученика |
| role | String | Роль |
| subject | String | Предмет |
| parallel | String | Параллель (5, 6, 7...) |
| level | String | Уровень сложности |
| work_name | String | Название работы |
| work_id | String | ID работы |
| work_type | String | Тип: Самостоятельная работа, КИМ, Лабораторная работа, Интерактивная презентация |
| tasks_count | UInt32 | Количество заданий |
| result_percent | UInt32 | Процент выполнения (0-100) |
| time_spent | UInt32 | Время выполнения (секунды) |
| labor_intensity | UInt32 | Трудоёмкость |
| submission_date | String | Дата сдачи (YYYY-MM-DD) |
| start_date | Date | Дата начала |
| start_time | String | Время начала |
| end_date | Date | Дата окончания |
| status | String | Статус: Отправлено, На согласовании, Подозрительно, Отказ |
| id_registration | String | ID регистрации |
| id_order | String | ID заказа |
| inn | String | ИНН школы |
"""

SQL_EXAMPLES = """
## Примеры SQL-запросов

-- Средний результат по предметам
SELECT subject, avg(result_percent) as avg_score, count() as works
FROM work_results_n
WHERE toDate(submission_date) = today()
GROUP BY subject
ORDER BY works DESC

-- Топ-10 регионов по количеству работ
SELECT region, count() as works, avg(result_percent) as avg_score
FROM work_results_n
WHERE toDate(submission_date) >= today() - 7
GROUP BY region
ORDER BY works DESC
LIMIT 10

-- Статистика по типам работ
SELECT work_type, count() as works, avg(result_percent) as avg_score
FROM work_results_n
GROUP BY work_type
ORDER BY works DESC

-- Результаты по параллелям
SELECT parallel, count() as works, avg(result_percent) as avg_score
FROM work_results_n
WHERE toDate(submission_date) = today()
GROUP BY parallel
ORDER BY parallel

-- Количество работ по дням
SELECT toDate(submission_date) as date, count() as works
FROM work_results_n
WHERE toDate(submission_date) >= today() - 7
GROUP BY date
ORDER BY date DESC
"""

QUERY_SELECTION_PROMPT = """Ты SQL-эксперт для аналитики образовательной платформы. База данных: ClickHouse.

{schema}

{examples}

## Задача
Вопрос пользователя: {question}

Напиши SELECT запрос для ClickHouse.

## Правила
- Только SELECT (никаких INSERT/UPDATE/DELETE/DROP)
- Сегодня: {today}
- Используй today() для текущей даты
- Используй LIMIT при необходимости
- Для подсчёта уникальных значений используй uniqExact()
- submission_date в work_results_n — это String, используй toDate(submission_date)
- НЕ используй UNION ALL — делай простые запросы к одной таблице
- Используй ТОЛЬКО таблицу work_results_n
- Возвращай ТОЛЬКО SQL запрос, без пояснений и markdown

SQL:
"""

ANSWER_PROMPT = """Ты аналитик образовательной платформы.

Вопрос пользователя: {question}

Результат запроса:
{results}

Ответь кратко и понятно на русском языке. Если данных нет или запрос не вернул результатов, скажи об этом.
"""


def answer_question(question: str) -> str:
    """Answer a user question about the data."""
    from datetime import date

    # Step 1: Generate SQL query
    query_prompt = QUERY_SELECTION_PROMPT.format(
        schema=DATABASE_SCHEMA,
        examples=SQL_EXAMPLES,
        question=question,
        today=date.today(),
    )

    query_response = _get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": query_prompt}],
    )

    sql_query = query_response.content[0].text.strip()

    # Clean up query (remove markdown code blocks if present)
    if sql_query.startswith("```"):
        sql_query = sql_query.split("\n", 1)[1]
    if sql_query.endswith("```"):
        sql_query = sql_query.rsplit("```", 1)[0]
    sql_query = sql_query.strip()

    # Safety check
    sql_upper = sql_query.upper()
    if any(keyword in sql_upper for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"]):
        return "❌ Извините, этот запрос не разрешён."

    # Block UNION - causes type conflicts in ClickHouse
    if "UNION" in sql_upper:
        return "❌ Задайте конкретный вопрос:\n• Сколько просмотров за неделю?\n• Топ 5 регионов\n• Средний результат по математике"

    # Step 2: Execute query
    try:
        results = execute_query(sql_query)
        logger.info(
            "Q&A Query executed | Question: %s | SQL: %s | Rows returned: %d",
            question,
            sql_query.replace("\n", " "),
            len(results),
        )
    except Exception as e:
        logger.error(
            "Q&A Query failed | Question: %s | SQL: %s | Error: %s",
            question,
            sql_query.replace("\n", " "),
            str(e),
        )
        return f"❌ Ошибка выполнения запроса: {str(e)}"

    # Step 3: Generate answer
    results_text = str(results) if results else "Нет данных"

    answer_response = _get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": ANSWER_PROMPT.format(
            question=question,
            results=results_text,
        )}],
    )

    return answer_response.content[0].text
