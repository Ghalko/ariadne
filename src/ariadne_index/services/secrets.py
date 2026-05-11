from __future__ import annotations

import fnmatch
import re
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any


SECRET_EXCLUDE_GLOBS = [
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
    ".aws/**",
    "**/.aws/**",
    ".ssh/**",
    "**/.ssh/**",
    "secrets.*",
    "**/secrets.*",
    "secret.*",
    "**/secret.*",
    "credentials.*",
    "**/credentials.*",
    "*.pem",
    "**/*.pem",
    "*.key",
    "**/*.key",
    "*.p12",
    "**/*.p12",
    "*.pfx",
    "**/*.pfx",
    "id_rsa",
    "**/id_rsa",
    "id_dsa",
    "**/id_dsa",
    "id_ecdsa",
    "**/id_ecdsa",
    "id_ed25519",
    "**/id_ed25519",
]

_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b("
    r"api[_-]?key|apikey|secret|token|password|passwd|pwd|private[_-]?key|"
    r"access[_-]?key|client[_-]?secret|auth[_-]?token"
    r")\b(\s*[:=]\s*)([\"']?)([^\"'\s,}#]+)([\"']?)"
)
_SECRET_KEY_NAME_RE = re.compile(
    r"(?i)\b("
    r"api[_-]?key|apikey|secret|token|password|passwd|pwd|private[_-]?key|"
    r"access[_-]?key|client[_-]?secret|auth[_-]?token"
    r")\b"
)
_AWS_ACCESS_KEY_RE = re.compile(r"\bA(?:KI|SI)A[0-9A-Z]{16}\b")
_GITHUB_TOKEN_RE = re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")
_SLACK_TOKEN_RE = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
_BEARER_TOKEN_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b")
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)


def looks_like_secret_path(relative_path: str) -> bool:
    lowered = relative_path.lower()
    return any(fnmatch.fnmatch(lowered, pattern.lower()) for pattern in SECRET_EXCLUDE_GLOBS)


def redact_secrets(text: str | None) -> str | None:
    if text is None:
        return None

    redacted = _PRIVATE_KEY_RE.sub("[REDACTED_PRIVATE_KEY]", text)
    redacted = _AWS_ACCESS_KEY_RE.sub("[REDACTED_AWS_ACCESS_KEY]", redacted)
    redacted = _GITHUB_TOKEN_RE.sub("[REDACTED_GITHUB_TOKEN]", redacted)
    redacted = _SLACK_TOKEN_RE.sub("[REDACTED_SLACK_TOKEN]", redacted)
    redacted = _BEARER_TOKEN_RE.sub("Bearer [REDACTED_TOKEN]", redacted)
    return _SECRET_ASSIGNMENT_RE.sub(r"\1\2\3[REDACTED]\5", redacted)


def redact_secret_values(value: Any) -> Any:
    if isinstance(value, Enum):
        return value
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, Mapping):
        return {
            key: "[REDACTED]" if isinstance(key, str) and _SECRET_KEY_NAME_RE.search(key) else redact_secret_values(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [redact_secret_values(item) for item in value]
    return value
