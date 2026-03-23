from __future__ import annotations

from spinner.context.token_budget import estimate_tokens, fits_budget


def test_token_estimation_is_positive() -> None:
    parts = ["spinner retrieval pipeline", "patch rollback policy"]
    assert estimate_tokens(parts) > 0
    assert fits_budget(parts, 100)
