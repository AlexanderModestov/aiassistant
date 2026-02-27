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
