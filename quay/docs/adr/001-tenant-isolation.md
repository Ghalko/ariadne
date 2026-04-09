# ADR 001: Tenant Isolation

Quay enforces strict tenant isolation at the service boundary. Cross-tenant reads should be rejected before query execution and logged as audit events.
