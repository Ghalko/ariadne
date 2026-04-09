from __future__ import annotations

from quay.webhooks.replay import replay_failed_deliveries


def test_replay_failed_deliveries_enqueues_jobs() -> None:
    jobs = replay_failed_deliveries("acme", limit=1)
    assert jobs
    assert jobs[0]["job"] == "webhook_retry"
