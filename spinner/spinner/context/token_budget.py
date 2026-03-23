from __future__ import annotations


def estimate_tokens(parts: list[str]) -> int:
    return sum(max(1, len(part.split())) for part in parts)


def fits_budget(parts: list[str], budget: int) -> bool:
    return estimate_tokens(parts) <= budget
