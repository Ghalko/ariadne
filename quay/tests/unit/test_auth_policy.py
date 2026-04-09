from __future__ import annotations

from quay.auth.policies import can_access_tenant


def test_cross_tenant_access_is_denied() -> None:
    assert can_access_tenant("acme", "beta") is False
