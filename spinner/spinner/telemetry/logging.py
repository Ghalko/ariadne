from __future__ import annotations

EVENTS: list[dict] = []


def append_event(event_type: str, payload: dict) -> None:
    EVENTS.append({"type": event_type, "payload": payload})
