from __future__ import annotations

from spinner.telemetry.logging import append_event


def record_retrieval_event(*, query: str, mode: str, count: int) -> None:
    append_event("retrieval", {"query": query, "mode": mode, "count": count})
