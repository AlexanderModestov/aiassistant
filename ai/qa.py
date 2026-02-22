import os
import logging
import time as _time
from dataclasses import dataclass
from datetime import date
from dotenv import load_dotenv
from anthropic import Anthropic
from queries.base import execute_query
from conversation import ConversationStore

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

SQL_SYSTEM_PROMPT = """Ты SQL-эксперт для аналитики образовательной платформы. База данных: ClickHouse.

{schema}

{examples}

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
- Если пользователь ссылается на предыдущий вопрос или запрос, используй контекст из истории диалога"""

ANSWER_SYSTEM_PROMPT = """Ты аналитик образовательной платформы.
Отвечай кратко и понятно на русском языке. Если данных нет или запрос не вернул результатов, скажи об этом.
Если пользователь ссылается на предыдущий вопрос, используй контекст из истории диалога."""


@dataclass
class QAResult:
    """Result of a Q&A exchange with metadata for logging."""
    answer: str
    success: bool = True
    generated_sql: str | None = None
    error_message: str | None = None
    sql_execution_time_ms: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0


def _build_sql_messages(exchanges: list[dict], question: str) -> list[dict]:
    """Build message history for SQL generation."""
    messages = []
    for ex in exchanges:
        messages.append({"role": "user", "content": ex["question"]})
        messages.append({"role": "assistant", "content": ex["sql"]})
    messages.append({"role": "user", "content": question})
    return messages


def _build_answer_messages(exchanges: list[dict], question: str, results_text: str) -> list[dict]:
    """Build message history for answer generation."""
    messages = []
    for ex in exchanges:
        messages.append({"role": "user", "content": ex["question"]})
        messages.append({"role": "assistant", "content": ex["answer"]})
    messages.append({"role": "user", "content": f"{question}\n\nРезультат запроса:\n{results_text}"})
    return messages


def answer_question(question: str, user_id: int, store: ConversationStore) -> QAResult:
    """Answer a user question about the data with conversation context."""
    exchanges = store.get_exchanges(user_id)

    # Step 1: Generate SQL query
    sql_system = SQL_SYSTEM_PROMPT.format(
        schema=DATABASE_SCHEMA,
        examples=SQL_EXAMPLES,
        today=date.today(),
    )
    sql_messages = _build_sql_messages(exchanges, question)

    query_response = _get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=sql_system,
        messages=sql_messages,
    )

    sql_query = query_response.content[0].text.strip()
    total_input = query_response.usage.input_tokens
    total_output = query_response.usage.output_tokens

    # Clean up query (remove markdown code blocks if present)
    if sql_query.startswith("```"):
        sql_query = sql_query.split("\n", 1)[1]
    if sql_query.endswith("```"):
        sql_query = sql_query.rsplit("```", 1)[0]
    sql_query = sql_query.strip()

    # Safety check
    sql_upper = sql_query.upper()
    if any(keyword in sql_upper for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"]):
        return QAResult(
            answer="❌ Извините, этот запрос не разрешён.",
            success=False,
            generated_sql=sql_query,
            error_message="Unsafe SQL keywords detected",
            input_tokens=total_input,
            output_tokens=total_output,
        )

    # Block UNION - causes type conflicts in ClickHouse
    if "UNION" in sql_upper:
        return QAResult(
            answer="❌ Задайте конкретный вопрос:\n• Сколько просмотров за неделю?\n• Топ 5 регионов\n• Средний результат по математике",
            success=False,
            generated_sql=sql_query,
            error_message="UNION queries not supported",
            input_tokens=total_input,
            output_tokens=total_output,
        )

    # Step 2: Execute query
    query_start = _time.monotonic()
    try:
        results = execute_query(sql_query)
        sql_execution_time_ms = int((_time.monotonic() - query_start) * 1000)
        logger.info(
            "Q&A Query executed | Question: %s | SQL: %s | Rows returned: %d",
            question,
            sql_query.replace("\n", " "),
            len(results),
        )
    except Exception as e:
        sql_execution_time_ms = int((_time.monotonic() - query_start) * 1000)
        logger.error(
            "Q&A Query failed | Question: %s | SQL: %s | Error: %s",
            question,
            sql_query.replace("\n", " "),
            str(e),
        )
        return QAResult(
            answer=f"❌ Ошибка выполнения запроса: {str(e)}",
            success=False,
            generated_sql=sql_query,
            error_message=str(e),
            sql_execution_time_ms=sql_execution_time_ms,
            input_tokens=total_input,
            output_tokens=total_output,
        )

    # Step 3: Generate answer
    results_text = str(results) if results else "Нет данных"
    answer_messages = _build_answer_messages(exchanges, question, results_text)

    answer_response = _get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=ANSWER_SYSTEM_PROMPT,
        messages=answer_messages,
    )

    answer = answer_response.content[0].text
    total_input += answer_response.usage.input_tokens
    total_output += answer_response.usage.output_tokens

    # Store the exchange for future context
    store.add_exchange(user_id, question, sql_query, answer)

    return QAResult(
        answer=answer,
        success=True,
        generated_sql=sql_query,
        sql_execution_time_ms=sql_execution_time_ms,
        input_tokens=total_input,
        output_tokens=total_output,
    )
