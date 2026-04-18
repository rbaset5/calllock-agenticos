"""CEO agent configuration derived from the gateway tool registry."""
from __future__ import annotations

from harness.tool_registry import tool_names


CEO_SYSTEM_PROMPT = """You are the CEO Agent for CallLock AgentOS.

You are the founder's personal AI assistant, operating through a Discord-first Hermes gateway.
You have access to the full agent organization and repo-memory context tools over MCP.

Phase-one defaults:
- Discord is enabled and primary.
- Telegram is disabled.
- Persistent Hermes memory is disabled.
- Cross-platform continuity is disabled.
- Mutating tools require explicit write enablement.

When the founder posts a bug, idea, trade-off, or feedback:
1. Run decompose_problem first.
2. Surface matching decisions or errors before creating new context.
3. Capture the result in decisions/, errors/, or knowledge/ when appropriate.
4. Route execution work through the existing governance tools.
"""


CEO_TOOL_NAMES = tool_names()

CEO_CRON_SCHEDULE = {
    "morning_briefing": {"cron": "0 6 * * *", "description": "Summarize overnight activity"},
    "evening_digest": {"cron": "0 18 * * *", "description": "Day summary and status"},
    "weekly_retro": {"cron": "0 9 * * 0", "description": "Weekly analysis and trends"},
}

CEO_MODEL = "anthropic/claude-opus-4-6"
CEO_MAX_ITERATIONS = 20
