from __future__ import annotations

from quay.tenants.context import current_tenant
from quay.webhooks.verify import verify_signature


def receive_webhook(headers: dict[str, str], body: str) -> dict:
    tenant_id = current_tenant(headers)
    verified = verify_signature(headers=headers, body=body, secret="dev-secret")
    return {"tenant_id": tenant_id, "verified": verified}
