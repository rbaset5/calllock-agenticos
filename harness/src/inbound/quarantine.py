from __future__ import annotations

import re
from html.parser import HTMLParser

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore[assignment]

from inbound.types import QuarantineResult


INJECTION_PATTERNS: list[tuple[str, str]] = [
    ("role_marker", r"\b(system|assistant|user)\s*:"),
    ("directive_override", r"ignore\s+(previous|above|all)\s+instructions"),
    ("identity_manipulation", r"act\s+as\s+(a|an|the)?\s*\w+"),
    ("identity_manipulation", r"you\s+are\s+now\s+(a|an|the)?\s*\w+"),
    ("directive_override", r"\bdo\s+not\s+follow\b"),
    ("directive_override", r"\bnew\s+instructions?\b"),
    ("directive_override", r"\boverride\b.*\b(rules?|instructions?|policy)"),
    ("directive_override", r"\bforget\b.*\b(rules?|instructions?|everything)"),
    ("code_fence_injection", r"```\s*(system|prompt|instruction)"),
]

URL_RE = re.compile(r"https?://\S+")
WHITESPACE_RE = re.compile(r"\s+")


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)


def strip_html(html: str) -> str:
    if BeautifulSoup is not None:
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    else:
        parser = _HTMLTextExtractor()
        parser.feed(html)
        parser.close()
        text = " ".join(parser.parts)
    return WHITESPACE_RE.sub(" ", text).strip()


def neutralize_links(text: str) -> str:
    return URL_RE.sub("[link removed]", text)


def detect_injection(text: str) -> list[str]:
    flags: list[str] = []
    for flag, pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE) and flag not in flags:
            flags.append(flag)
    return flags


def run_full_quarantine(html: str) -> QuarantineResult:
    sanitized_text = neutralize_links(strip_html(html))
    flags = detect_injection(sanitized_text)
    if flags:
        return QuarantineResult(
            status="blocked",
            flags=flags,
            reason=f"Matched quarantine patterns: {', '.join(flags)}",
            sanitized_text=sanitized_text,
        )
    return QuarantineResult(status="clean", flags=[], reason=None, sanitized_text=sanitized_text)
