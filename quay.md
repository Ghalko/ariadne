# Quay

`quay` is the second internal fixture repo for Ariadne.

It complements `spinner` by stressing a different retrieval shape:

- heavier config influence on runtime behavior
- multi-tenant service boundaries
- docs and runbooks attached to operational code paths
- schemas, policies, and service modules rather than coding-runtime internals

`quay` is not an IDE. It is a service-platform fixture.

## Purpose

At a high level, `quay` should model a small internal platform service that handles:

- tenant-aware API requests
- webhook intake and replay
- billing and invoice events
- auth/session policy
- background jobs
- config-driven behavior
- operational runbooks and ADRs

That gives Ariadne a second repo shape that should be good for:

- config-to-code retrieval
- docs and runbooks that constrain behavior
- subsystem boundary questions
- schema and data-model retrieval
- tenant isolation and policy queries

## Proposed Layout

`quay/`

- `quay/api/`
- `quay/auth/`
- `quay/audit/`
- `quay/billing/`
- `quay/config/`
- `quay/db/`
- `quay/events/`
- `quay/jobs/`
- `quay/service/`
- `quay/tenants/`
- `quay/webhooks/`
- `config/`
- `docs/adr/`
- `docs/architecture/`
- `docs/runbooks/`
- `tests/unit/`
- `tests/integration/`

## Core Subsystems

### API and service entry

- route handlers for webhook intake and tenant-scoped actions
- service runtime that routes incident-style queries to the right subsystem

### Auth and tenancy

- tenant access checks
- session revocation rules
- tenant context extraction from headers

### Billing and events

- invoice creation
- event emission and outbox behavior
- billing policies that affect retries and delivery

### Webhooks and jobs

- signature verification
- failed-delivery replay
- retry job dispatch

### Config and schema

- service settings
- webhook/auth/billing config files
- schema helper functions and query helpers

### Docs and memory-style artifacts

- ADRs for tenant isolation and webhook idempotency
- runbooks for replay failures and token revocation
- architecture note for service boundaries

## Benchmark Tasks Quay Should Support

- “What config affects webhook retry behavior?”
- “Which files enforce tenant isolation?”
- “What runbook applies to failed webhook replay?”
- “Which schema and query paths matter for invoice creation?”
- “Where is session revocation handled and what decision constrains it?”
- “What tests cover replaying failed webhooks?”

## Target Complexity

Initial scaffold should include:

- 20-30 Python source files
- 4-6 docs
- 3-4 config files
- 3-5 tests

That is enough to be useful without becoming noise.

## Why Quay Complements Spinner

`spinner` is a coding-runtime fixture.

`quay` should be:

- more service-oriented
- more config-sensitive
- more policy-driven
- more operationally grounded

Together they give Ariadne two different benchmark shapes:

- agent/runtime retrieval
- service/platform retrieval

That is a much healthier place to evaluate the system than overfitting on one repo alone.
