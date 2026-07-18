"""Anthropic Claude chat model factory, cached for process lifetime."""

from functools import lru_cache

from langchain_anthropic import ChatAnthropic

from app.config import get_settings


@lru_cache
def get_llm(temperature: float = 0.0) -> ChatAnthropic:
    settings = get_settings()
    return ChatAnthropic(
        model_name=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=temperature,
        timeout=60,
        stop=None,
    )
