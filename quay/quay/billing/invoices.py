from __future__ import annotations

from quay.events.outbox import publish_billing_event
from quay.models import InvoiceRecord


def create_invoice(tenant_id: str, plan_code: str, amount_cents: int) -> InvoiceRecord:
    invoice = InvoiceRecord(tenant_id=tenant_id, plan_code=plan_code, amount_cents=amount_cents)
    publish_billing_event("invoice.created", tenant_id=tenant_id, payload={"plan_code": plan_code, "amount_cents": amount_cents})
    return invoice
