from __future__ import annotations

from spinner.telemetry.logging import append_event


def maybe_warn_on_large_context(*, mode: str, estimated_tokens: int, budget: int) -> None:
    if estimated_tokens > budget:
        append_event(
            "incident",
            {
                "kind": "context_over_budget",
                "mode": mode,
                "estimated_tokens": estimated_tokens,
                "budget": budget,
            },
        )
