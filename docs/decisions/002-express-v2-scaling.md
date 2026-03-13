# ADR 002: Express V2 Horizontal Scaling

Status: Accepted

## Context

Express V2 on Render handles webhook ingress from Retell AI and serves API routes. It parses webhooks and emits Inngest events — stateless and lightweight. The harness runs as a separate Render service.

Current load is 1 contractor × 3 trades = low tens of calls/day. At 10 tenants × 3 trades, Express V2 still operates well within single-instance capacity for a Node.js server.

## Decision

Express V2 remains single-instance by default.

Revisit when, over a sustained window, any of these hold:

- Webhook p95 latency > 2s
- CPU > 80%
- Memory pressure or restarts appear
- Webhook backlog or 5xx rate rises materially

When triggered: run multiple stateless instances behind the platform load balancer, preserving statelessness and idempotent webhook handling.

## Consequences

- No scaling infrastructure needed now
- Scaling triggers are documented and measurable
- Scaling Express V2 is only useful if the bottleneck is actually ingress — if Inngest, the harness, or downstream services are the choke point, adding Express instances will not help
