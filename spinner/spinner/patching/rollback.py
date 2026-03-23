from __future__ import annotations

from spinner.models import PatchPlan


def rollback_message(plan: PatchPlan) -> str:
    return f"Rollback prepared for {plan.task_id}: {plan.rollback_hint}"
