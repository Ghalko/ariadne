from __future__ import annotations

from quay.models import IncidentBundle


def diagnose_incident(*, query: str, mode: str, tenant_id: str) -> IncidentBundle:
    lowered = query.lower()
    if "webhook" in lowered or "replay" in lowered:
        return IncidentBundle(
            focus_files=[
                "quay/webhooks/replay.py",
                "quay/db/queries.py",
                "quay/jobs/dispatcher.py",
                "quay/webhooks/verify.py",
            ],
            docs=[
                "docs/runbooks/webhook-replay-failures.md",
                "docs/adr/002-webhook-idempotency.md",
            ],
            configs=["config/webhooks.toml", "config/quay.toml"],
            notes=[f"tenant={tenant_id}", f"mode={mode}"],
        )
    if "session" in lowered or "token" in lowered or "auth" in lowered:
        return IncidentBundle(
            focus_files=[
                "quay/auth/sessions.py",
                "quay/auth/policies.py",
                "quay/audit/log.py",
                "quay/tenants/context.py",
            ],
            docs=[
                "docs/runbooks/token-revocation.md",
                "docs/adr/001-tenant-isolation.md",
            ],
            configs=["config/auth.toml", "config/quay.toml"],
            notes=[f"tenant={tenant_id}", f"mode={mode}"],
        )
    return IncidentBundle(
        focus_files=[
            "quay/billing/invoices.py",
            "quay/events/outbox.py",
            "quay/db/schema.py",
            "quay/config/loaders.py",
        ],
        docs=["docs/architecture/service-map.md"],
        configs=["config/billing.toml", "config/quay.toml"],
        notes=[f"tenant={tenant_id}", f"mode={mode}"],
    )
