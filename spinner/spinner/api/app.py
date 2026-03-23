from __future__ import annotations

from spinner.api.routes.retrieve import retrieve_payload
from spinner.api.routes.tasks import run_task_payload


def app() -> dict:
    return {
        "status": "ok",
        "routes": {
            "/retrieve": retrieve_payload,
            "/tasks/run": run_task_payload,
        },
    }
