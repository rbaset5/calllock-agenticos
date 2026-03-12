from __future__ import annotations

from pathlib import Path

from knowledge.frontmatter_parser import parse_frontmatter


def load_markdown(path: str | Path) -> dict[str, object]:
    target = Path(path)
    content = target.read_text()
    metadata, body = parse_frontmatter(content)
    return {"path": str(target), "metadata": metadata, "body": body}
