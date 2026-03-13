# ADR 009: Compliance Conflict Resolution

Status: Accepted

The policy gate must treat compliance conflicts as a first-class blocked state, not as a side effect of simple deny precedence.

## Decision

Compliance rules now resolve by these rules:

- Only rules matching the current target (`*`, the requested tool, or the tenant's industry pack) are considered.
- Matching rules are grouped by `metadata.conflict_key`, then `metadata.disclosure_key`, then `target`.
- If a group contains more than one effect (`allow`, `deny`, `escalate`), the result is always `escalate`.
- If there is no mixed-effect conflict, precedence is `deny > escalate > allow`.
- If no allow rule matches a tool invocation, the gate remains deny-by-default.
- Tenant settings may escalate policy violations that are otherwise pure denies, but they do not downgrade a true mixed-effect conflict. Conflicts always block pending operator review.

## Why

The architecture spec already established "most restrictive wins," but that principle was too underspecified for real rule authoring. In practice there are two distinct cases:

- pure restriction: one or more matching deny rules, no contradiction
- contradiction: the same compliance surface is simultaneously allowed and denied or otherwise mixed

Those should not collapse to the same runtime outcome. A contradiction indicates policy ambiguity and requires operator review.

## Implementation Notes

- Runtime policy evaluation now resolves conflicts explicitly in [policy_gate.py](/Users/rashidbaset/Documents/calllock-agenticos/harness/src/harness/nodes/policy_gate.py).
- Supabase conflict introspection is implemented in [044_compliance_conflict_resolution_v2.sql](/Users/rashidbaset/Documents/calllock-agenticos/supabase/migrations/044_compliance_conflict_resolution_v2.sql).
- Local seed compliance rules now include `scope`, `rule_type`, and `metadata.conflict_key` in [local_seed.json](/Users/rashidbaset/Documents/calllock-agenticos/supabase/local_seed.json).

## Consequences

- Compliance authors must supply a stable `metadata.conflict_key` when multiple rules speak to the same disclosure or action surface.
- True contradictions surface as `escalate`, which means more operator review but avoids silently choosing a permissive interpretation.
- The gate remains deny-by-default, so this does not weaken existing safety behavior.
