from __future__ import annotations

from dataclasses import asdict

from spinner.models import TaskMode
from spinner.retrieval.pipeline import RetrievalPipeline


def retrieve_payload(workspace: str, query: str, mode: str = "understand") -> dict:
    pipeline = RetrievalPipeline()
    results = pipeline.retrieve(workspace=workspace, query=query, mode=TaskMode(mode))
    return {
        "workspace": workspace,
        "query": query,
        "mode": mode,
        "results": [asdict(candidate) for candidate in results],
    }
