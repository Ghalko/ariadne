from __future__ import annotations

from spinner.models import TaskRequest


def classify_task(request: TaskRequest) -> str:
    query = request.query.lower()
    if "refactor" in query or request.mode.value == "refactor":
        return "refactor"
    if "fix" in query or request.mode.value == "bugfix":
        return "bugfix"
    return "understand"
