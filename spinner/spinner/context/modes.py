from __future__ import annotations

from spinner.models import TaskMode

MODE_TOKEN_LIMITS = {
    TaskMode.understand: 1800,
    TaskMode.refactor: 2400,
    TaskMode.bugfix: 2200,
    TaskMode.docs: 1600,
}


def token_limit_for_mode(mode: TaskMode) -> int:
    return MODE_TOKEN_LIMITS[mode]
