from __future__ import annotations

from inbound.quarantine import detect_injection


def scan_draft(draft_text: str) -> tuple[str, list[str]]:
    flags = detect_injection(draft_text)
    if flags:
        return ("blocked", flags)
    return ("passed", [])
