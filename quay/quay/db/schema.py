from __future__ import annotations


def describe_schema() -> dict[str, list[str]]:
    return {
        "webhook_deliveries": ["tenant_id", "event_id", "attempt_count", "status"],
        "sessions": ["tenant_id", "session_id", "revoked_at", "reason"],
        "invoices": ["tenant_id", "invoice_id", "plan_code", "amount_cents"],
    }
