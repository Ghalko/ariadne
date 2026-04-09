from __future__ import annotations

from quay.db.queries import list_failed_webhooks
from quay.jobs.dispatcher import enqueue_webhook_retry


def replay_failed_deliveries(tenant_id: str, limit: int = 25) -> list[dict]:
    failed = list_failed_webhooks(tenant_id)[:limit]
    return [enqueue_webhook_retry(item["event_id"]) for item in failed]
