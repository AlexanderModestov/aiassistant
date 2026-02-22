# Q&A Logging to Supabase

## Goal

Log every interactive Q&A exchange to Supabase (Postgres) so we can see which users ask what questions, what answers they get, and how many tokens each exchange costs.

## Scope

- Only interactive Q&A is logged (not daily scheduled reports)
- Logging is fire-and-forget: if Supabase is down, the bot continues working

## Table Schema

```sql
CREATE TABLE qa_logs (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    telegram_user_id bigint NOT NULL,
    telegram_username text,
    question text NOT NULL,
    generated_sql text,
    answer text,
    success boolean NOT NULL DEFAULT true,
    error_message text,
    sql_execution_time_ms integer,
    input_tokens integer,
    output_tokens integer,
    created_at timestamptz DEFAULT now()
);
```

Fields:
- `telegram_user_id` / `telegram_username` — who asked
- `question` — the user's natural language question
- `generated_sql` — the SQL Claude generated from the question
- `answer` — the response sent back to the user
- `success` / `error_message` — whether the exchange completed or failed
- `sql_execution_time_ms` — ClickHouse query duration
- `input_tokens` / `output_tokens` — summed across both Claude calls (SQL generation + answer generation)
- `created_at` — timestamp with timezone

## Architecture

### New file: `supabase_client.py`

Initializes the Supabase client and exposes a `log_qa_exchange()` function. Wraps the insert in a try/except so failures are printed to console but never crash the bot.

### Modified: `ai/qa.py`

Return token usage from both Claude API calls (SQL generation and answer generation) alongside the existing return values. The two calls' tokens are summed.

### Modified: `bot/telegram.py`

After sending the answer to the user, call `log_qa_exchange()` with all collected data: user info, question, SQL, answer, tokens, timing, and success/error status.

### Flow

```
User asks question
  -> bot/telegram.py receives message
  -> ai/qa.py generates SQL (track tokens)
  -> ai/qa.py executes query (track timing)
  -> ai/qa.py generates answer (track tokens)
  -> Send answer to user
  -> Log everything to Supabase (fire-and-forget)
```

## Configuration

New environment variables in `.env`:
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_KEY` — Supabase anon or service key

## Changes Summary

| Change | File |
|--------|------|
| New file | `supabase_client.py` |
| Modified | `ai/qa.py` — return token counts |
| Modified | `bot/telegram.py` — call logging after Q&A |
| New dependency | `supabase` in `requirements.txt` |
| New env vars | `SUPABASE_URL`, `SUPABASE_KEY` |
| New table | `qa_logs` in Supabase (created via SQL editor) |
