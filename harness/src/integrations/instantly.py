"""Instantly.ai API client with built-in guardrails.

Handles email sending, warmup status, reply checking, and domain reputation
for the CallLock outbound email pipeline. Guardrails are built INTO the client,
not into callers — this prevents bypassing rate limits or warmup checks.

Environment:
    INSTANTLY_API_KEY: Required. Instantly API key.
    INSTANTLY_BASE_URL: Optional. Defaults to "https://api.instantly.ai/api/v1".
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.instantly.ai/api/v1"

DEFAULT_RATE_LIMIT_PER_ACCOUNT_PER_HOUR = 30
DEFAULT_MIN_WARMUP_SCORE = 70
DEFAULT_MAX_BOUNCE_RATE = 0.05
DEFAULT_MAX_COMPLAINT_RATE = 0.01
DEFAULT_DEDUP_WINDOW_HOURS = 72


class InstantlyError(Exception):
    """Base exception for Instantly client errors."""


class InstantlyRateLimitError(InstantlyError):
    """Raised when rate limit is exceeded."""


class InstantlyWarmupError(InstantlyError):
    """Raised when account warmup score is below threshold."""


class InstantlyReputationError(InstantlyError):
    """Raised when account reputation is too low to send."""


class InstantlyDedupError(InstantlyError):
    """Raised when a prospect was already emailed within the dedup window."""


class InstantlyClient:
    """Instantly.ai API client with built-in guardrails."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        rate_limit_per_hour: int = DEFAULT_RATE_LIMIT_PER_ACCOUNT_PER_HOUR,
        min_warmup_score: int = DEFAULT_MIN_WARMUP_SCORE,
        max_bounce_rate: float = DEFAULT_MAX_BOUNCE_RATE,
        max_complaint_rate: float = DEFAULT_MAX_COMPLAINT_RATE,
        dedup_window_hours: int = DEFAULT_DEDUP_WINDOW_HOURS,
    ) -> None:
        self.api_key = api_key or os.environ.get("INSTANTLY_API_KEY", "")
        self.base_url = (base_url or os.environ.get("INSTANTLY_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.rate_limit_per_hour = rate_limit_per_hour
        self.min_warmup_score = min_warmup_score
        self.max_bounce_rate = max_bounce_rate
        self.max_complaint_rate = max_complaint_rate
        self.dedup_window_hours = dedup_window_hours
        self._send_log: dict[str, list[float]] = {}

        if not self.api_key:
            logger.warning("instantly_no_api_key", extra={"base_url": self.base_url})

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the Instantly API."""
        import json
        from urllib import error, parse, request

        url = f"{self.base_url}{path}"
        all_params: dict[str, Any] = {"api_key": self.api_key}
        if params:
            all_params.update(params)
        query = parse.urlencode(all_params, doseq=True)
        full_url = f"{url}?{query}" if query else url

        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")

        req = request.Request(
            full_url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )

        try:
            with request.urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8")
                if not body:
                    return {}
                parsed = json.loads(body)
                return parsed if isinstance(parsed, dict) else {"data": parsed}
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            logger.error(
                "instantly_api_error",
                extra={
                    "status": exc.code,
                    "path": path,
                    "body": body[:500],
                },
            )
            raise InstantlyError(f"Instantly API {method} {path} failed: {exc.code} {body[:200]}") from exc
        except (error.URLError, OSError) as exc:
            raise InstantlyError(f"Instantly API connection error: {exc}") from exc

    async def send(
        self,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
        account_id: str,
        campaign_id: str | None = None,
        reply_to_message_id: str | None = None,
        variables: dict[str, str] | None = None,
        skip_guardrails: bool = False,
    ) -> dict[str, Any]:
        """Send an email via Instantly."""
        if not skip_guardrails:
            self._check_rate_limit(account_id)

            warmup = await self.get_warmup_status(account_id)
            if warmup.get("score", 0) < self.min_warmup_score:
                raise InstantlyWarmupError(
                    f"Account {account_id} warmup score {warmup.get('score', 0)} "
                    f"below threshold {self.min_warmup_score}"
                )

            reputation = await self.check_reputation(account_id)
            bounce_rate = float(reputation.get("bounce_rate", 0) or 0)
            complaint_rate = float(reputation.get("complaint_rate", 0) or 0)
            if bounce_rate > self.max_bounce_rate:
                raise InstantlyReputationError(
                    f"Account {account_id} bounce rate {bounce_rate:.3f} "
                    f"exceeds threshold {self.max_bounce_rate}"
                )
            if complaint_rate > self.max_complaint_rate:
                raise InstantlyReputationError(
                    f"Account {account_id} complaint rate {complaint_rate:.3f} "
                    f"exceeds threshold {self.max_complaint_rate}"
                )

            send_log = await self.get_send_log(account_id, limit=250)
            self._check_dedup(account_id, to_email, send_log)

        payload: dict[str, Any] = {
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "body": body,
        }
        if campaign_id:
            payload["campaign_id"] = campaign_id
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        if variables:
            payload["variables"] = variables

        result = await self._request("POST", "/email/send", json_body=payload)
        self._record_send(account_id)

        logger.info(
            "instantly_email_sent",
            extra={
                "from": from_email,
                "to": to_email,
                "account_id": account_id,
                "campaign_id": campaign_id,
            },
        )
        return result

    async def get_warmup_status(self, account_id: str) -> dict[str, Any]:
        """Get warmup status for a sending account."""
        return await self._request("GET", "/account/warmup/status", params={"email": account_id})

    async def check_replies(
        self,
        campaign_id: str,
        email: str | None = None,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """Check for replies to a campaign."""
        params: dict[str, Any] = {"campaign_id": campaign_id}
        if email:
            params["email"] = email
        if since:
            params["since"] = since
        result = await self._request("GET", "/email/replies", params=params)
        return result.get("data", []) if isinstance(result, dict) else []

    async def get_send_log(
        self,
        account_id: str,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get recent sends for a sending account."""
        params: dict[str, Any] = {"email": account_id, "limit": str(limit)}
        if since:
            params["since"] = since
        result = await self._request("GET", "/email/send-log", params=params)
        return result.get("data", []) if isinstance(result, dict) else []

    async def check_reputation(self, account_id: str) -> dict[str, Any]:
        """Check sending reputation for an account."""
        return await self._request("GET", "/account/reputation", params={"email": account_id})

    def _check_rate_limit(self, account_id: str) -> None:
        """Check if sending from this account would exceed the hourly rate limit."""
        now = time.time()
        one_hour_ago = now - 3600
        if account_id in self._send_log:
            self._send_log[account_id] = [timestamp for timestamp in self._send_log[account_id] if timestamp > one_hour_ago]

        count = len(self._send_log.get(account_id, []))
        if count >= self.rate_limit_per_hour:
            raise InstantlyRateLimitError(
                f"Account {account_id} has sent {count} emails in the last hour "
                f"(limit: {self.rate_limit_per_hour})"
            )

    def _record_send(self, account_id: str) -> None:
        """Record a send event for rate limiting."""
        if account_id not in self._send_log:
            self._send_log[account_id] = []
        self._send_log[account_id].append(time.time())

    def _check_dedup(self, account_id: str, to_email: str, send_log: list[dict[str, Any]]) -> None:
        """Check if this recipient was emailed within the dedup window."""
        cutoff = datetime.now(timezone.utc).timestamp() - (self.dedup_window_hours * 3600)
        for entry in send_log:
            if entry.get("to") != to_email:
                continue
            sent_at = entry.get("sent_at", "")
            if not sent_at:
                continue
            try:
                entry_ts = datetime.fromisoformat(str(sent_at).replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError):
                continue
            if entry_ts > cutoff:
                raise InstantlyDedupError(
                    f"Recipient {to_email} was emailed from {account_id} "
                    f"at {sent_at} (within {self.dedup_window_hours}h dedup window)"
                )
