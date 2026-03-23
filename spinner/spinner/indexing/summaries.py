from __future__ import annotations


def summarize_file(path: str) -> str:
    if "retrieval" in path:
        return f"{path}: retrieval pipeline or scoring logic"
    if "patching" in path:
        return f"{path}: patch application or rollback logic"
    if "providers" in path:
        return f"{path}: provider model selection or fallback"
    if "context" in path:
        return f"{path}: context packing or token budgeting"
    return f"{path}: workspace runtime component"
