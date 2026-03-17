"""FastAPI router for booking management REST API (CallLock App-facing)."""

from __future__ import annotations

from fastapi import APIRouter

booking_router = APIRouter(tags=["voice-bookings"])

__all__ = ["booking_router"]
