"""FastAPI router for Retell call-ended webhook (post-call pipeline)."""

from __future__ import annotations

from fastapi import APIRouter

post_call_router = APIRouter(tags=["voice-post-call"])

__all__ = ["post_call_router"]
