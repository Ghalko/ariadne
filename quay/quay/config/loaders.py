from __future__ import annotations


def load_service_settings() -> dict:
    return {
        "strict_isolation": True,
        "max_retry_attempts": 5,
        "replay_batch_size": 25,
        "emit_invoice_events": True,
    }
