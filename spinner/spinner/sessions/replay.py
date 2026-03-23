from __future__ import annotations

from spinner.sessions.history import list_runs


def replay_latest() -> dict | None:
    runs = list_runs()
    return runs[-1] if runs else None
