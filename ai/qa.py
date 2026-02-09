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
## Справочники и агрегаты

### school_stats — Агрегированная статистика по школам
| Колонка | Тип | Описание |
|---------|-----|----------|
| school | String | Идентификатор/название школы |
| school_registration_date | Date | Дата регистрации школы |

### school_stats_mv — Материализованное представление по школам
| Колонка | Тип | Описание |
|---------|-----|----------|
| school | String | Идентификатор/название школы |
| school_registration_date | Date | Дата регистрации школы |

### parallel_reg_stats — Статистика регистраций по параллелям
| Колонка | Тип | Описание |
|---------|-----|----------|
| school_parallel | String | Параллель (например: 5А, 6Б, 10В) |
| registration_date | Date | Дата регистрации |

### parallel_reg_mv — Материализованное представление параллелей
| Колонка | Тип | Описание |
|---------|-----|----------|
| school_parallel | String | Параллель |
| registration_date | Date | Дата регистрации |

## Факт-таблицы

### school_work — Учебная активность (просмотры)
| Колонка | Тип | Описание |
|---------|-----|----------|
| date | Date | Дата события |
| direction | String | Направление обучения |
| role | String | Роль: "Ученик" или "Учитель" |
| region | String | Регион РФ |
| municipality | String | Муниципалитет |
| school | String | Название школы |
| class | String | Класс |
| supplier | String | Поставщик/платформа |
| subject | String | Предмет |
| total_view | UInt32 | Количество просмотров |

### work_results_n — Результаты работ (основная таблица, ~1.4M строк)
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

### work_results_06 — Результаты работ (исторический срез)
Структура идентична work_results_n, используется для архивных/исторических данных.

## CRM-контур

### company_crm — Финансовые транзакции и CRM
| Колонка | Тип | Описание |
|---------|-----|----------|
| id | UInt32 | Уникальный ID |
| inn | String | ИНН клиента |
| title | String | Название компании/школы |
| name_transaction | String | Название транзакции |
| stage_transaction | String | Этап сделки: Новая, Отправить КП, ВКС, Ждем активности, Отказ, Партнеры |
| sum | Float64 | Сумма сделки |
| comment | String | Комментарий |
| uploaded_at | DateTime | Дата загрузки |
| reg_operator | String | Ответственный оператор |
"""

SQL_EXAMPLES = """
## Примеры SQL-запросов

-- Просмотры за день по ролям
SELECT role, sum(total_view) as views
FROM school_work
WHERE date = today()
GROUP BY role

-- Топ-10 регионов по активности
SELECT region, sum(total_view) as views, uniqExact(school) as schools
FROM school_work
WHERE date >= today() - 7
GROUP BY region
ORDER BY views DESC
LIMIT 10

-- Средний результат по предметам
SELECT subject, avg(result_percent) as avg_score, count() as works
FROM work_results_n
WHERE toDate(submission_date) = today()
GROUP BY subject
ORDER BY works DESC

-- Сравнение недель
SELECT toStartOfWeek(date) as week, sum(total_view) as views
FROM school_work
GROUP BY week
ORDER BY week DESC
LIMIT 4

-- Воронка CRM по этапам
SELECT stage_transaction, count() as deals, sum(sum) as total_sum
FROM company_crm
GROUP BY stage_transaction
ORDER BY deals DESC
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
- LIMIT до 20 строк
- Для подсчёта уникальных значений используй uniqExact()
- submission_date в work_results_n — это String, используй toDate(submission_date)
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
    results_text = str(results[:20]) if results else "Нет данных"

    answer_response = _get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": ANSWER_PROMPT.format(
            question=question,
            results=results_text,
        )}],
    )

    return answer_response.content[0].text
