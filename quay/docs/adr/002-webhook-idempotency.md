# ADR 002: Webhook Idempotency

Webhook replay must remain idempotent. Replayed deliveries should reuse event identifiers and honor the configured retry batch size.
