from __future__ import annotations


def verify_signature(*, headers: dict[str, str], body: str, secret: str) -> bool:
    supplied = headers.get("x-quay-signature", "")
    return supplied == f"sha256:{secret}:{len(body)}"
