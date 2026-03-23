from __future__ import annotations

from spinner.context.modes import token_limit_for_mode
from spinner.context.snippets import pick_snippets
from spinner.context.token_budget import estimate_tokens
from spinner.models import ContextBundle, RetrievalCandidate, TaskMode
from spinner.telemetry.incidents import maybe_warn_on_large_context


def pack_context(mode: TaskMode, candidates: list[RetrievalCandidate]) -> ContextBundle:
    summaries = [candidate.summary or candidate.path for candidate in candidates[:6]]
    snippets = pick_snippets(candidates)
    memories = [
        "ADR: summary-first context beats dumping raw files",
        "Runbook: provider quota failures should fall back cleanly",
    ]
    token_budget = token_limit_for_mode(mode)
    estimated_tokens = estimate_tokens([*summaries, *snippets, *memories])
    maybe_warn_on_large_context(mode=mode.value, estimated_tokens=estimated_tokens, budget=token_budget)
    return ContextBundle(
        mode=mode,
        summaries=summaries,
        snippets=snippets,
        memories=memories,
        estimated_tokens=estimated_tokens,
    )
