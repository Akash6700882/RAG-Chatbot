"""Chat model factory. Provider is selected via LLM_PROVIDER (anthropic|gemini|groq)
so the RAG nodes stay provider-agnostic — they only ever call get_llm()."""

from functools import lru_cache
from typing import Any

from app.config import get_settings


@lru_cache
def get_llm(temperature: float = 0.0) -> Any:
    settings = get_settings()

    if settings.llm_provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=temperature,
        )

    if settings.llm_provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=temperature,
        )

    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model_name=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=temperature,
        timeout=60,
        stop=None,
    )
