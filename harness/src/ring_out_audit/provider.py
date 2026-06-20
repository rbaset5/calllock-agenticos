from __future__ import annotations

import os
from typing import Any, Protocol


CALL_TIMEOUT_SECONDS = 20


class RingOutProvider(Protocol):
    def place_call(self, attempt: dict[str, Any]) -> dict[str, Any]:
        ...


class FakeRingOutProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def place_call(self, attempt: dict[str, Any]) -> dict[str, Any]:
        call_sid = f"CA_fake_{attempt['attempt_id']}"
        call = {
            "call_sid": call_sid,
            "provider_status": "queued",
            "attempt_id": attempt["attempt_id"],
            "prospect_id": attempt["prospect_id"],
            "to": attempt["phone"],
        }
        self.calls.append(call)
        return call


class TwilioRingOutProvider:
    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        from_number: str,
        status_callback_url: str,
        answer_url: str,
        twilio_client: Any | None = None,
    ) -> None:
        self.from_number = from_number
        self.status_callback_url = status_callback_url
        self.answer_url = answer_url
        if twilio_client is not None:
            self.client = twilio_client
        else:
            from twilio.rest import Client as TwilioClient

            self.client = TwilioClient(account_sid, auth_token)

    @classmethod
    def from_env(cls) -> "TwilioRingOutProvider":
        required = {
            "TWILIO_ACCOUNT_SID": os.getenv("TWILIO_ACCOUNT_SID"),
            "TWILIO_AUTH_TOKEN": os.getenv("TWILIO_AUTH_TOKEN"),
            "RING_OUT_TWILIO_FROM_NUMBER": os.getenv("RING_OUT_TWILIO_FROM_NUMBER"),
            "RING_OUT_STATUS_CALLBACK_URL": os.getenv("RING_OUT_STATUS_CALLBACK_URL"),
            "RING_OUT_ANSWER_URL": os.getenv("RING_OUT_ANSWER_URL"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Missing ring-out Twilio env vars: {', '.join(missing)}")
        return cls(
            account_sid=required["TWILIO_ACCOUNT_SID"] or "",
            auth_token=required["TWILIO_AUTH_TOKEN"] or "",
            from_number=required["RING_OUT_TWILIO_FROM_NUMBER"] or "",
            status_callback_url=required["RING_OUT_STATUS_CALLBACK_URL"] or "",
            answer_url=required["RING_OUT_ANSWER_URL"] or "",
        )

    def place_call(self, attempt: dict[str, Any]) -> dict[str, Any]:
        call = self.client.calls.create(
            to=attempt["phone"],
            from_=self.from_number,
            url=self.answer_url,
            method="POST",
            status_callback=self.status_callback_url,
            status_callback_method="POST",
            status_callback_event=["completed"],
            machine_detection="Enable",
            timeout=CALL_TIMEOUT_SECONDS,
        )
        return {
            "call_sid": call.sid,
            "provider_status": getattr(call, "status", "queued"),
            "attempt_id": attempt["attempt_id"],
            "prospect_id": attempt["prospect_id"],
            "to": attempt["phone"],
        }


def provider_from_env() -> RingOutProvider:
    provider_name = os.getenv("RING_OUT_PROVIDER", "fake").strip().lower()
    if provider_name == "fake":
        return FakeRingOutProvider()
    if provider_name == "twilio":
        return TwilioRingOutProvider.from_env()
    raise RuntimeError(f"Unsupported RING_OUT_PROVIDER: {provider_name}")
