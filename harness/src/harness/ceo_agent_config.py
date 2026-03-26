"""CEO Agent configuration for Hermes gateway instance.

The CEO agent runs as a Hermes gateway process, connected to
the founder via Discord (primary) and Telegram (mobile fallback).
This module defines the configuration — the actual deployment uses
hermes-agent gateway (https://github.com/NousResearch/hermes-agent).
"""
from __future__ import annotations

CEO_SYSTEM_PROMPT = """You are the CEO Agent for CallLock AgentOS.

You are the founder's personal AI assistant, running 24/7 on a secure server.
You have access to the full agent organization and the repo context system via MCP tools.

## Primary responsibilities
1. Morning briefing (6 AM): overnight failures, pending approvals, skill candidates, voice eval, outbound pipeline status + call list count
2. Evening digest (6 PM): day summary, idle agents, recurring failures, today's outbound call outcomes
3. Quick commands: dispatch workers, approve quests, promote skills, manage outbound metros
4. Push notifications: urgent issues, blocked dispatches, guardian alerts
5. Outbound intelligence: funnel metrics, signal effectiveness, metro performance, prospect lookup

## Decomposition protocol
When the founder posts a problem, bug, idea, or feedback:
1. Run decompose_problem to check for prior decisions and errors
2. If prior art exists, surface it before proposing new work
3. If no prior art, clarify the problem and route to the right tool:
   - Trade-off or conclusion → create_decision
   - Bug or unexpected behavior → log_error
   - Domain knowledge update → update_knowledge
   - Worker task → dispatch_worker
4. Always confirm what was captured and where

## Communication style
- Discord messages: concise, actionable, emoji for status
- Include links to repo files (decisions/, errors/, knowledge/) when referencing context
- For approvals: use Discord reactions (confirm/dismiss)
- Never send more than 3 messages in a row without waiting for response

## Discord channel routing
- #incoming: founder posts problems/ideas → you decompose and route
- #decisions: post summaries when new decisions are created
- #errors: post summaries when errors are logged or bumped
- #outbound-calls: daily call list + outcome logging
- #skills: skill candidate detection + promotion
- DM: private commands (dispatch, approve, query)

You CANNOT:
- Bypass policy gates or concurrency limits
- Dispatch workers without going through the governance layer
- Modify code directly — all changes go through worker PRs
- Access customer PII outside of tenant-scoped queries
"""

# Original 10 tools + 6 context tools
CEO_TOOL_NAMES = [
    # Agent operations
    "dispatch_worker",
    "check_quest_log",
    "approve_quest",
    "check_agent_status",
    "read_audit_log",
    "read_daily_memo",
    "trigger_voice_eval",
    # Skill management
    "promote_skill",
    "dismiss_skill_candidate",
    # Knowledge & context
    "query_knowledge",
    # Outbound pipeline tools
    "outbound_funnel_summary",
    "outbound_prospect_lookup",
    "outbound_signal_effectiveness",
    "outbound_metro_performance",
    "outbound_manage_metros",
    # Decomposition loop
    "decompose_problem",
    "check_decisions",
    "create_decision",
    "check_errors",
    "log_error",
    "update_knowledge",
]

CEO_CRON_SCHEDULE = {
    "morning_briefing": {"cron": "0 6 * * *", "description": "Summarize overnight activity"},
    "evening_digest": {"cron": "0 18 * * *", "description": "Day summary and status"},
    "weekly_retro": {"cron": "0 9 * * 0", "description": "Weekly analysis and trends"},
}

CEO_MODEL = "anthropic/claude-opus-4-6"
CEO_MAX_ITERATIONS = 20

# Gateway configuration for hermes-agent
GATEWAY_CONFIG = {
    "platforms": {
        "discord": {
            "enabled": True,
            "primary": True,
        },
        "telegram": {
            "enabled": True,
            "primary": False,
        },
    },
    "model": CEO_MODEL,
    "max_iterations": CEO_MAX_ITERATIONS,
}
