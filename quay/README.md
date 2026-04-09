# Quay

Quay is a config-heavy service platform fixture repo used to benchmark Ariadne on operational service code rather than coding-runtime internals.

## Main Concepts

- tenant isolation and access policy
- webhook verification and replay
- billing events and invoice handling
- config-driven service behavior
- audit logging and operational runbooks

## Layout

- `quay/api/`: request entry points
- `quay/auth/`: tenant access and session policy
- `quay/audit/`: audit event logging
- `quay/billing/`: invoices and plans
- `quay/config/`: runtime settings and feature flags
- `quay/db/`: schema and query helpers
- `quay/events/`: outbox event publishing
- `quay/jobs/`: async retry dispatch
- `quay/service/`: incident-oriented runtime
- `quay/tenants/`: tenant context extraction
- `quay/webhooks/`: signature verification and replay
- `docs/`: ADRs, runbooks, architecture notes
- `config/`: TOML configs used by the service

## Run

```bash
uv venv --python 3.14
source .venv/bin/activate
uv sync
quay diagnose quay "Investigate webhook replay failures for tenant acme" --mode incident
```
