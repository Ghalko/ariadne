from __future__ import annotations


def tenant_feature_flags(tenant_id: str) -> dict[str, bool]:
    return {
        "webhook_replay": True,
        "billing_events": tenant_id != "disabled",
        "support_override": False,
    }
