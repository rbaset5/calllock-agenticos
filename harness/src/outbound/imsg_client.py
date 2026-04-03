"""Thin wrapper around the imsg CLI for iMessage send and watch.

imsg (steipete/imsg) uses AppleScript to send via Messages.app.
Requires macOS with Messages signed in, Full Disk Access, and
Automation permissions for the terminal process.

Send: subprocess with retry (max 2 attempts, 5s delay).
Watch: persistent subprocess with line-buffered JSON stdout.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from typing import Any, Callable

import re


def mask_phone(phone: str | None) -> str:
    """Mask phone number for safe logging — show only last 4 digits."""
    if not phone:
        return "unknown"
    cleaned = re.sub(r"\D", "", phone)
    if len(cleaned) < 4:
        return "****"
    return f"***-***-{cleaned[-4:]}"

logger = logging.getLogger(__name__)

IMSG_BINARY = "imsg"
SEND_TIMEOUT_S = 30
RETRY_DELAY_S = 5
MAX_SEND_ATTEMPTS = 2


def _imsg_available() -> bool:
    return shutil.which(IMSG_BINARY) is not None


def send_imessage(phone: str, text: str) -> dict[str, Any]:
    """Send an iMessage via imsg CLI. Returns {"success": bool, "error": str|None}.

    Retries once on failure with a 5s delay between attempts.
    """
    if not _imsg_available():
        logger.error("imsg_client.binary_missing", extra={"phone": mask_phone(phone)})
        return {"success": False, "error": "imsg binary not found in PATH"}

    for attempt in range(MAX_SEND_ATTEMPTS):
        try:
            result = subprocess.run(
                [IMSG_BINARY, "send", "--to", phone, "--text", text],
                capture_output=True,
                text=True,
                timeout=SEND_TIMEOUT_S,
            )
            if result.returncode == 0:
                logger.info(
                    "imsg_client.sent",
                    extra={"phone": mask_phone(phone), "attempt": attempt + 1},
                )
                return {"success": True, "error": None}

            error_msg = result.stderr.strip() or f"exit code {result.returncode}"
            logger.warning(
                "imsg_client.send_failed",
                extra={
                    "phone": mask_phone(phone),
                    "attempt": attempt + 1,
                    "error": error_msg,
                },
            )
            if attempt < MAX_SEND_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_S)
                continue
            return {"success": False, "error": error_msg}

        except subprocess.TimeoutExpired:
            logger.warning(
                "imsg_client.timeout",
                extra={"phone": mask_phone(phone), "attempt": attempt + 1},
            )
            if attempt < MAX_SEND_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_S)
                continue
            return {"success": False, "error": f"imsg send timed out after {SEND_TIMEOUT_S}s"}

        except Exception as exc:
            logger.exception(
                "imsg_client.unexpected_error",
                extra={"phone": mask_phone(phone), "attempt": attempt + 1},
            )
            if attempt < MAX_SEND_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_S)
                continue
            return {"success": False, "error": str(exc)}

    return {"success": False, "error": "all attempts exhausted"}


def watch_replies(callback: Callable[[dict[str, Any]], None]) -> None:
    """Start persistent watch for inbound iMessages.

    Calls callback(msg_dict) for each incoming message.
    Runs until the imsg process exits or is killed.
    Uses line-buffered stdout to minimize reply detection latency.

    Expected imsg watch JSON fields: direction, sender, text, timestamp, chat_id.
    """
    if not _imsg_available():
        logger.error("imsg_client.watch_binary_missing")
        return

    logger.info("imsg_client.watch_started")
    proc = subprocess.Popen(
        [IMSG_BINARY, "watch", "--json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("imsg_client.watch_malformed_json", extra={"line": line[:200]})
                continue

            if msg.get("direction") == "incoming":
                try:
                    callback(msg)
                except Exception:
                    logger.exception("imsg_client.watch_callback_error")
    except Exception:
        logger.exception("imsg_client.watch_stream_error")
    finally:
        proc.terminate()
        logger.info("imsg_client.watch_stopped")


def health_check() -> dict[str, Any]:
    """Check if imsg CLI is available and callable."""
    if not _imsg_available():
        return {"healthy": False, "error": "imsg binary not found in PATH"}

    try:
        result = subprocess.run(
            [IMSG_BINARY, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return {"healthy": True, "version": result.stdout.strip()}
        return {"healthy": False, "error": f"imsg --version failed: {result.stderr.strip()}"}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}
