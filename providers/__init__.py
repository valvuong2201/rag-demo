"""Factory: pick the active AI provider (OpenAI or Gemini) from config."""
from __future__ import annotations

from .base import Provider


def get_provider(
    name: str,
    *,
    openai_api_key: str | None = None,
    gemini_api_key: str | None = None,
    gemini_embedding_model: str | None = None,
) -> Provider:
    name = name.lower()
    if name == "openai":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(openai_api_key)
    if name == "gemini":
        from .gemini_provider import GeminiProvider

        return GeminiProvider(gemini_api_key, gemini_embedding_model or "models/gemini-embedding-2")
    raise ValueError(f"Unknown AI_PROVIDER: {name!r} (expected 'openai' or 'gemini')")
