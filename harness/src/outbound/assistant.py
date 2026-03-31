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
import threading
import time
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
from .daily_plan import build_daily_plan
from .lifecycle import classify_lead_type
from .scoreboard import sprint_scoreboard

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM Tool Definitions
# ---------------------------------------------------------------------------

TOOL_DEFS = [
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

def _execute_tool(name: str) -> dict[str, Any]:
    """Execute a tool call and return the result."""
    today = date.today()
    tenant = OUTBOUND_TENANT_ID

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
    return os.getenv("SALES_ASSISTANT_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"


def answer_question(question: str) -> str:
    """Use LLM tool-calling to answer a natural language question about the sales sprint."""
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
            result = _execute_tool(tool_call.function.name)
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
        import re
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
        _run_bot_forever(client, token)

    thread = threading.Thread(target=_run, daemon=True, name="discord-bot")
    thread.start()
    logger.info("Sales Assistant Discord bot starting in background thread")


def _run_bot_forever(
    client: Any,
    token: str,
    *,
    sleep_fn: Any = time.sleep,
    max_attempts: int | None = None,
) -> bool:
    """Keep retrying Discord connection attempts for the life of the process."""
    attempt = 0
    delay = 1.0

    while max_attempts is None or attempt < max_attempts:
        attempt += 1
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client.start(token))
            return True
        except Exception:
            logger.exception("Discord bot crashed")
        finally:
            try:
                loop.close()
            except Exception:
                logger.exception("Failed to close Discord bot loop")

        if max_attempts is not None and attempt >= max_attempts:
            break

        sleep_fn(delay)
        delay = min(delay * 2, 30.0)

    return False
