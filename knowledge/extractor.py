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
