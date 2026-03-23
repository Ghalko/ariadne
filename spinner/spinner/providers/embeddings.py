from __future__ import annotations

import os

from spinner.providers.deterministic import deterministic_embedding_name
from spinner.providers.openai import load_openai_settings


def resolve_embedding_provider() -> dict:
    settings = load_openai_settings()
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return {
            "provider": "openai",
            "model": settings.primary_embedding_model,
            "fallback": settings.fallback_embedding_model,
        }
    return {
        "provider": "deterministic",
        "model": deterministic_embedding_name(),
        "fallback": None,
    }
