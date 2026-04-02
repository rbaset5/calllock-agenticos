"""Conversational Sales Assistant — Discord bot via Gateway (websocket).

Connects to Discord as a bot, listens for @mentions in any channel,
uses LLM tool-calling to query harness data functions, and replies
with formatted answers. Runs as a background task inside the harness process.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
from datetime import date
from typing import Any

try:
    import discord
except Exception:  # pragma: no cover
    discord = None  # type: ignore[assignment]

try:
    from litellm import completion
except Exception:  # pragma: no cover
    completion = None  # type: ignore[assignment]

from . import store
from .constants import OUTBOUND_TENANT_ID
from .daily_plan import build_daily_plan, get_week_config, load_schedule
from . import queue_builder, sprint_state
from .lifecycle import classify_lead_type
from .scoreboard import sprint_scoreboard

logger = logging.getLogger(__name__)

DIALER_BASE_URL = os.getenv("DIALER_BASE_URL", "http://localhost:3004")

INTENT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("WHAT_NEXT", (r"\bwhat('?s| is)? next\b", r"\bwhat should i do\b", r"^next$")),
    ("OPEN_DIALER", (r"\bopen dialer\b", r"\bstart dialing\b")),
    ("OPEN_HUD", (r"\bopen hud\b", r"\bcoaching\b")),
    ("SHOW_CALLBACKS", (r"\bcallbacks?\b", r"\bcallbacks due\b")),
    ("SHOW_FOUNDER_TOUCH", (r"\bfounder touch\b", r"\bhot leads\b", r"\bwho needs attention\b")),
    ("SHOW_DIGEST", (r"\bstats\b", r"\bscoreboard\b", r"\bhow am i doing\b")),
    ("SHOW_FULL_DAY", (r"\bfull day\b", r"\bshow all blocks\b", r"\btoday'?s plan\b")),
    ("END_MY_DAY", (r"\bend my day\b", r"\bshutdown\b", r"\bdone for today\b")),
]


def route_intent(message_text: str) -> str | None:
    text = message_text.strip().lower()
    for intent, patterns in INTENT_PATTERNS:
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            return intent
    return None


def _dialer_link(block: str | None, segment: str | None, view: str) -> str:
    query = []
    if block:
        query.append(f"block={block}")
    if segment:
        query.append(f"segment={segment}")
    query.append(f"view={view}")
    suffix = "&".join(query)
    path = "/hud" if view == "hud" else "/"
    return f"{DIALER_BASE_URL}{path}?{suffix}"


def _build_shutdown_log() -> str:
    schedule = load_schedule()
    today = date.today()
    metrics = sprint_scoreboard(OUTBOUND_TENANT_ID, today)
    state = sprint_state.get_current_state()
    week_config = get_week_config(schedule, metrics.get("week", 0)) or {}
    fields = week_config.get("shutdown_fields", [])
    mapping = {
        "dials": metrics.get("daily_dials", 0),
        "connects": metrics.get("live_conversations", 0),
        "demos": metrics.get("demos_booked_today", 0),
        "close_attempts": metrics.get("close_attempts_today", 0),
        "customers_signed": metrics.get("customers_signed", 0),
        "top_objection": (metrics.get("objection_summary") or [{}])[0].get("type", "---") if metrics.get("objection_summary") else "---",
    }
    lines = [f"- {field}: {mapping.get(field, '---')}" for field in fields]


    # Plan-vs-actual: schedule adherence
    dials_done = int(state.get("dials_completed_today", 0) or 0)
    dials_target = int(state.get("dials_target_today", 0) or 0)
    lines.append(f"- progress: {dials_done}/{dials_target} dials")

    try:
        calls = store.list_outbound_calls(tenant_id=OUTBOUND_TENANT_ID, start_date=today.isoformat())
        if calls:
            first_call_at = min(str(c.get("called_at", "")) for c in calls if c.get("called_at"))
            if first_call_at:
                lines.append(f"- first_dial: {first_call_at[:16]}")
    except Exception:
        pass


    return "\n".join(lines) if lines else "- dials: 0"


def _answer_intent(intent: str) -> str:
    state = sprint_state.get_current_state()
    block = str(state.get("current_block") or state.get("next_block") or "AM")
    segment = str(state.get("active_segment") or "")

    if intent in {"WHAT_NEXT", "OPEN_DIALER", "OPEN_HUD", "SHOW_CALLBACKS"} and not state.get("block_active"):
        if state.get("next_block"):
            return f"Sprint not active. Next block: {state['next_block']} at {state.get('next_block_at', '')}."
        return str(state.get("message") or "Sprint not active.")

    if intent in {"WHAT_NEXT", "OPEN_DIALER", "OPEN_HUD", "SHOW_CALLBACKS"}:
        queue = queue_builder.build_queue(block=block, segment=segment)
        dialer_link = _dialer_link(block, segment, "dialer")
        hud_link = _dialer_link(block, segment, "hud")
        if intent == "OPEN_DIALER":
            return dialer_link
        if intent == "OPEN_HUD":
            return hud_link
        if intent == "SHOW_CALLBACKS":
            callbacks = [prospect for prospect in queue.get("prospects", []) if prospect.get("stage") == "callback"][:10]
            if not callbacks:
                return "No callbacks due right now."
            return "\n".join([f"{prospect.get('business_name', 'Unknown')} · {prospect.get('metro', '')}" for prospect in callbacks])
        return (
            f"{block} Sprint {state.get('sprint_index', 0)} of {state.get('sprints_target_today', 0)}\n"
            f"Segment: {segment}\n"
            f"Queue: {queue.get('total', 0)} leads ({queue.get('summary', '0 callbacks, 0 interested, 0 follow-up, 0 fresh')})\n"
            f"Progress: {state.get('dials_completed_today', 0)}/{state.get('dials_target_today', 0)} dials today\n"
            f"Next segment: {state.get('next_segment_name') or '—'} ({state.get('minutes_until_next', '—')} min)\n\n"
            f"[Dialer]({dialer_link})\n"
            f"[HUD]({hud_link})\n\n"
            f"Instruction: {state.get('instruction', '')}"
        )

    if intent == "SHOW_FOUNDER_TOUCH":
        prospects = store.list_prospects_by_stages(["interested", "callback"], include_signals=True)
        flagged = [prospect for prospect in prospects if queue_builder.compute_needs_attention(prospect)]
        if not flagged:
            return "No founder-touch leads need attention right now."
        return "\n".join(
            [
                f"{prospect.get('business_name', 'Unknown')} · {prospect.get('stage')} · {prospect.get('metro', '')}"
                for prospect in flagged[:10]
            ]
        )

    if intent == "SHOW_DIGEST":
        metrics = sprint_scoreboard(OUTBOUND_TENANT_ID, date.today())
        return (
            f"Dials: {metrics.get('daily_dials', 0)}/{metrics.get('daily_target', 0)}\n"
            f"Connects: {metrics.get('live_conversations', 0)}\n"
            f"Demos: {metrics.get('demos_booked_today', 0)}\n"
            f"Weekly: {metrics.get('weekly_dials', 0)}/{metrics.get('weekly_target', 0)}"
        )

    if intent == "SHOW_FULL_DAY":
        queues = queue_builder.build_queue(block="all").get("queues", [])
        if not queues:
            return "No blocks configured for today."
        return "\n".join([f"{entry['block']}: {entry.get('summary', '0 callbacks, 0 interested, 0 follow-up, 0 fresh')}" for entry in queues])

    if intent == "END_MY_DAY":
        return _build_shutdown_log()

    return "I don't have a deterministic answer for that yet."

# ---------------------------------------------------------------------------
# LLM Tool Definitions
# ---------------------------------------------------------------------------

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_queue",
            "description": "Get the current calling queue with deep links to the dialer and HUD. Call this when the user wants to know what to do next, wants to start dialing, or asks about the current block's leads. Returns sprint state, queue breakdown, and clickable links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "block": {"type": "string", "description": "Optional block override (AM, MID, EOD). Defaults to current block."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_scoreboard",
            "description": "Get current sprint metrics: daily/weekly/cumulative dials, connect rate, streak, demos, close attempts, weekly progress.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_plan",
            "description": "Get today's calling plan: which blocks are active, sprint count, lead counts by type, coaching note, weekly goal.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pipeline_review",
            "description": "Get warm leads missing next steps, leads without clear follow-up actions, and pipeline health summary.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_digest",
            "description": "Get today's call stats: total calls, answered, interested, callbacks, voicemails, demos scheduled.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hot_leads",
            "description": "Get leads classified as hot (interested with demo or close attempt pending) and warm (callbacks, interested without next step).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Execution
# ---------------------------------------------------------------------------

def _execute_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a tool call and return the result."""
    today = date.today()
    tenant = OUTBOUND_TENANT_ID
    args = arguments or {}

    if name == "get_current_queue":
        state = sprint_state.get_current_state()
        block = args.get("block") or str(state.get("current_block") or state.get("next_block") or "AM")
        segment = str(state.get("active_segment") or "")
        queue = queue_builder.build_queue(block=block, segment=segment)
        dialer_link = _dialer_link(block, segment, "dialer")
        hud_link = _dialer_link(block, segment, "hud")
        return {
            "state": state,
            "queue_summary": queue.get("summary", ""),
            "queue_total": queue.get("total", 0),
            "breakdown": queue.get("breakdown", {}),
            "dialer_link": dialer_link,
            "hud_link": hud_link,
        }

    if name == "get_scoreboard":
        return sprint_scoreboard(tenant_id=tenant, today=today)

    if name == "get_daily_plan":
        return build_daily_plan(today=today, tenant_id=tenant)

    if name == "get_pipeline_review":
        prospects = store.list_outbound_prospects(tenant_id=tenant)
        warm = [p for p in prospects if p.get("stage") in ("callback", "interested")]
        missing_next = [
            {
                "business_name": p.get("business_name", "Unknown"),
                "stage": p.get("stage"),
                "metro": p.get("metro", ""),
                "phone": p.get("phone", ""),
            }
            for p in warm
            if not p.get("next_action_date")
        ]
        return {
            "warm_leads_total": len(warm),
            "missing_next_step": missing_next[:15],
            "missing_next_step_count": len(missing_next),
        }

    if name == "get_digest":
        try:
            stats = store.today_call_stats(tenant_id=tenant, today=today.isoformat())
            return stats if isinstance(stats, dict) else {"stats": stats}
        except Exception:
            return {"error": "digest_unavailable"}

    if name == "get_hot_leads":
        prospects = store.list_outbound_prospects(tenant_id=tenant)
        classified = []
        for p in prospects:
            if p.get("stage") in ("interested", "callback"):
                lead_type = classify_lead_type(p)
                classified.append({
                    "business_name": p.get("business_name", "Unknown"),
                    "phone": p.get("phone", ""),
                    "metro": p.get("metro", ""),
                    "stage": p.get("stage"),
                    "lead_type": lead_type,
                    "next_action_date": p.get("next_action_date"),
                    "next_action_type": p.get("next_action_type"),
                })
        hot = [c for c in classified if c["lead_type"] == "hot"]
        warm = [c for c in classified if c["lead_type"] == "warm"]
        return {"hot_leads": hot, "warm_leads": warm}

    return {"error": f"unknown_tool: {name}"}


# ---------------------------------------------------------------------------
# LLM Question Answering
# ---------------------------------------------------------------------------

def _assistant_model() -> str:
    return os.getenv("SALES_ASSISTANT_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"


def answer_question(question: str) -> str:
    """Use LLM tool-calling to answer a natural language question about the sales sprint."""
    intent = route_intent(question)
    if intent is not None:
        return _answer_intent(intent)

    if completion is None:
        return "LLM not available (litellm not installed)."

    messages = [
        {
            "role": "system",
            "content": (
                "You are a sales assistant for an outbound calling sprint. "
                "You have access to tools that query real-time sales data. "
                "Use the tools to answer the user's question with specific numbers. "
                "Be concise, direct, and encouraging. Format for Discord (markdown). "
                "If the data shows good progress, acknowledge it briefly. "
                "If something needs attention, flag it clearly."
            ),
        },
        {"role": "user", "content": question},
    ]

    try:
        response = completion(
            model=_assistant_model(),
            messages=messages,
            tools=TOOL_DEFS,
            temperature=0,
        )
    except Exception:
        logger.exception("LLM initial call failed")
        return "Sorry, I couldn't process that question right now."

    msg = response.choices[0].message

    # If LLM wants to call tools, execute them and send results back
    if msg.tool_calls:
        messages.append(msg)
        for tool_call in msg.tool_calls:
            tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
            result = _execute_tool(tool_call.function.name, tool_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            })

        try:
            final = completion(
                model=_assistant_model(),
                messages=messages,
                temperature=0,
            )
            return str(final.choices[0].message.content)
        except Exception:
            logger.exception("LLM final call failed")
            return "I got the data but couldn't format the answer. Try again."

    return str(msg.content)


# ---------------------------------------------------------------------------
# Discord Bot (Gateway)
# ---------------------------------------------------------------------------

def _create_bot() -> Any:
    """Create the Discord bot client. Returns None if discord.py is not installed."""
    if discord is None:
        logger.warning("discord.py not installed, bot will not start")
        return None

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        logger.info("Sales Assistant bot connected as %s", client.user)

    @client.event
    async def on_message(message: Any) -> None:
        # Ignore own messages
        if message.author == client.user:
            return

        # Only respond to @mentions
        if client.user not in message.mentions:
            return

        # Strip the mention to get the question
        question = re.sub(r"<@!?\d+>\s*", "", message.content).strip()

        if not question:
            await message.reply("Ask me anything about your calling sprint! Try: *how am I tracking this week?*")
            return

        # Show typing indicator while processing
        async with message.channel.typing():
            # Run the synchronous LLM call in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            answer = await loop.run_in_executor(None, answer_question, question)

        # Truncate to Discord's 2000 char limit
        if len(answer) > 1950:
            answer = answer[:1950] + "\n..."

        await message.reply(answer)

    return client


def start_bot_background() -> None:
    """Start the Discord bot in a background thread. Called from server.py on startup."""
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        logger.info("DISCORD_BOT_TOKEN not set, Sales Assistant bot disabled")
        return

    if discord is None:
        logger.warning("discord.py not installed, Sales Assistant bot disabled")
        return

    client = _create_bot()
    if client is None:
        return

    def _run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client.start(token))
        except Exception:
            logger.exception("Discord bot crashed")
        finally:
            loop.close()

    thread = threading.Thread(target=_run, daemon=True, name="discord-bot")
    thread.start()
    logger.info("Sales Assistant Discord bot starting in background thread")
