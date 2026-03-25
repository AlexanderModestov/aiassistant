import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

_client = None
provider = os.getenv("AI_PROVIDER", "openai").lower()
model = os.getenv("AI_MODEL", "gpt-4o-mini")


def get_client():
    """Lazy initialization of AI client based on AI_PROVIDER."""
    global _client
    if _client is None:
        if provider == "anthropic":
            from anthropic import Anthropic
            _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        else:
            from openai import OpenAI
            _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


@dataclass
class AIResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


def chat(messages: list[dict], system: str | None = None, max_tokens: int = 1024) -> AIResponse:
    """Unified chat call that works with both providers."""
    client = get_client()

    if provider == "anthropic":
        kwargs = dict(model=model, max_tokens=max_tokens, messages=messages)
        if system:
            kwargs["system"] = system
        response = client.messages.create(**kwargs)
        return AIResponse(
            text=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
    else:
        openai_messages = []
        if system:
            openai_messages.append({"role": "system", "content": system})
        openai_messages.extend(messages)
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=openai_messages,
        )
        usage = response.usage
        return AIResponse(
            text=response.choices[0].message.content,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
