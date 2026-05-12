# ClickHouse Database Schema

**Database:** `cok_db`

**Host:** `http://91.236.197.14:8123`

---

## Логическая структура

```
┌─────────────────────────────────────────────────────────────┐
│                       ФАКТ-ТАБЛИЦА                          │
├─────────────────────────────────────────────────────────────┤
│  oblakoz_sending       │  Отправки работ (sending events)   │
└─────────────────────────────────────────────────────────────┘
        │                              │
        │ school_id                    │ id
        ▼                              ▼
┌──────────────────────┐    ┌─────────────────────────────┐
│   oblakoz_school     │    │   oblakoz_sending_module    │
│   (справочник школ)  │    │   sending_id → module       │
└──────────────────────┘    └──────────────┬──────────────┘
                                           │ module
                                           ▼
                            ┌─────────────────────────────┐
                            │   oblakoz_content_module    │
                            │   content_id → module       │
                            └──────────────┬──────────────┘
                                           │ content_id
                                           ▼
                            ┌─────────────────────────────┐
                            │   oblakoz_content           │
                            │   (метаданные работ)        │
                            └─────────────────────────────┘
```

---

## Tables Overview

| Table | Description | Доступна для запросов |
|-------|-------------|----------------------|
| `oblakoz_sending` | Отправки / выполнения работ | ✅ Да |
| `oblakoz_school` | Справочник школ | ✅ Да |
| `oblakoz_content` | Метаданные контента (работ) | ✅ Да |
| `oblakoz_sending_module` | Связь отправка ↔ модуль | ✅ Да |
| `oblakoz_content_module` | Связь контент ↔ модуль | ✅ Да |

---

## Факт-таблица

### Table: `oblakoz_sending`

Отправки выполненных работ (один ряд = одна выполненная работа учеником).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UInt32 | Уникальный ID отправки |
| `registration` | String | ID регистрации |
| `user_id` | String | ID пользователя (ученика) |
| `role` | String | Роль (Ученик / Учитель) |
| `school_id` | UInt32 | FK → `oblakoz_school.id` |
| `grade` | String | Параллель/класс ученика (5, 6, 7, ...) |
| `order_id` | String | ID заказа |
| `result` | UInt32 | Процент выполнения (0–100) |
| `duration` | UInt32 | Время выполнения (секунды) |
| `start_date` | Nullable(Date) | Дата начала |
| `start_time` | Nullable(String) | Время начала |
| `end_date` | Nullable(Date) | Дата окончания (используется как «дата сдачи») |
| `end_time` | Nullable(String) | Время окончания |

> **Важно:** «Дата сдачи работы» в новой схеме = `end_date`. Это `Nullable(Date)`, сравнивать можно напрямую (`end_date = '2026-05-01'`).

---

## Справочники

### Table: `oblakoz_school`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UInt32 | ID школы |
| `inn` | String | ИНН |
| `name` | String | Название школы |
| `region` | String | Регион |
| `municipality` | String | Муниципалитет |

### Table: `oblakoz_content`

Метаданные контента (работ/курсов).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UInt32 | ID контента |
| `title` | String | Название работы |
| `tasks_amount` | UInt32 | Количество заданий |
| `duration` | UInt32 | Длительность |
| `genre` | String | Жанр / тип контента |
| `subject` | String | Предмет |
| `grade` | String | Параллель контента |
| `level` | String | Уровень сложности |

---

## Связующие таблицы

### Table: `oblakoz_sending_module`

| Column | Type | Description |
|--------|------|-------------|
| `sending_id` | UInt32 | FK → `oblakoz_sending.id` |
| `module` | UInt32 | Код модуля |

### Table: `oblakoz_content_module`

| Column | Type | Description |
|--------|------|-------------|
| `content_id` | UInt32 | FK → `oblakoz_content.id` |
| `module` | UInt32 | Код модуля |

> Связь sending ↔ content идёт через общее значение `module`:
> `oblakoz_sending → oblakoz_sending_module → oblakoz_content_module → oblakoz_content`.

---

## Common Queries

### Количество работ за сегодня
```sql
SELECT count() as works, uniqExact(user_id) as students
FROM oblakoz_sending
WHERE end_date = today()
```

### Топ-10 регионов по активности за неделю
```sql
SELECT sch.region as region,
       count() as works,
       uniqExact(s.school_id) as schools,
       uniqExact(s.user_id) as students
FROM oblakoz_sending s
INNER JOIN oblakoz_school sch ON s.school_id = sch.id
WHERE s.end_date >= today() - 7
GROUP BY sch.region
ORDER BY works DESC
LIMIT 10
```

### Топ-10 школ за день
```sql
SELECT sch.name as school, sch.region as region,
       count() as works,
       uniqExact(s.user_id) as students
FROM oblakoz_sending s
INNER JOIN oblakoz_school sch ON s.school_id = sch.id
WHERE s.end_date = today()
GROUP BY sch.name, sch.region
ORDER BY works DESC
LIMIT 10
```

### Результаты по параллелям
```sql
SELECT grade,
       count() as works,
       avg(result) as avg_score
FROM oblakoz_sending
WHERE end_date = today()
  AND grade != ''
GROUP BY grade
ORDER BY grade
```

### Средний результат по предметам (через модуль)
```sql
SELECT c.subject as subject,
       count() as works,
       avg(s.result) as avg_score
FROM oblakoz_sending s
INNER JOIN oblakoz_sending_module sm ON s.id = sm.sending_id
INNER JOIN oblakoz_content_module cm ON sm.module = cm.module
INNER JOIN oblakoz_content c ON cm.content_id = c.id
WHERE s.end_date = today()
GROUP BY c.subject
ORDER BY works DESC
```

### Среднее время выполнения (в минутах) по школам
```sql
SELECT sch.name as school,
       round(avg(s.duration) / 60) as avg_minutes,
       count() as works
FROM oblakoz_sending s
INNER JOIN oblakoz_school sch ON s.school_id = sch.id
WHERE s.end_date = today()
GROUP BY sch.name
ORDER BY works DESC
LIMIT 10
```

### Динамика по дням за неделю
```sql
SELECT end_date as day, count() as works, uniqExact(user_id) as students
FROM oblakoz_sending
WHERE end_date >= today() - 7
GROUP BY day
ORDER BY day
```

---

## Типовые сценарии использования

1. **Активность** — количество работ, уникальные ученики и школы по дате
2. **География** — топ регионов / школ / муниципалитетов (JOIN с `oblakoz_school`)
3. **Параллели** — распределение по `grade`
4. **Предметная аналитика** — JOIN sending → content через модуль
5. **Время выполнения** — `duration` (секунды → минуты)

---

## Правила маппинга со старой схемой

| Старое поле | Новое поле | Примечание |
|-------------|------------|------------|
| `work_results_n.submission_date` | `oblakoz_sending.end_date` | Тип теперь `Nullable(Date)` — сравнивать напрямую |
| `work_results_n.student_id` | `oblakoz_sending.user_id` | |
| `work_results_n.result_percent` | `oblakoz_sending.result` | |
| `work_results_n.time_spent` | `oblakoz_sending.duration` | Секунды |
| `work_results_n.parallel` | `oblakoz_sending.grade` | |
| `work_results_n.region` | `oblakoz_school.region` (JOIN) | |
| `work_results_n.school` | `oblakoz_school.name` (JOIN) | |
| `work_results_n.district` | `oblakoz_school.municipality` (JOIN) | |
| `work_results_n.inn` | `oblakoz_school.inn` (JOIN) | |
| `work_results_n.subject` | `oblakoz_content.subject` (JOIN через модуль) | |
| `work_results_n.level` | `oblakoz_content.level` (JOIN через модуль) | |
| `work_results_n.work_name` | `oblakoz_content.title` (JOIN через модуль) | |
| `work_results_n.tasks_count` | `oblakoz_content.tasks_amount` (JOIN через модуль) | |
| `work_results_n.id_registration` | `oblakoz_sending.registration` | |
| `work_results_n.id_order` | `oblakoz_sending.order_id` | |
| `work_results_n.status` | — | Удалено, в новой схеме нет |
| `work_results_n.work_type` | — | Удалено (есть `oblakoz_content.genre`, но семантика другая) |
| `work_results_n.class_teacher` | — | Удалено |
