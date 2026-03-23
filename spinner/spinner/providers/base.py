from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProviderSettings:
    primary_chat_model: str
    primary_embedding_model: str
    fallback_embedding_model: str
    deterministic_fallback: bool = True
