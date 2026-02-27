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
