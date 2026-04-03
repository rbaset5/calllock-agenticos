"""Shared LLM completion helper for outbound pipeline modules.

Wraps litellm completion() with standard config: model from LITELLM_MODEL env,
retry on failure, structured logging. Used by extraction.py and followup.py.
"""

from __future__ import annotations

import logging
import os
from typing import Any

try:
    from litellm import completion
except Exception:  # pragma: no cover
    completion = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def llm_completion(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Call LLM via litellm and return the response text.

    Returns dict with keys: text, status.
    Status is one of: complete, failed, unavailable.
    """
    if completion is None:
        logger.error("litellm is not installed, cannot run LLM call")
        return {"text": None, "status": "unavailable"}

    model = os.getenv("LITELLM_MODEL", "claude-sonnet-4-6")

    for attempt in range(max_retries):
        try:
            response = completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            text = response.choices[0].message.content
            if not text or not text.strip():
                logger.warning("LLM returned empty response (attempt %d/%d)", attempt + 1, max_retries)
                if attempt < max_retries - 1:
                    continue
                return {"text": None, "status": "failed"}
            return {"text": text.strip(), "status": "complete"}
        except Exception:
            logger.exception("LLM call failed (attempt %d/%d)", attempt + 1, max_retries)
            if attempt < max_retries - 1:
                continue
            return {"text": None, "status": "failed"}

    return {"text": None, "status": "failed"}
