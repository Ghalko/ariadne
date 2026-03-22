from __future__ import annotations

import hashlib
import math
from collections import Counter
from typing import Protocol


class EmbeddingProvider(Protocol):
    dimensions: int
    model_name: str

    def embed(self, text: str) -> list[float]:
        ...


class DeterministicEmbeddingProvider:
    def __init__(self, dimensions: int = 1024, model_name: str = "deterministic-local") -> None:
        self.dimensions = dimensions
        self.model_name = model_name

    def embed(self, text: str) -> list[float]:
        buckets = [0.0] * self.dimensions
        tokens = text.lower().split()
        counts = Counter(tokens)
        for token, count in counts.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = digest[0] % self.dimensions
            direction = -1.0 if digest[1] % 2 else 1.0
            buckets[index] += direction * float(count)

        norm = math.sqrt(sum(value * value for value in buckets)) or 1.0
        return [value / norm for value in buckets]


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = "text-embedding-3-small",
        dimensions: int = 1024,
        client=None,
    ) -> None:
        self.model_name = model_name
        self.dimensions = dimensions
        if client is not None:
            self.client = client
            return

        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=self.model_name,
            input=text,
            dimensions=self.dimensions,
        )
        return list(response.data[0].embedding)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))
