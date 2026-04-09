from __future__ import annotations

from quay.audit.log import append_audit_event


def can_access_tenant(actor_tenant_id: str, target_tenant_id: str) -> bool:
    allowed = actor_tenant_id == target_tenant_id
    if not allowed:
        append_audit_event("cross_tenant_denied", {"actor": actor_tenant_id, "target": target_tenant_id})
    return allowed
