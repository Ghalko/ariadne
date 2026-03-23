from __future__ import annotations

from spinner.providers.embeddings import resolve_embedding_provider


def test_embedding_provider_defaults_to_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resolved = resolve_embedding_provider()
    assert resolved["provider"] == "deterministic"
    assert resolved["model"] == "deterministic-local"
