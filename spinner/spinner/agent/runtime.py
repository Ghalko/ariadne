from __future__ import annotations

from spinner.agent.executor import execute_plan
from spinner.agent.planner import build_plan
from spinner.context.packer import pack_context
from spinner.models import RunResult, TaskRequest
from spinner.retrieval.pipeline import RetrievalPipeline
from spinner.sessions.store import record_session_run


class AgentRuntime:
    def __init__(self) -> None:
        self.pipeline = RetrievalPipeline()

    def run(self, request: TaskRequest) -> RunResult:
        candidates = self.pipeline.retrieve(workspace=request.workspace, query=request.query, mode=request.mode)
        context = pack_context(request.mode, candidates)
        plan = build_plan(request, [candidate.path for candidate in candidates])
        result = execute_plan(plan)
        result.message = f"{result.message} Packed {len(context.summaries)} summaries."
        record_session_run(request=request, result=result, context=context)
        return result
