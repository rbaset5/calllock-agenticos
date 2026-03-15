from __future__ import annotations


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        return {}, content
    _, remainder = content.split("---\n", 1)
    frontmatter_raw, body = remainder.split("\n---\n", 1)
    metadata: dict[str, str] = {}
    current_parent = ""
    for line in frontmatter_raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  ") and current_parent:
            key, value = line.strip().split(":", 1)
            metadata[f"{current_parent}.{key.strip()}"] = value.strip()
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
        current_parent = key.strip() if not value.strip() else ""
    return metadata, body
