# Conversation Memory Design

## Goal

Add per-user conversation memory to the Q&A system so follow-up questions work naturally (e.g. "now break that down by region" references the previous query).

## Scope

- Conversation memory within a session (not cross-session)
- Per-user context with 30-minute auto-expiry
- Current 2-step Q&A flow (generate SQL → answer) stays the same
- Daily reports remain stateless

## Design

### ConversationStore (`conversation.py`)

In-memory class managing per-user message histories with auto-expiry.

```
ConversationStore:
  _conversations: dict[user_id → {messages: list, last_active: timestamp}]
  TTL: 30 minutes (configurable)
  MAX_EXCHANGES: 10 (question + answer pairs)

  Methods:
  - get_history(user_id) → list of messages (returns [] if expired)
  - add_message(user_id, role, content) → appends, trims if > MAX_EXCHANGES
  - clear(user_id) → explicitly resets
```

Each message follows Claude's API format: `{"role": "user" | "assistant", "content": "..."}`.

No database, no persistence. Bot restart = clean slate.

### Q&A Changes (`ai/qa.py`)

`answer_question(question)` becomes `answer_question(question, user_id, conversation_store)`.

**SQL generation:** Message history is prepended to the messages list. Claude sees previous questions and SQL so it can resolve references like "break that down by subject."

**Answer generation:** History includes full formatted answers for conversational consistency.

**After each exchange:** Both user question and final answer are stored. Intermediate SQL and results are embedded in the assistant message content.

### Bot Changes (`bot/telegram.py`)

- Create `ConversationStore` instance at startup
- Pass `user_id` and store to `answer_question()`
- Add `/clear` command to manually reset context
- `/start`, `/help`, `/report`, whitelist, scheduled reports — unchanged

## Files Changed

1. **New:** `conversation.py` — ConversationStore class
2. **Modified:** `ai/qa.py` — pass message history into Claude calls
3. **Modified:** `bot/telegram.py` — wire up store, add `/clear`
