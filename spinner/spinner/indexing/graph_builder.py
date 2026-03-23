from __future__ import annotations


def build_graph_hints(path: str) -> list[str]:
    hints: list[str] = []
    if "retrieval/pipeline.py" in path:
        hints.extend(["context/packer.py", "providers/embeddings.py", "telemetry/events.py"])
    if "patching/apply.py" in path:
        hints.extend(["patching/validation.py", "patching/rollback.py", "sessions/store.py"])
    if "agent/runtime.py" in path:
        hints.extend(["retrieval/pipeline.py", "agent/planner.py", "agent/executor.py"])
    return hints
