from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TenantRequest:
    tenant_id: str
    actor_tenant_id: str
    path: str
    query: str
    mode: str


@dataclass(slots=True)
class IncidentBundle:
    focus_files: list[str]
    docs: list[str]
    configs: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class InvoiceRecord:
    tenant_id: str
    plan_code: str
    amount_cents: int
    currency: str = "usd"
