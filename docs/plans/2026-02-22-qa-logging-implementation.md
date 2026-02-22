# Q&A Logging to Supabase — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Log every interactive Q&A exchange (user, question, answer, SQL, tokens, timing) to Supabase so we can analyze usage patterns and API costs.

**Architecture:** Modify `answer_question()` to return a result object with metadata (tokens, timing, SQL, success). Add a `supabase_client.py` module for fire-and-forget logging. Wire it up in the Telegram handler after each Q&A exchange.

**Tech Stack:** Python, supabase-py, existing Anthropic/aiogram stack

---

### Task 1: Add supabase dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Add the supabase package**

Add `supabase` to `requirements.txt`:

```
supabase
```

**Step 2: Install dependencies**

Run: `pip install supabase`

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "feat: add supabase dependency for Q&A logging"
```

---

### Task 2: Create QAResult dataclass in ai/qa.py

**Files:**
- Modify: `ai/qa.py:1-7` (imports section)
- Modify: `ai/qa.py:138-209` (answer_question function)

**Step 1: Add dataclass import and QAResult definition**

Add after line 3 (`from datetime import date`):

```python
from dataclasses import dataclass, field
```

Add before the `_build_sql_messages` function (before line 118):

```python
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
```

**Step 2: Modify answer_question to return QAResult**

Change the function signature return type and modify the body:

Replace the current `answer_question` function (lines 138-209) with:

```python
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

    total_input = query_response.usage.input_tokens
    total_output = query_response.usage.output_tokens

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
        return QAResult(
            answer="❌ Извините, этот запрос не разрешён.",
            success=False,
            generated_sql=sql_query,
            error_message="Blocked: unsafe SQL keywords detected",
            input_tokens=total_input,
            output_tokens=total_output,
        )

    # Block UNION - causes type conflicts in ClickHouse
    if "UNION" in sql_upper:
        return QAResult(
            answer="❌ Задайте конкретный вопрос:\n• Сколько просмотров за неделю?\n• Топ 5 регионов\n• Средний результат по математике",
            success=False,
            generated_sql=sql_query,
            error_message="Blocked: UNION not allowed",
            input_tokens=total_input,
            output_tokens=total_output,
        )

    # Step 2: Execute query
    import time as _time
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

    total_input += answer_response.usage.input_tokens
    total_output += answer_response.usage.output_tokens

    answer = answer_response.content[0].text

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
```

**Step 3: Verify no syntax errors**

Run: `python -c "from ai.qa import QAResult, answer_question; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add ai/qa.py
git commit -m "feat: return QAResult with token counts and timing from answer_question"
```

---

### Task 3: Create supabase_client.py

**Files:**
- Create: `supabase_client.py`

**Step 1: Create the module**

Create `supabase_client.py` with:

```python
import os
import logging
from supabase import create_client

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """Lazy initialization of Supabase client."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            logger.warning("SUPABASE_URL or SUPABASE_KEY not configured, logging disabled")
            return None
        _client = create_client(url, key)
    return _client


def log_qa_exchange(
    telegram_user_id: int,
    telegram_username: str | None,
    question: str,
    generated_sql: str | None,
    answer: str,
    success: bool,
    error_message: str | None,
    sql_execution_time_ms: int | None,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Log a Q&A exchange to Supabase. Fire-and-forget — never raises."""
    try:
        client = _get_client()
        if client is None:
            return

        client.table("qa_logs").insert({
            "telegram_user_id": telegram_user_id,
            "telegram_username": telegram_username,
            "question": question,
            "generated_sql": generated_sql,
            "answer": answer,
            "success": success,
            "error_message": error_message,
            "sql_execution_time_ms": sql_execution_time_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }).execute()

        logger.info("Q&A exchange logged to Supabase for user %s", telegram_user_id)
    except Exception as e:
        logger.warning("Failed to log Q&A exchange to Supabase: %s", e)
```

**Step 2: Verify no syntax errors**

Run: `python -c "import supabase_client; print('OK')"`
Expected: `OK` (with a warning about missing env vars, which is fine)

**Step 3: Commit**

```bash
git add supabase_client.py
git commit -m "feat: add supabase_client module for Q&A logging"
```

---

### Task 4: Wire up logging in bot/telegram.py

**Files:**
- Modify: `bot/telegram.py:157-173` (handle_message function)

**Step 1: Update handle_message to use QAResult and log**

Replace the `handle_message` function (lines 157-173) with:

```python
@router.message(F.text)
async def handle_message(message: Message) -> None:
    """Handle free-form questions."""
    if not is_user_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    question = message.text
    await message.answer("🤔 Думаю...")

    try:
        from ai.qa import answer_question
        from supabase_client import log_qa_exchange

        result = answer_question(question, message.from_user.id, conversation_store)
        await safe_reply(message, result.answer)

        log_qa_exchange(
            telegram_user_id=message.from_user.id,
            telegram_username=message.from_user.username,
            question=question,
            generated_sql=result.generated_sql,
            answer=result.answer,
            success=result.success,
            error_message=result.error_message,
            sql_execution_time_ms=result.sql_execution_time_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
    except Exception as e:
        logger.exception("Error answering question")
        await message.answer(f"❌ Ошибка: {str(e)}")
```

**Step 2: Verify no syntax errors**

Run: `python -c "from bot.telegram import handle_message; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add bot/telegram.py
git commit -m "feat: log Q&A exchanges to Supabase after each interaction"
```

---

### Task 5: Add env vars to .env and verify end-to-end

**Step 1: Add Supabase env vars**

Add to `.env`:

```
SUPABASE_URL=<your-supabase-url>
SUPABASE_KEY=<your-supabase-key>
```

**Step 2: Create the table in Supabase**

Run in Supabase SQL editor:

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

**Step 3: Test the bot**

Run: `python main.py`
Send a question via Telegram, verify:
1. The answer comes back as before
2. A row appears in the `qa_logs` table in Supabase dashboard

**Step 4: Final commit**

```bash
git commit -m "docs: add Supabase setup instructions to logging plan"
```
