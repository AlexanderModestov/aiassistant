import os
import logging
from supabase import create_client

logger = logging.getLogger(__name__)

_NOT_INITIALIZED = object()
_client = _NOT_INITIALIZED


def _get_client():
    """Lazy initialization of Supabase client."""
    global _client
    if _client is _NOT_INITIALIZED:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            logger.warning("SUPABASE_URL or SUPABASE_KEY not configured, logging disabled")
            _client = None
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
    """Log a Q&A exchange to Supabase. Fire-and-forget -- never raises."""
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


def get_qa_stats(since_iso: str | None = None) -> list[dict]:
    """Fetch qa_logs rows, optionally filtered by created_at >= since_iso."""
    client = _get_client()
    if client is None:
        return []

    query = client.table("qa_logs").select(
        "telegram_user_id, telegram_username, question, input_tokens, output_tokens"
    )
    if since_iso is not None:
        query = query.gte("created_at", since_iso)

    response = query.execute()
    return response.data


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
