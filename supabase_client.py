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
