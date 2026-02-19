import time
import logging

logger = logging.getLogger(__name__)

DEFAULT_TTL = 1800  # 30 minutes
DEFAULT_MAX_EXCHANGES = 10


class ConversationStore:
    """Per-user conversation memory with auto-expiry."""

    def __init__(self, ttl: int = DEFAULT_TTL, max_exchanges: int = DEFAULT_MAX_EXCHANGES):
        self._conversations: dict[int, dict] = {}
        self._ttl = ttl
        self._max_exchanges = max_exchanges

    def get_exchanges(self, user_id: int) -> list[dict]:
        """Get exchange history for a user. Returns [] if expired or not found."""
        entry = self._conversations.get(user_id)
        if entry is None:
            return []

        if time.time() - entry["last_active"] > self._ttl:
            logger.info("Conversation expired for user %s", user_id)
            del self._conversations[user_id]
            return []

        return list(entry["exchanges"])

    def add_exchange(self, user_id: int, question: str, sql: str, answer: str) -> None:
        """Add a completed exchange to the user's history."""
        if user_id not in self._conversations:
            self._conversations[user_id] = {"exchanges": [], "last_active": time.time()}

        entry = self._conversations[user_id]
        entry["exchanges"].append({"question": question, "sql": sql, "answer": answer})
        entry["last_active"] = time.time()

        if len(entry["exchanges"]) > self._max_exchanges:
            entry["exchanges"] = entry["exchanges"][-self._max_exchanges:]

    def clear(self, user_id: int) -> None:
        """Clear conversation history for a user."""
        self._conversations.pop(user_id, None)
