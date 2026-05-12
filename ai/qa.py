import logging
import time as _time
from dataclasses import dataclass
from datetime import date
from queries.base import execute_query
from conversation import ConversationStore
from ai.client import chat

logger = logging.getLogger(__name__)

DATABASE_SCHEMA = """
## Таблица oblakoz_sending — Отправки работ (факты)
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UInt32 | Уникальный ID отправки |
| registration | String | ID регистрации |
| user_id | String | ID пользователя (ученика) |
| role | String | Роль (Ученик / Учитель) |
| school_id | UInt32 | ID школы → JOIN с oblakoz_school.id |
| grade | String | Параллель / класс (5, 6, 7, ...) |
| order_id | String | ID заказа |
| result | UInt32 | Процент выполнения (0-100) |
| duration | UInt32 | Время выполнения (секунды) |
| start_date | Nullable(Date) | Дата начала |
| start_time | Nullable(String) | Время начала |
| end_date | Nullable(Date) | Дата окончания (используется как дата сдачи) |
| end_time | Nullable(String) | Время окончания |

## Таблица oblakoz_school — Справочник школ
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UInt32 | ID школы |
| inn | String | ИНН |
| name | String | Название школы |
| region | String | Регион |
| municipality | String | Муниципалитет |

## Таблица oblakoz_content — Контент / работы
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UInt32 | ID контента |
| title | String | Название работы |
| tasks_amount | UInt32 | Количество заданий |
| duration | UInt32 | Длительность |
| genre | String | Жанр / тип контента |
| subject | String | Предмет |
| grade | String | Параллель |
| level | String | Уровень сложности |

## Таблица oblakoz_sending_module — Модули отправки
| Колонка | Тип | Описание |
|---------|-----|----------|
| sending_id | UInt32 | ID отправки → oblakoz_sending.id |
| module | UInt32 | Код модуля |

## Таблица oblakoz_content_module — Модули контента
| Колонка | Тип | Описание |
|---------|-----|----------|
| content_id | UInt32 | ID контента → oblakoz_content.id |
| module | UInt32 | Код модуля |

## Связи
- oblakoz_sending.school_id = oblakoz_school.id — атрибуты школы (регион, муниципалитет, ИНН, название)
- oblakoz_sending → oblakoz_sending_module (по sending_id) → oblakoz_content_module (по module) → oblakoz_content (по content_id) — атрибуты работы (subject, level, title, genre, tasks_amount)
"""

SQL_EXAMPLES = """
## Примеры SQL-запросов

-- Количество работ за сегодня
SELECT count() as works, uniqExact(user_id) as students
FROM oblakoz_sending
WHERE end_date = today()

-- Топ-10 регионов по количеству работ
SELECT sch.region as region, count() as works, avg(s.result) as avg_score
FROM oblakoz_sending s
INNER JOIN oblakoz_school sch ON s.school_id = sch.id
WHERE s.end_date >= today() - 7
GROUP BY sch.region
ORDER BY works DESC
LIMIT 10

-- Топ-10 школ за неделю
SELECT sch.name as school, sch.region as region, count() as works
FROM oblakoz_sending s
INNER JOIN oblakoz_school sch ON s.school_id = sch.id
WHERE s.end_date >= today() - 7
GROUP BY sch.name, sch.region
ORDER BY works DESC
LIMIT 10

-- Результаты по параллелям
SELECT grade, count() as works, avg(result) as avg_score
FROM oblakoz_sending
WHERE end_date = today()
  AND grade != ''
GROUP BY grade
ORDER BY grade

-- Количество работ по дням
SELECT end_date as date, count() as works
FROM oblakoz_sending
WHERE end_date >= today() - 7
GROUP BY date
ORDER BY date DESC

-- Средний результат по предметам (JOIN sending → content через модуль)
SELECT c.subject as subject, count() as works, avg(s.result) as avg_score
FROM oblakoz_sending s
INNER JOIN oblakoz_sending_module sm ON s.id = sm.sending_id
INNER JOIN oblakoz_content_module cm ON sm.module = cm.module
INNER JOIN oblakoz_content c ON cm.content_id = c.id
WHERE s.end_date = today()
GROUP BY c.subject
ORDER BY works DESC

-- Среднее время выполнения (в минутах) по школам
SELECT sch.name as school, round(avg(s.duration) / 60) as avg_minutes, count() as works
FROM oblakoz_sending s
INNER JOIN oblakoz_school sch ON s.school_id = sch.id
WHERE s.end_date = today()
GROUP BY sch.name
ORDER BY works DESC
LIMIT 10
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
- Используй ТОЛЬКО таблицы oblakoz_*: oblakoz_sending, oblakoz_school, oblakoz_content, oblakoz_sending_module, oblakoz_content_module
- За «дату сдачи / выполнения работы» считай end_date в oblakoz_sending (тип Nullable(Date), можно сравнивать напрямую: end_date = '2026-05-01')
- Для атрибутов школы (region, municipality, name, inn) делай JOIN: oblakoz_sending s JOIN oblakoz_school sch ON s.school_id = sch.id
- Для атрибутов работы (subject, level, title, genre, tasks_amount) делай JOIN через модуль: s → oblakoz_sending_module sm (s.id = sm.sending_id) → oblakoz_content_module cm (sm.module = cm.module) → oblakoz_content c (cm.content_id = c.id)
- Параллель/класс ученика — это поле grade в oblakoz_sending (НЕ путать с oblakoz_content.grade, которое относится к контенту)
- Процент выполнения — это поле result в oblakoz_sending
- Время выполнения (duration) хранится в секундах — при выводе пользователю конвертируй в минуты (duration / 60), округляй до целого
- НЕ используй UNION ALL — делай простые запросы
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

    query_response = chat(messages=sql_messages, system=sql_system, max_tokens=500)

    sql_query = query_response.text.strip()
    total_input = query_response.input_tokens
    total_output = query_response.output_tokens

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

    # Auto-add LIMIT to prevent huge result sets
    if "LIMIT" not in sql_upper:
        sql_query = sql_query.rstrip(";") + " LIMIT 100"

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

    # Step 3: Generate answer (truncate large result sets to stay within token limits)
    MAX_ROWS = 100
    if not results:
        results_text = "Нет данных"
    elif len(results) > MAX_ROWS:
        results_text = (
            str(results[:MAX_ROWS])
            + f"\n... (показано {MAX_ROWS} из {len(results)} строк)"
        )
    else:
        results_text = str(results)
    # Hard cap on character length (~50K chars ≈ ~15K tokens)
    if len(results_text) > 50_000:
        results_text = results_text[:50_000] + "\n... (результат обрезан)"
    answer_messages = _build_answer_messages(exchanges, question, results_text)

    answer_response = chat(messages=answer_messages, system=ANSWER_SYSTEM_PROMPT)

    answer = answer_response.text
    total_input += answer_response.input_tokens
    total_output += answer_response.output_tokens

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
