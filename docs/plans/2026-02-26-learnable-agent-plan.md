# Learnable Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the AI Analyst bot learn from user corrections and resolve school/territory names in arbitrary forms.

**Architecture:** Two Supabase tables (`knowledge_rules`, `name_aliases`) with in-memory cache. Keyword matching loads only relevant rules into system prompt. Admin approves new rules via Telegram inline buttons. Name resolution runs before SQL generation.

**Tech Stack:** Python 3.10+, aiogram 3.4+ (inline keyboards, callback queries), Supabase (PostgreSQL), Anthropic Claude API

---

### Task 1: Supabase CRUD for knowledge tables

**Files:**
- Modify: `supabase_client.py`

**Step 1: Add CRUD functions for knowledge_rules and name_aliases**

Add to `supabase_client.py` after existing functions:

```python
def insert_knowledge_rule(
    category: str,
    rule_text: str,
    keywords: list[str],
    source_question: str,
    source_correction: str,
    created_by: int,
) -> dict | None:
    """Insert a pending knowledge rule. Returns the inserted row or None."""
    try:
        client = _get_client()
        if client is None:
            return None
        response = client.table("knowledge_rules").insert({
            "category": category,
            "rule_text": rule_text,
            "keywords": keywords,
            "source_question": source_question,
            "source_correction": source_correction,
            "created_by": created_by,
            "status": "pending",
        }).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.warning("Failed to insert knowledge rule: %s", e)
        return None


def get_approved_rules() -> list[dict]:
    """Fetch all approved knowledge rules."""
    client = _get_client()
    if client is None:
        return []
    response = client.table("knowledge_rules").select("*").eq("status", "approved").execute()
    return response.data


def update_rule_status(rule_id: int, status: str, approved_by: int | None = None) -> bool:
    """Update rule status (approved/rejected). Returns True on success."""
    try:
        client = _get_client()
        if client is None:
            return False
        data = {"status": status}
        if approved_by is not None:
            data["approved_by"] = approved_by
        client.table("knowledge_rules").update(data).eq("id", rule_id).execute()
        return True
    except Exception as e:
        logger.warning("Failed to update rule %s: %s", rule_id, e)
        return False


def update_rule_text(rule_id: int, new_text: str) -> bool:
    """Update the rule_text of a knowledge rule. Returns True on success."""
    try:
        client = _get_client()
        if client is None:
            return False
        client.table("knowledge_rules").update({"rule_text": new_text}).eq("id", rule_id).execute()
        return True
    except Exception as e:
        logger.warning("Failed to update rule text %s: %s", rule_id, e)
        return False


def insert_name_alias(
    alias: str,
    canonical_name: str,
    entity_type: str,
) -> dict | None:
    """Insert a pending name alias. Returns the inserted row or None."""
    try:
        client = _get_client()
        if client is None:
            return None
        response = client.table("name_aliases").insert({
            "alias": alias,
            "canonical_name": canonical_name,
            "entity_type": entity_type,
            "status": "pending",
        }).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.warning("Failed to insert name alias: %s", e)
        return None


def get_approved_aliases() -> list[dict]:
    """Fetch all approved name aliases."""
    client = _get_client()
    if client is None:
        return []
    response = client.table("name_aliases").select("*").eq("status", "approved").execute()
    return response.data


def update_alias_status(alias_id: int, status: str) -> bool:
    """Update alias status (approved/rejected). Returns True on success."""
    try:
        client = _get_client()
        if client is None:
            return False
        client.table("name_aliases").update({"status": status}).eq("id", alias_id).execute()
        return True
    except Exception as e:
        logger.warning("Failed to update alias %s: %s", alias_id, e)
        return False
```

**Step 2: Commit**

```bash
git add supabase_client.py
git commit -m "feat: add Supabase CRUD for knowledge_rules and name_aliases"
```

---

### Task 2: KnowledgeStore — in-memory cache with keyword matching

**Files:**
- Create: `knowledge/__init__.py`
- Create: `knowledge/store.py`
- Create: `tests/test_knowledge_store.py`

**Step 1: Create the knowledge package**

Create empty `knowledge/__init__.py`.

**Step 2: Write failing tests for KnowledgeStore**

Create `tests/test_knowledge_store.py`:

```python
from knowledge.store import KnowledgeStore


def test_find_rules_matches_keywords():
    store = KnowledgeStore()
    store._rules = [
        {"id": 1, "rule_text": "Use region not district for Краснодар", "keywords": ["краснодар", "край", "регион"]},
        {"id": 2, "rule_text": "КИМ means control measurements", "keywords": ["ким", "контрольн"]},
    ]
    matched = store.find_rules("Сколько работ в Краснодаре?")
    assert len(matched) == 1
    assert matched[0]["id"] == 1


def test_find_rules_no_match():
    store = KnowledgeStore()
    store._rules = [
        {"id": 1, "rule_text": "Some rule", "keywords": ["москва"]},
    ]
    matched = store.find_rules("Результаты по математике")
    assert matched == []


def test_find_rules_case_insensitive():
    store = KnowledgeStore()
    store._rules = [
        {"id": 1, "rule_text": "Rule about KIM", "keywords": ["ким"]},
    ]
    matched = store.find_rules("Сколько КИМ сдано?")
    assert len(matched) == 1


def test_find_rules_multiple_matches():
    store = KnowledgeStore()
    store._rules = [
        {"id": 1, "rule_text": "Rule 1", "keywords": ["математика"]},
        {"id": 2, "rule_text": "Rule 2", "keywords": ["результат"]},
        {"id": 3, "rule_text": "Rule 3", "keywords": ["физика"]},
    ]
    matched = store.find_rules("Средний результат по математике")
    assert len(matched) == 2
    assert {r["id"] for r in matched} == {1, 2}


def test_find_alias_exact_match():
    store = KnowledgeStore()
    store._aliases = [
        {"alias": "школа 5 краснодар", "canonical_name": "МБОУ СОШ №5 г. Краснодар", "entity_type": "school"},
    ]
    result = store.find_alias("школа 5 краснодар")
    assert result is not None
    assert result["canonical_name"] == "МБОУ СОШ №5 г. Краснодар"


def test_find_alias_substring_match():
    store = KnowledgeStore()
    store._aliases = [
        {"alias": "школа 5 краснодар", "canonical_name": "МБОУ СОШ №5 г. Краснодар", "entity_type": "school"},
    ]
    result = store.find_alias("результаты школа 5 краснодар за неделю")
    assert result is not None
    assert result["canonical_name"] == "МБОУ СОШ №5 г. Краснодар"


def test_find_alias_no_match():
    store = KnowledgeStore()
    store._aliases = [
        {"alias": "школа 5 краснодар", "canonical_name": "МБОУ СОШ №5 г. Краснодар", "entity_type": "school"},
    ]
    result = store.find_alias("школа 10 москва")
    assert result is None
```

**Step 3: Run tests to verify they fail**

```bash
cd "C:\Users\aleks\Documents\Projects\AI Analyst"
.venv/Scripts/python -m pytest tests/test_knowledge_store.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'knowledge.store'`

**Step 4: Implement KnowledgeStore**

Create `knowledge/store.py`:

```python
import logging

logger = logging.getLogger(__name__)


class KnowledgeStore:
    """In-memory cache for knowledge rules and name aliases with keyword matching."""

    def __init__(self):
        self._rules: list[dict] = []
        self._aliases: list[dict] = []

    def load(self, rules: list[dict], aliases: list[dict]) -> None:
        """Replace cached rules and aliases with fresh data."""
        self._rules = rules
        self._aliases = aliases
        logger.info("KnowledgeStore loaded: %d rules, %d aliases", len(rules), len(aliases))

    def find_rules(self, question: str) -> list[dict]:
        """Find rules whose keywords appear in the question."""
        question_lower = question.lower()
        matched = []
        for rule in self._rules:
            keywords = rule.get("keywords", [])
            if any(kw.lower() in question_lower for kw in keywords):
                matched.append(rule)
        return matched

    def find_alias(self, question: str) -> dict | None:
        """Find first alias whose alias text appears in the question."""
        question_lower = question.lower()
        for alias in self._aliases:
            if alias["alias"].lower() in question_lower:
                return alias
        return None

    def format_rules_for_prompt(self, rules: list[dict]) -> str:
        """Format matched rules as a section for the system prompt."""
        if not rules:
            return ""
        lines = ["## Правила из опыта"]
        for rule in rules:
            lines.append(f"- {rule['rule_text']}")
        return "\n".join(lines)

    def format_alias_hint(self, alias: dict) -> str:
        """Format alias as a hint for the system prompt."""
        return f'Подсказка: "{alias["alias"]}" = "{alias["canonical_name"]}" в базе данных.'
```

**Step 5: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_knowledge_store.py -v
```

Expected: All 7 tests PASS

**Step 6: Commit**

```bash
git add knowledge/__init__.py knowledge/store.py tests/test_knowledge_store.py
git commit -m "feat: add KnowledgeStore with keyword matching and alias lookup"
```

---

### Task 3: Rule extractor — detect corrections via LLM

**Files:**
- Create: `knowledge/extractor.py`

**Step 1: Implement rule extraction**

Create `knowledge/extractor.py`:

```python
import json
import logging
import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


EXTRACTION_PROMPT = """Проанализируй диалог между пользователем и AI-аналитиком.
Определи, было ли второе сообщение пользователя уточнением или коррекцией первого запроса.

Первый вопрос: {question1}
Первый ответ (SQL): {sql1}
Второй вопрос: {question2}
Второй ответ (SQL): {sql2}

Если второе сообщение — уточнение или коррекция (пользователь исправляет ошибку бота, уточняет термин, указывает на неправильную фильтрацию и т.п.), сформулируй правило.

Верни JSON (без markdown):
{{"is_correction": true, "rule_text": "Когда ..., нужно ...", "keywords": ["слово1", "слово2"], "category": "sql_pattern|domain_term|business_logic"}}

Если второе сообщение — это новый, независимый вопрос, верни:
{{"is_correction": false}}"""


def extract_rule(
    question1: str, sql1: str,
    question2: str, sql2: str,
) -> dict | None:
    """Analyze two exchanges and extract a rule if the second was a correction.

    Returns dict with keys: rule_text, keywords, category — or None if not a correction.
    """
    prompt = EXTRACTION_PROMPT.format(
        question1=question1, sql1=sql1,
        question2=question2, sql2=sql2,
    )

    try:
        response = _get_client().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # Clean up potential markdown wrapping
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        result = json.loads(text)
        if result.get("is_correction"):
            return {
                "rule_text": result["rule_text"],
                "keywords": result["keywords"],
                "category": result["category"],
            }
        return None
    except Exception as e:
        logger.warning("Rule extraction failed: %s", e)
        return None
```

**Step 2: Commit**

```bash
git add knowledge/extractor.py
git commit -m "feat: add LLM-based rule extractor for correction detection"
```

---

### Task 4: Name resolver — alias lookup + fuzzy DB search

**Files:**
- Create: `knowledge/resolver.py`

**Step 1: Implement name resolver**

Create `knowledge/resolver.py`:

```python
import logging
from knowledge.store import KnowledgeStore
from queries.base import execute_query

logger = logging.getLogger(__name__)


def resolve_names(question: str, store: KnowledgeStore) -> dict:
    """Check if the question contains known aliases. Returns resolution info.

    Returns:
        {
            "alias_found": True/False,
            "alias": {...} or None,
            "hint": "string for prompt" or ""
        }
    """
    alias = store.find_alias(question)
    if alias:
        return {
            "alias_found": True,
            "alias": alias,
            "hint": store.format_alias_hint(alias),
        }
    return {"alias_found": False, "alias": None, "hint": ""}


def fuzzy_search_schools(search_terms: list[str], limit: int = 5) -> list[str]:
    """Search for school names matching search terms in DB."""
    if not search_terms:
        return []
    conditions = " AND ".join(
        f"lower(school) LIKE '%{term.lower().replace(chr(39), '')}%'"
        for term in search_terms
    )
    query = f"""
    SELECT DISTINCT school
    FROM work_results_n
    WHERE {conditions} AND school != ''
    LIMIT {limit}
    """
    try:
        results = execute_query(query)
        return [r["school"] for r in results]
    except Exception as e:
        logger.warning("Fuzzy school search failed: %s", e)
        return []


def fuzzy_search_regions(search_terms: list[str], limit: int = 5) -> list[str]:
    """Search for region names matching search terms in DB."""
    if not search_terms:
        return []
    conditions = " AND ".join(
        f"lower(region) LIKE '%{term.lower().replace(chr(39), '')}%'"
        for term in search_terms
    )
    query = f"""
    SELECT DISTINCT region
    FROM work_results_n
    WHERE {conditions} AND region != ''
    LIMIT {limit}
    """
    try:
        results = execute_query(query)
        return [r["region"] for r in results]
    except Exception as e:
        logger.warning("Fuzzy region search failed: %s", e)
        return []
```

**Step 2: Commit**

```bash
git add knowledge/resolver.py
git commit -m "feat: add name resolver with alias lookup and fuzzy DB search"
```

---

### Task 5: Admin approval handlers — Telegram inline buttons

**Files:**
- Create: `bot/admin.py`

**Step 1: Implement admin notification and callback handlers**

Create `bot/admin.py`:

```python
import logging
from aiogram import Bot, Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.enums import ParseMode
from aiogram.filters import Command

logger = logging.getLogger(__name__)

admin_router = Router()

# Temporary storage for rules awaiting edit (admin_user_id -> rule_id)
_pending_edits: dict[int, int] = {}


async def notify_admin_new_rule(
    bot: Bot,
    admin_ids: set[int],
    rule: dict,
) -> None:
    """Send rule approval request to all admins."""
    rule_id = rule["id"]
    text = (
        f"📝 *Новое правило из диалога:*\n\n"
        f"Вопрос: _{rule.get('source_question', '?')}_\n"
        f"Уточнение: _{rule.get('source_correction', '?')}_\n\n"
        f"Предложенное правило:\n"
        f"«{rule.get('rule_text', '?')}»\n\n"
        f"Категория: `{rule.get('category', '?')}`\n"
        f"Ключевые слова: {', '.join(rule.get('keywords', []))}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"rule_approve:{rule_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"rule_edit:{rule_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rule_reject:{rule_id}"),
        ]
    ])

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.warning("Failed to notify admin %s: %s", admin_id, e)


async def notify_admin_new_alias(
    bot: Bot,
    admin_ids: set[int],
    alias_row: dict,
) -> None:
    """Send alias approval request to all admins."""
    alias_id = alias_row["id"]
    text = (
        f"📝 *Новый алиас названия:*\n\n"
        f"Пользователь написал: _{alias_row.get('alias', '?')}_\n"
        f"Значение в базе: _{alias_row.get('canonical_name', '?')}_\n"
        f"Тип: `{alias_row.get('entity_type', '?')}`"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"alias_approve:{alias_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"alias_reject:{alias_id}"),
        ]
    ])

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.warning("Failed to notify admin %s about alias: %s", admin_id, e)


@admin_router.callback_query(F.data.startswith("rule_approve:"))
async def handle_rule_approve(callback: CallbackQuery) -> None:
    from bot.telegram import is_admin
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только для админов", show_alert=True)
        return

    rule_id = int(callback.data.split(":")[1])
    from supabase_client import update_rule_status
    success = update_rule_status(rule_id, "approved", approved_by=callback.from_user.id)

    if success:
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ *Одобрено*",
            parse_mode=ParseMode.MARKDOWN,
        )
        # Refresh the knowledge store cache
        from knowledge.store import refresh_store
        refresh_store()
    else:
        await callback.answer("❌ Ошибка сохранения", show_alert=True)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("rule_reject:"))
async def handle_rule_reject(callback: CallbackQuery) -> None:
    from bot.telegram import is_admin
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только для админов", show_alert=True)
        return

    rule_id = int(callback.data.split(":")[1])
    from supabase_client import update_rule_status
    success = update_rule_status(rule_id, "rejected")

    if success:
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ *Отклонено*",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await callback.answer("❌ Ошибка сохранения", show_alert=True)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("rule_edit:"))
async def handle_rule_edit(callback: CallbackQuery) -> None:
    from bot.telegram import is_admin
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только для админов", show_alert=True)
        return

    rule_id = int(callback.data.split(":")[1])
    _pending_edits[callback.from_user.id] = rule_id
    await callback.message.edit_text(
        callback.message.text + "\n\n✏️ Отправьте новый текст правила:",
        parse_mode=ParseMode.MARKDOWN,
    )
    await callback.answer()


@admin_router.message(F.text & ~F.text.startswith("/"))
async def handle_rule_edit_text(message: Message) -> None:
    """Catch admin's edited rule text if they have a pending edit."""
    from bot.telegram import is_admin
    user_id = message.from_user.id
    if user_id not in _pending_edits or not is_admin(user_id):
        return  # Not an edit response, skip (will be handled by main router)

    rule_id = _pending_edits.pop(user_id)
    new_text = message.text.strip()

    from supabase_client import update_rule_text, update_rule_status
    update_rule_text(rule_id, new_text)
    update_rule_status(rule_id, "approved", approved_by=user_id)

    from knowledge.store import refresh_store
    refresh_store()

    await message.answer(f"✅ Правило #{rule_id} обновлено и одобрено:\n«{new_text}»")


@admin_router.callback_query(F.data.startswith("alias_approve:"))
async def handle_alias_approve(callback: CallbackQuery) -> None:
    from bot.telegram import is_admin
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только для админов", show_alert=True)
        return

    alias_id = int(callback.data.split(":")[1])
    from supabase_client import update_alias_status
    success = update_alias_status(alias_id, "approved")

    if success:
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ *Одобрено*",
            parse_mode=ParseMode.MARKDOWN,
        )
        from knowledge.store import refresh_store
        refresh_store()
    else:
        await callback.answer("❌ Ошибка сохранения", show_alert=True)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("alias_reject:"))
async def handle_alias_reject(callback: CallbackQuery) -> None:
    from bot.telegram import is_admin
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только для админов", show_alert=True)
        return

    alias_id = int(callback.data.split(":")[1])
    from supabase_client import update_alias_status
    success = update_alias_status(alias_id, "rejected")

    if success:
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ *Отклонено*",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await callback.answer("❌ Ошибка сохранения", show_alert=True)
    await callback.answer()
```

**Step 2: Commit**

```bash
git add bot/admin.py
git commit -m "feat: add admin approval handlers for rules and aliases"
```

---

### Task 6: Global knowledge store instance + refresh logic

**Files:**
- Modify: `knowledge/store.py` (add module-level instance and `refresh_store()`)

**Step 1: Add global instance and refresh function**

Append to the end of `knowledge/store.py`:

```python
# --- Module-level singleton ---

_store = KnowledgeStore()


def get_store() -> KnowledgeStore:
    """Get the global KnowledgeStore instance."""
    return _store


def refresh_store() -> None:
    """Reload rules and aliases from Supabase into the global store."""
    from supabase_client import get_approved_rules, get_approved_aliases
    rules = get_approved_rules()
    aliases = get_approved_aliases()
    _store.load(rules, aliases)
```

**Step 2: Commit**

```bash
git add knowledge/store.py
git commit -m "feat: add global KnowledgeStore singleton with refresh from Supabase"
```

---

### Task 7: Integrate into Q&A pipeline

**Files:**
- Modify: `ai/qa.py`

This is the core integration. Changes to `answer_question()`:
1. Before SQL generation: resolve names + find matching rules
2. Inject rules and alias hints into system prompt
3. After answer on 2nd+ exchange: call rule extractor

**Step 1: Add imports and modify SQL_SYSTEM_PROMPT to accept dynamic rules**

At top of `ai/qa.py`, add imports:

```python
from knowledge.store import get_store
from knowledge.extractor import extract_rule
from knowledge.resolver import resolve_names
```

**Step 2: Modify SQL_SYSTEM_PROMPT to include a placeholder for rules**

Change `SQL_SYSTEM_PROMPT` to:

```python
SQL_SYSTEM_PROMPT = """Ты SQL-эксперт для аналитики образовательной платформы. База данных: ClickHouse.

{schema}

{examples}

{knowledge_rules}

{alias_hints}

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
```

**Step 3: Modify answer_question() to use knowledge store**

Replace the `answer_question` function with:

```python
def answer_question(question: str, user_id: int, store: ConversationStore) -> QAResult:
    """Answer a user question about the data with conversation context."""
    exchanges = store.get_exchanges(user_id)

    # --- Knowledge integration ---
    knowledge_store = get_store()
    matched_rules = knowledge_store.find_rules(question)
    rules_text = knowledge_store.format_rules_for_prompt(matched_rules)
    resolution = resolve_names(question, knowledge_store)
    alias_hint = resolution["hint"]

    # Step 1: Generate SQL query
    sql_system = SQL_SYSTEM_PROMPT.format(
        schema=DATABASE_SCHEMA,
        examples=SQL_EXAMPLES,
        knowledge_rules=rules_text,
        alias_hints=alias_hint,
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

    # Step 4: Check for correction pattern (only on 2nd+ exchange)
    if len(exchanges) >= 1:
        prev = exchanges[-1]
        try:
            rule_data = extract_rule(
                question1=prev["question"], sql1=prev["sql"],
                question2=question, sql2=sql_query,
            )
            if rule_data:
                from supabase_client import insert_knowledge_rule
                inserted = insert_knowledge_rule(
                    category=rule_data["category"],
                    rule_text=rule_data["rule_text"],
                    keywords=rule_data["keywords"],
                    source_question=prev["question"],
                    source_correction=question,
                    created_by=user_id,
                )
                if inserted:
                    # Signal to telegram handler that a rule was proposed
                    return QAResult(
                        answer=answer,
                        success=True,
                        generated_sql=sql_query,
                        sql_execution_time_ms=sql_execution_time_ms,
                        input_tokens=total_input,
                        output_tokens=total_output,
                        proposed_rule=inserted,
                    )
        except Exception as e:
            logger.warning("Rule extraction step failed: %s", e)

    return QAResult(
        answer=answer,
        success=True,
        generated_sql=sql_query,
        sql_execution_time_ms=sql_execution_time_ms,
        input_tokens=total_input,
        output_tokens=total_output,
    )
```

**Step 4: Add `proposed_rule` field to QAResult**

Update the `QAResult` dataclass:

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
    proposed_rule: dict | None = None
```

**Step 5: Commit**

```bash
git add ai/qa.py
git commit -m "feat: integrate knowledge store and rule extraction into Q&A pipeline"
```

---

### Task 8: Wire everything into Telegram bot and main.py

**Files:**
- Modify: `bot/telegram.py`
- Modify: `main.py`

**Step 1: Update telegram.py — add admin router, /rules command, rule notification**

Add import at top of `bot/telegram.py`:

```python
from bot.admin import admin_router, notify_admin_new_rule
```

Update `handle_message()` to notify admins on proposed rules:

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

        # Notify admins if a rule was proposed
        if result.proposed_rule and ADMIN_USERS:
            await notify_admin_new_rule(
                message.bot, ADMIN_USERS, result.proposed_rule,
            )
    except Exception as e:
        logger.exception("Error answering question")
        await message.answer(f"❌ Ошибка: {str(e)}")
```

Add `/rules` command for admins to see active rules:

```python
@router.message(Command("rules"))
async def rules_command(message: Message) -> None:
    """Handle /rules command - show active knowledge rules (admin only)."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён. Команда доступна только администраторам.")
        return

    from knowledge.store import get_store
    store = get_store()

    if not store._rules and not store._aliases:
        await message.answer("📋 База знаний пуста.")
        return

    lines = ["📋 *Активные правила:*\n"]
    for i, rule in enumerate(store._rules, 1):
        kw = ", ".join(rule.get("keywords", []))
        lines.append(f"{i}. {rule['rule_text']}\n   Ключевые слова: _{kw}_\n")

    if store._aliases:
        lines.append("\n📋 *Алиасы названий:*\n")
        for alias in store._aliases:
            lines.append(f"• _{alias['alias']}_ → {alias['canonical_name']}")

    await safe_reply(message, "\n".join(lines))
```

Update `create_dispatcher()` to include admin router:

```python
def create_dispatcher() -> Dispatcher:
    """Create and configure the dispatcher."""
    dp = Dispatcher()
    dp.include_router(admin_router)  # Admin router first (handles callbacks)
    dp.include_router(router)
    return dp
```

Update `/help` command text to include `/rules`.

**Step 2: Update main.py — load knowledge store on startup**

Add to `main.py` after bot creation, before scheduler:

```python
    # Load knowledge store
    from knowledge.store import refresh_store
    refresh_store()
```

**Step 3: Commit**

```bash
git add bot/telegram.py main.py
git commit -m "feat: wire knowledge system into Telegram bot with /rules command"
```

---

### Task 9: Create Supabase tables (SQL migration)

**Files:**
- Create: `docs/migrations/001_knowledge_tables.sql`

**Step 1: Write the migration SQL**

```sql
-- Knowledge rules table
CREATE TABLE IF NOT EXISTS knowledge_rules (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL CHECK (category IN ('sql_pattern', 'domain_term', 'business_logic')),
    rule_text TEXT NOT NULL,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    source_question TEXT,
    source_correction TEXT,
    created_by BIGINT,
    approved_by BIGINT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_knowledge_rules_status ON knowledge_rules(status);

-- Name aliases table
CREATE TABLE IF NOT EXISTS name_aliases (
    id SERIAL PRIMARY KEY,
    alias TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('school', 'region', 'district')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_name_aliases_status ON name_aliases(status);
```

**Step 2: Run this SQL in Supabase SQL Editor**

Go to Supabase Dashboard → SQL Editor → paste and run.

**Step 3: Commit**

```bash
mkdir -p docs/migrations
git add docs/migrations/001_knowledge_tables.sql
git commit -m "feat: add SQL migration for knowledge_rules and name_aliases tables"
```

---

### Task 10: Manual integration test

**Step 1: Run the bot locally**

```bash
cd "C:\Users\aleks\Documents\Projects\AI Analyst"
.venv/Scripts/python main.py
```

**Step 2: Test the learning flow**

1. Send a question to the bot: "Сколько работ в Краснодаре?"
2. Bot answers (might filter by district)
3. Send correction: "Я имел в виду Краснодарский край"
4. Bot answers correctly
5. Check that admin received a rule proposal notification
6. Admin approves the rule
7. Send `/rules` to verify rule is active
8. Send "Сколько работ в Краснодаре?" again — should now use region filter

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: learnable agent with knowledge rules and name aliases"
```
