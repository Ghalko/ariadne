from __future__ import annotations


def list_failed_webhooks(tenant_id: str) -> list[dict]:
    return [
        {"tenant_id": tenant_id, "event_id": "evt_1", "attempt_count": 3, "status": "failed"},
        {"tenant_id": tenant_id, "event_id": "evt_2", "attempt_count": 2, "status": "failed"},
    ]
