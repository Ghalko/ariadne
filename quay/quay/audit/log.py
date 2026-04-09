from __future__ import annotations

AUDIT_LOG: list[dict] = []


def append_audit_event(kind: str, payload: dict) -> None:
    AUDIT_LOG.append({"kind": kind, "payload": payload})
