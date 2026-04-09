from __future__ import annotations


def current_tenant(headers: dict[str, str]) -> str:
    return headers.get("x-tenant-id", "acme")
