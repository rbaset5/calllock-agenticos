from __future__ import annotations

import re
from pathlib import Path


WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def find_links(content: str) -> list[str]:
    return WIKI_LINK_RE.findall(content)


def resolve_link(knowledge_root: str | Path, link: str) -> Path:
    return Path(knowledge_root) / f"{link}.md"
