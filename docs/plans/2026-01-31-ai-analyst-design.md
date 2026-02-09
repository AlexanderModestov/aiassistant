# AI Analyst MVP Design

## Overview

An AI-powered analytics system for an educational platform that provides:
1. **Phase 1:** Automated daily growth reports delivered via Telegram
2. **Phase 2:** Interactive Q&A - ask questions about data in natural language

## Data Source

**ClickHouse Database:** `cok_db`

### Tables

| Table | Purpose |
|-------|---------|
| `school_work` | Activity tracking (views by date, region, role, school, subject) |
| `work_results_n` | Student work submissions (1.3M+ records) |
| `work_results_06` | Historical work results |
| `company_crm` | CRM data for schools/companies |

### Key Columns

- `role` - "Ученик" (Student) / "Учитель" (Teacher)
- `region` - Russian regions (Московская область, etc.)
- `date` / `submission_date` - Activity dates
- `total_view` - View counts
- `result_percent`, `status` - Work completion metrics

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ClickHouse    │────▶│   Python App    │────▶│    Telegram     │
│   (cok_db)      │     │                 │     │    Bot API      │
└─────────────────┘     │  ┌───────────┐  │     └─────────────────┘
                        │  │  Queries  │  │
                        │  └───────────┘  │
                        │        │        │
                        │        ▼        │
                        │  ┌───────────┐  │
                        │  │  Claude   │  │
                        │  │   API     │  │
                        │  └───────────┘  │
                        └─────────────────┘
```

### Components

1. **Data Layer** - ClickHouse connection and pre-defined queries
2. **AI Layer** - Claude API for insight generation and Q&A
3. **Delivery Layer** - Telegram bot with scheduler

## Phase 1: Daily Reports

### Schedule

- Runs every morning at 9:00 AM Moscow time
- Uses `APScheduler` for reliable scheduling
- Retry once on failure

### Growth Queries

1. **Daily activity** - Views by students and teachers yesterday vs previous day
2. **Weekly trend** - Total views and work submissions this week vs last week
3. **Regional breakdown** - Activity and submissions by region, sorted by growth
4. **Student engagement** - Work completion rates, average result_percent
5. **Teacher vs Student activity** - Ratio of views and activity by role

### Report Format

Telegram message (under 4000 chars) in Russian:

```
📊 Сводка за день (Daily summary)
📈 Рост (Growth highlights)
🏆 Топ регионы (Top regions)
💡 Наблюдение (Key observation)
```

### Claude Prompt Template

```
You are an analyst for an educational platform in Russia.

Here is today's data:
- Yesterday's views: {views_data}
- Work submissions: {submissions_data}
- Regional breakdown: {regional_data}
- Week-over-week changes: {trends_data}

Write a concise daily insight report (3-5 key points) focusing on:
1. Notable growth or decline vs yesterday/last week
2. Top performing regions
3. Any anomalies worth attention
4. One actionable observation

Keep it conversational and in Russian.
```

## Phase 2: Interactive Q&A

### Flow

1. User sends question to Telegram bot
2. Claude analyzes question to determine data needs
3. System selects/generates appropriate query
4. Query runs against ClickHouse
5. Claude interprets results and responds

### Example Interactions

| Question | System Action |
|----------|---------------|
| "Сколько работ сдали вчера?" | Runs submissions count, compares to previous day |
| "Топ-5 регионов по активности" | Runs regional breakdown, formats ranked list |
| "Как дела в Московской области?" | Filters all metrics by region, summarizes |

### Safety Constraints

- Only SELECT queries (no INSERT/UPDATE/DELETE)
- Query timeout: 10 seconds
- Ask for clarification if question is unclear

### MVP Limitations

- No complex multi-step analysis
- No data export or file generation
- No historical comparisons beyond 30 days

## Project Structure

```
ai-analyst/
├── .env                 # Credentials (ClickHouse, Telegram, Anthropic)
├── main.py              # Entry point, scheduler, bot setup
├── requirements.txt     # Python dependencies
├── queries/
│   ├── __init__.py
│   ├── base.py          # ClickHouse connection helper
│   └── growth.py        # Growth metric queries
├── ai/
│   ├── __init__.py
│   └── insights.py      # Claude prompt and report generation
├── bot/
│   ├── __init__.py
│   └── telegram.py      # Telegram bot handlers
└── docs/
    └── plans/
        └── 2026-01-31-ai-analyst-design.md
```

## Dependencies

```
clickhouse-connect    # ClickHouse database access
anthropic             # Claude API
python-telegram-bot   # Telegram integration
apscheduler           # Job scheduling
python-dotenv         # Environment variables
```

## Configuration (.env)

```
# ClickHouse
CLICKHOUSE_HOST=http://91.236.197.14:8123
CLICKHOUSE_DATABASE=cok_db
CLICKHOUSE_USER=clickhouse_admin
CLICKHOUSE_PASSWORD=<password>

# Telegram
TELEGRAM_BOT_TOKEN=<from @BotFather>
TELEGRAM_CHAT_ID=<your chat ID>

# Anthropic
ANTHROPIC_API_KEY=<api key>

# Schedule
REPORT_TIME=09:00
TIMEZONE=Europe/Moscow
```

## Next Steps

1. Set up Telegram bot via @BotFather
2. Get Anthropic API key
3. Implement Phase 1 (daily reports)
4. Test and iterate on report quality
5. Implement Phase 2 (interactive Q&A)
