from __future__ import annotations

from quay.audit.log import append_audit_event


def revoke_session(session_id: str, reason: str) -> dict:
    append_audit_event("session_revoked", {"session_id": session_id, "reason": reason})
    return {"session_id": session_id, "status": "revoked", "reason": reason}
