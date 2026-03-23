from __future__ import annotations

from spinner.sessions.store import RUN_LOG


def list_runs() -> list[dict]:
    return list(RUN_LOG)
