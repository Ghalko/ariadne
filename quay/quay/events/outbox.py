from __future__ import annotations

OUTBOX: list[dict] = []


def publish_billing_event(event_type: str, *, tenant_id: str, payload: dict) -> None:
    OUTBOX.append({"event_type": event_type, "tenant_id": tenant_id, "payload": payload})
