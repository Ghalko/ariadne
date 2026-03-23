from __future__ import annotations

from spinner.models import PatchPlan


def render_diff(plan: PatchPlan) -> str:
    touched = "\n".join(f"+++ {path}" for path in plan.target_files)
    return f"# Patch plan\n# {plan.summary}\n{touched}"
