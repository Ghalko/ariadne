from __future__ import annotations

from spinner.providers.base import ProviderSettings


def load_openai_settings() -> ProviderSettings:
    return ProviderSettings(
        primary_chat_model="gpt-5-codex",
        primary_embedding_model="text-embedding-3-small",
        fallback_embedding_model="deterministic-local",
        deterministic_fallback=True,
    )
