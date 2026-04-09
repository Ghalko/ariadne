from __future__ import annotations

from quay.service.runtime import diagnose_incident


def test_runtime_returns_webhook_bundle() -> None:
    bundle = diagnose_incident(
        query="Investigate webhook replay failures for tenant acme",
        mode="incident",
        tenant_id="acme",
    )
    assert "quay/webhooks/replay.py" in bundle.focus_files
    assert "docs/runbooks/webhook-replay-failures.md" in bundle.docs
