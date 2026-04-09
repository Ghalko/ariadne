from __future__ import annotations


def enqueue_webhook_retry(event_id: str) -> dict:
    return {"event_id": event_id, "job": "webhook_retry", "status": "queued"}
