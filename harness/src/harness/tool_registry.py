from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from harness import ceo_tools, context_tools
from outbound import ceo_tools as outbound_ceo_tools


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    json_schema: JsonObject
    callable: Callable[..., Any]
    mutating: bool


DOMAIN_ENUM = ["voice-pipeline", "product", "architecture"]


def _object_schema(
    properties: JsonObject,
    *,
    required: list[str] | None = None,
    additional_properties: bool = False,
) -> JsonObject:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": additional_properties,
    }


REGISTRY: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="dispatch_worker",
        description="Send a task to any worker in the agent roster.",
        json_schema=_object_schema(
            {
                "worker_id": {"type": "string", "description": "Worker ID from knowledge/worker-specs."},
                "tenant_id": {"type": "string", "description": "Tenant ID or slug."},
                "task_type": {"type": "string"},
                "problem_description": {"type": "string", "default": ""},
                "feature_flags": {"type": "object", "default": {}, "additionalProperties": True},
            },
            required=["worker_id", "tenant_id", "task_type"],
        ),
        callable=ceo_tools.dispatch_worker,
        mutating=True,
    ),
    ToolSpec(
        name="check_quest_log",
        description="Read pending approval requests.",
        json_schema=_object_schema(
            {
                "tenant_id": {"type": "string"},
                "status": {"type": "string", "default": "pending"},
            }
        ),
        callable=ceo_tools.check_quest_log,
        mutating=False,
    ),
    ToolSpec(
        name="approve_quest",
        description="Approve a blocked dispatch or quest.",
        json_schema=_object_schema(
            {
                "approval_id": {"type": "string"},
                "approved_by": {"type": "string", "default": "founder"},
            },
            required=["approval_id"],
        ),
        callable=ceo_tools.approve_quest,
        mutating=True,
    ),
    ToolSpec(
        name="promote_skill",
        description="Extract and save a skill from a completed run.",
        json_schema=_object_schema(
            {
                "candidate_id": {"type": "string"},
                "skill_title": {"type": "string"},
                "skill_body": {"type": "string"},
                "universal": {"type": "boolean", "default": True},
                "promoted_by": {"type": "string", "default": "founder"},
            },
            required=["candidate_id", "skill_title", "skill_body"],
        ),
        callable=ceo_tools.promote_skill,
        mutating=True,
    ),
    ToolSpec(
        name="dismiss_skill_candidate",
        description="Mark a skill candidate as reviewed and dismissed.",
        json_schema=_object_schema(
            {
                "candidate_id": {"type": "string"},
                "reason": {"type": "string", "default": ""},
            },
            required=["candidate_id"],
        ),
        callable=ceo_tools.dismiss_skill_candidate,
        mutating=True,
    ),
    ToolSpec(
        name="read_daily_memo",
        description="Get aggregated status across all agents.",
        json_schema=_object_schema(
            {
                "tenant_id": {"type": "string"},
            },
            required=["tenant_id"],
        ),
        callable=ceo_tools.read_daily_memo,
        mutating=False,
    ),
    ToolSpec(
        name="query_knowledge",
        description="Read from the knowledge graph.",
        json_schema=_object_schema(
            {
                "path": {"type": "string", "description": "Path relative to knowledge/."},
            },
            required=["path"],
        ),
        callable=ceo_tools.query_knowledge,
        mutating=False,
    ),
    ToolSpec(
        name="check_agent_status",
        description="Check current state of agents (idle/active/queued).",
        json_schema=_object_schema(
            {
                "worker_id": {"type": "string"},
            }
        ),
        callable=ceo_tools.check_agent_status,
        mutating=False,
    ),
    ToolSpec(
        name="read_audit_log",
        description="Read recent command audit log entries.",
        json_schema=_object_schema(
            {
                "tenant_id": {"type": "string"},
                "action_type": {"type": "string"},
                "limit": {"type": "integer", "default": 20, "minimum": 1},
            }
        ),
        callable=ceo_tools.read_audit_log,
        mutating=False,
    ),
    ToolSpec(
        name="trigger_voice_eval",
        description="Kick off a voice pipeline evaluation run.",
        json_schema=_object_schema(
            {
                "tenant_id": {"type": "string"},
            },
            required=["tenant_id"],
        ),
        callable=ceo_tools.trigger_voice_eval,
        mutating=True,
    ),
    ToolSpec(
        name="outbound_funnel_summary",
        description="Summarize outbound pipeline funnel metrics for a recent time window.",
        json_schema=_object_schema(
            {
                "days": {"type": "integer", "default": 7, "minimum": 1},
            }
        ),
        callable=outbound_ceo_tools.outbound_funnel_summary,
        mutating=False,
    ),
    ToolSpec(
        name="outbound_prospect_lookup",
        description="Look up a specific prospect's outbound history by business name or phone.",
        json_schema=_object_schema(
            {
                "business_name": {"type": "string", "default": ""},
                "phone": {"type": "string", "default": ""},
            }
        ),
        callable=outbound_ceo_tools.outbound_prospect_lookup,
        mutating=False,
    ),
    ToolSpec(
        name="outbound_signal_effectiveness",
        description="Compare outbound signal types by positive call outcome rate.",
        json_schema=_object_schema({}),
        callable=outbound_ceo_tools.outbound_signal_effectiveness,
        mutating=False,
    ),
    ToolSpec(
        name="outbound_metro_performance",
        description="Compare outbound metros by answer rate and interest rate.",
        json_schema=_object_schema({}),
        callable=outbound_ceo_tools.outbound_metro_performance,
        mutating=False,
    ),
    ToolSpec(
        name="outbound_manage_metros",
        description="Add or remove a target outbound metro in repo memory.",
        json_schema=_object_schema(
            {
                "action": {"type": "string", "enum": ["add", "remove"]},
                "metro": {"type": "string"},
            },
            required=["action", "metro"],
        ),
        callable=outbound_ceo_tools.outbound_manage_metros,
        mutating=True,
    ),
    ToolSpec(
        name="decompose_problem",
        description="Analyze a founder problem, detect domain, search prior art, and recommend the next tool action.",
        json_schema=_object_schema(
            {
                "raw_input": {"type": "string"},
            },
            required=["raw_input"],
        ),
        callable=context_tools.decompose_problem,
        mutating=False,
    ),
    ToolSpec(
        name="check_decisions",
        description="Search the decisions index for prior decisions matching a query.",
        json_schema=_object_schema(
            {
                "query": {"type": "string"},
                "domain": {"type": "string", "enum": DOMAIN_ENUM},
            },
            required=["query"],
        ),
        callable=context_tools.check_decisions,
        mutating=False,
    ),
    ToolSpec(
        name="create_decision",
        description="Write a new decision record to the repo and update decisions/_index.md.",
        json_schema=_object_schema(
            {
                "title": {"type": "string"},
                "domain": {"type": "string", "enum": DOMAIN_ENUM},
                "context": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": _object_schema(
                        {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        additional_properties=False,
                    ),
                    "minItems": 1,
                },
                "decision": {"type": "string"},
                "consequences": {"type": "string"},
                "status": {"type": "string", "default": "active"},
            },
            required=["title", "domain", "context", "options", "decision", "consequences"],
        ),
        callable=context_tools.create_decision,
        mutating=True,
    ),
    ToolSpec(
        name="check_errors",
        description="Search the errors index for known error patterns matching a query.",
        json_schema=_object_schema(
            {
                "query": {"type": "string"},
                "domain": {"type": "string", "enum": DOMAIN_ENUM},
            },
            required=["query"],
        ),
        callable=context_tools.check_errors,
        mutating=False,
    ),
    ToolSpec(
        name="log_error",
        description="Create or update an error pattern and bump occurrences for repeats.",
        json_schema=_object_schema(
            {
                "title": {"type": "string"},
                "domain": {"type": "string", "enum": DOMAIN_ENUM},
                "symptoms": {"type": "string"},
                "root_cause": {"type": "string", "default": ""},
                "fix": {"type": "string", "default": ""},
                "pattern_notes": {"type": "string", "default": ""},
                "status": {"type": "string", "default": "logged"},
            },
            required=["title", "domain", "symptoms"],
        ),
        callable=context_tools.log_error,
        mutating=True,
    ),
    ToolSpec(
        name="update_knowledge",
        description="Write or append content to a file under knowledge/.",
        json_schema=_object_schema(
            {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "append": {"type": "boolean", "default": False},
            },
            required=["path", "content"],
        ),
        callable=context_tools.update_knowledge,
        mutating=True,
    ),
)


REGISTRY_BY_NAME = {tool.name: tool for tool in REGISTRY}


def get_tool(name: str) -> ToolSpec:
    try:
        return REGISTRY_BY_NAME[name]
    except KeyError as exc:
        raise KeyError(f"Unknown gateway tool: {name}") from exc


def list_tools() -> list[ToolSpec]:
    return list(REGISTRY)


def tool_names() -> list[str]:
    return [tool.name for tool in REGISTRY]


def mutating_tool_names() -> list[str]:
    return [tool.name for tool in REGISTRY if tool.mutating]


def exported_tools_manifest() -> JsonObject:
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "json_schema": tool.json_schema,
                "mutating": tool.mutating,
            }
            for tool in REGISTRY
        ]
    }


def tools_json_text() -> str:
    return json.dumps(exported_tools_manifest(), indent=2, sort_keys=True) + "\n"


def export_tools_json(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(tools_json_text())
    return target


def resolve_granted_tools(
    authored: Iterable[str],
    tenant_allowed: Iterable[str] | None = None,
    environment_allowed: Iterable[str] | None = None,
    runtime_denied: Iterable[str] | None = None,
) -> list[str]:
    authored_set = {tool for tool in authored if tool}
    tenant_set = set(tenant_allowed or authored_set)
    environment_set = set(environment_allowed or authored_set)
    denied_set = set(runtime_denied or [])
    granted = authored_set & tenant_set & environment_set
    return sorted(granted - denied_set)
