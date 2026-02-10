# ClickHouse Database Schema

**Database:** `cok_db`

**Host:** `http://91.236.197.14:8123`

---

## Логическая структура

```
┌─────────────────────────────────────────────────────────────┐
│                    СПРАВОЧНИКИ / АГРЕГАТЫ                   │
├─────────────────────────────────────────────────────────────┤
│  school_stats          │  school_stats_mv                   │
│  parallel_reg_stats    │  parallel_reg_mv                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       ФАКТ-ТАБЛИЦЫ                          │
├─────────────────────────────────────────────────────────────┤
│  school_work           │  Учебная активность (просмотры)    │
│  work_results_n        │  Результаты работ (основная)       │
│  work_results_06       │  Результаты работ (архив)          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      CRM-КОНТУР                             │
├─────────────────────────────────────────────────────────────┤
│  company_crm           │  Финансовые транзакции             │
└─────────────────────────────────────────────────────────────┘
```

---

## Tables Overview

| Table | Description | Row Count | Доступна для запросов |
|-------|-------------|-----------|----------------------|
| `school_work` | Учебная активность (просмотры) | 567,937 | ✅ Да |
| `work_results_n` | Результаты работ (основная) | 1,372,247 | ✅ Да |
| `work_results_06` | Результаты работ (архив) | 91,349 | ✅ Да |
| `company_crm` | CRM данные и транзакции | 7,637 | ✅ Да |
| `school_stats` | Агрегат по школам | - | ❌ AggregatingMergeTree |
| `school_stats_mv` | MV по школам | - | ❌ AggregatingMergeTree |
| `parallel_reg_stats` | Агрегат по параллелям | - | ❌ AggregatingMergeTree |
| `parallel_reg_mv` | MV по параллелям | - | ❌ AggregatingMergeTree |

> **Примечание:** Таблицы с `AggregatingMergeTree` используют агрегатные функции и не подходят для прямых запросов через text-to-sql.

---

## Факт-таблицы

### Table: `school_work`

Учебная активность — просмотры по ученикам и учителям.

**Date Range:** 2026-01-01 to present

| Column | Type | Description |
|--------|------|-------------|
| `date` | Date | Дата события |
| `direction` | String | Направление обучения |
| `role` | String | Роль пользователя |
| `region` | String | Регион РФ |
| `municipality` | String | Муниципалитет |
| `school` | String | Название школы |
| `class` | String | Класс |
| `supplier` | String | Поставщик/платформа |
| `subject` | String | Предмет |
| `total_view` | UInt32 | Количество просмотров |

**Role Values:**
- `Ученик` — Student
- `Учитель` — Teacher

---

### Table: `work_results_n`

Результаты выполнения работ учениками (основная таблица).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UInt64 | Уникальный идентификатор |
| `region` | String | Регион |
| `district` | String | Район |
| `school` | String | Школа |
| `class` | String | Класс |
| `class_teacher` | String | Классный руководитель |
| `student_id` | String | ID ученика |
| `student_full_name` | String | ФИО ученика |
| `role` | String | Роль |
| `subject` | String | Предмет |
| `parallel` | String | Параллель (5, 6, 7, 8, 9, 10, 11) |
| `level` | String | Уровень сложности |
| `work_name` | String | Название работы |
| `work_id` | String | ID работы |
| `work_type` | String | Тип работы |
| `tasks_count` | UInt32 | Количество заданий |
| `result_percent` | UInt32 | Процент выполнения (0-100) |
| `time_spent` | UInt32 | Время выполнения (секунды) |
| `labor_intensity` | UInt32 | Трудоёмкость |
| `submission_date` | Nullable(String) | Дата сдачи (YYYY-MM-DD) |
| `start_date` | Nullable(Date) | Дата начала |
| `start_time` | Nullable(String) | Время начала |
| `end_date` | Nullable(Date) | Дата окончания |
| `status` | String | Статус |
| `id_registration` | String | ID регистрации |
| `id_order` | String | ID заказа |
| `inn` | String | ИНН школы |

**Work Types:**
- `Самостоятельная работа` — Independent work
- `КИМ` — Control measurement materials
- `Интерактивная презентация` — Interactive presentation
- `Лабораторная работа` — Laboratory work
- `Опорный конспект` — Reference notes

**Status Values:**
- `Отправлено` — Submitted
- `На согласовании` — Under review
- `Подозрительно` — Suspicious
- `Отказ` — Rejected

---

### Table: `work_results_06`

Исторические результаты работ (архивный срез).

Структура идентична `work_results_n`, но с non-nullable датами.
Используется для исторических/архивных данных.

---

## CRM-контур

### Table: `company_crm`

CRM данные — транзакции и этапы сделок.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UInt32 | Уникальный ID |
| `inn` | String | ИНН клиента |
| `title` | String | Название компании/школы |
| `name_transaction` | String | Название транзакции |
| `stage_transaction` | String | Этап сделки |
| `sum` | Float64 | Сумма сделки |
| `comment` | String | Комментарий |
| `reg_operator` | String | Ответственный оператор |
| `uploaded_at` | DateTime | Дата загрузки |

**Transaction Stages:**
- `Новая` — New
- `Отправить КП` — Send commercial offer
- `ВКС` — Video conference
- `Ждем активности` — Waiting for activity
- `Изучают материалы` — Studying materials
- `Недозвон ЦОК` — No answer
- `Отказ` — Rejected
- `Партнеры` — Partners
- `Малочисленные школы` — Small schools
- `База на обзвон` — Call list

---

## Common Queries

### Просмотры за день по ролям
```sql
SELECT role, sum(total_view) as views
FROM school_work
WHERE date = today()
GROUP BY role
```

### Топ-10 регионов по активности
```sql
SELECT region, sum(total_view) as views, uniqExact(school) as schools
FROM school_work
WHERE date >= today() - 7
GROUP BY region
ORDER BY views DESC
LIMIT 10
```

### Средний результат по предметам
```sql
SELECT subject, avg(result_percent) as avg_score, count() as works
FROM work_results_n
WHERE toDate(submission_date) = today()
GROUP BY subject
ORDER BY works DESC
```

### Недельное сравнение
```sql
SELECT toStartOfWeek(date) as week, sum(total_view) as views
FROM school_work
GROUP BY week
ORDER BY week DESC
LIMIT 4
```

### Воронка CRM по этапам
```sql
SELECT stage_transaction, count() as deals, sum(sum) as total_sum
FROM company_crm
GROUP BY stage_transaction
ORDER BY deals DESC
```

### Связка учебной активности с CRM (по ИНН)
```sql
SELECT
    c.title,
    c.stage_transaction,
    c.sum,
    count(w.id) as works_count,
    avg(w.result_percent) as avg_result
FROM company_crm c
LEFT JOIN work_results_n w ON c.inn = w.inn
GROUP BY c.title, c.stage_transaction, c.sum
ORDER BY works_count DESC
LIMIT 20
```

---

## Типовые сценарии использования

1. **Анализ активности** — просмотры по регионам, школам, предметам
2. **Результаты работ** — процент выполнения, время, трудоёмкость
3. **Сравнение школ и регионов** — динамика, топы, отстающие
4. **CRM-аналитика** — воронка сделок, суммы по этапам
5. **Связка учёбы и выручки** — JOIN по ИНН школы
