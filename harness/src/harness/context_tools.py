"""Repo-memory tools exposed through the Hermes CEO gateway."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DECISIONS_DIR = REPO_ROOT / "decisions"
ERRORS_DIR = REPO_ROOT / "errors"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"

DOMAIN_SECTIONS = {
    "voice-pipeline": "Voice Pipeline",
    "product": "Product",
    "architecture": "Architecture",
}


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _append_to_index(index_path: Path, *, section_header: str, entry_line: str) -> None:
    content = _read_text(index_path)
    lines = content.splitlines()

    section_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == f"## {section_header}":
            section_idx = idx
            break

    if section_idx is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([f"## {section_header}", "", entry_line])
    else:
        insert_at = section_idx + 1
        for idx in range(section_idx + 1, len(lines)):
            if lines[idx].startswith("## "):
                break
            if lines[idx].strip():
                insert_at = idx + 1
            if "(none yet)" in lines[idx]:
                lines[idx] = ""
        lines.insert(insert_at, entry_line)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines).rstrip() + "\n")


def _search_index(index_path: Path, *, query: str, domain: str | None = None) -> dict[str, Any]:
    content = _read_text(index_path)
    if not content:
        return {"query": query, "domain": domain, "matches": [], "count": 0}

    query_words = [word for word in query.lower().split() if word]
    matches: list[str] = []
    in_domain = domain is None
    expected_section = DOMAIN_SECTIONS.get(domain or "", "").lower()

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            section_name = stripped.removeprefix("## ").strip().lower()
            in_domain = domain is None or section_name == expected_section
            continue
        if not in_domain or not stripped.startswith("- "):
            continue
        line_lower = stripped.lower()
        if any(word in line_lower for word in query_words):
            matches.append(stripped)

    return {"query": query, "domain": domain, "matches": matches, "count": len(matches)}


def check_decisions(*, query: str, domain: str | None = None) -> dict[str, Any]:
    return _search_index(DECISIONS_DIR / "_index.md", query=query, domain=domain)


def create_decision(
    *,
    title: str,
    domain: str,
    context: str,
    options: list[dict[str, str]],
    decision: str,
    consequences: str,
    status: str = "active",
) -> dict[str, Any]:
    if domain not in DOMAIN_SECTIONS:
        return {"error": f"Unknown domain: {domain}. Use: {sorted(DOMAIN_SECTIONS)}"}

    today = _today()
    slug = _slugify(title)
    decision_id = f"DEC-{today}-{slug}"
    filename = f"{decision_id}.md"

    domain_dir = DECISIONS_DIR / domain
    domain_dir.mkdir(parents=True, exist_ok=True)

    option_lines = "\n".join(
        f"- **{option.get('name', f'Option {idx + 1}')}:** {option.get('description', '')}"
        for idx, option in enumerate(options)
    )

    content = f"""---
id: {decision_id}
domain: {domain}
status: {status}
---

# {title}

## Context
{context}

## Options Considered
{option_lines}

## Decision
{decision}

## Consequences
{consequences}
"""

    file_path = domain_dir / filename
    file_path.write_text(content)

    summary = decision.split(".")[0].strip() if "." in decision else decision[:100].strip()
    _append_to_index(
        DECISIONS_DIR / "_index.md",
        section_header=DOMAIN_SECTIONS[domain],
        entry_line=f"- [{title}]({domain}/{filename}) — {summary}",
    )

    return {"path": str(file_path.relative_to(REPO_ROOT)), "id": decision_id, "content": content}


def check_errors(*, query: str, domain: str | None = None) -> dict[str, Any]:
    return _search_index(ERRORS_DIR / "_index.md", query=query, domain=domain)


def log_error(
    *,
    title: str,
    domain: str,
    symptoms: str,
    root_cause: str = "",
    fix: str = "",
    pattern_notes: str = "",
    status: str = "logged",
) -> dict[str, Any]:
    if domain not in DOMAIN_SECTIONS:
        return {"error": f"Unknown domain: {domain}. Use: {sorted(DOMAIN_SECTIONS)}"}

    today = _today()
    slug = _slugify(title)
    domain_dir = ERRORS_DIR / domain
    domain_dir.mkdir(parents=True, exist_ok=True)

    existing = next((path for path in domain_dir.glob("*.md") if slug in path.stem), None)
    if existing is not None:
        content = existing.read_text()
        match = re.search(r"occurrences:\s*(\d+)", content)
        current_occurrences = int(match.group(1)) if match else 1
        new_occurrences = current_occurrences + 1
        content = re.sub(r"occurrences:\s*\d+", f"occurrences: {new_occurrences}", content, count=1)
        content = content.rstrip() + f"\n\n### Occurrence {new_occurrences} ({today})\n{symptoms}\n"
        existing.write_text(content)
        should_extract_rule = new_occurrences >= 3
        return {
            "path": str(existing.relative_to(REPO_ROOT)),
            "occurrences": new_occurrences,
            "action": "bumped",
            "should_extract_rule": should_extract_rule,
            "note": (
                "Pattern recurred 3+ times; extract a durable rule into decisions/ or knowledge/."
                if should_extract_rule
                else f"Occurrence {new_occurrences} logged."
            ),
        }

    error_id = f"ERR-{today}-{slug}"
    filename = f"{error_id}.md"
    content = f"""---
id: {error_id}
domain: {domain}
occurrences: 1
status: {status}
---

# {title}

## Symptoms
{symptoms}

## Root Cause
{root_cause}

## Fix
{fix}

## Pattern Notes
{pattern_notes}
"""

    file_path = domain_dir / filename
    file_path.write_text(content)

    summary = symptoms.split(".")[0].strip() if "." in symptoms else symptoms[:100].strip()
    _append_to_index(
        ERRORS_DIR / "_index.md",
        section_header=DOMAIN_SECTIONS[domain],
        entry_line=f"- [{title}]({domain}/{filename}) — {summary}",
    )

    return {"path": str(file_path.relative_to(REPO_ROOT)), "id": error_id, "content": content}


def update_knowledge(*, path: str, content: str, append: bool = False) -> dict[str, Any]:
    target = KNOWLEDGE_DIR / path
    if not target.suffix:
        target = target.with_suffix(".md")
    target.parent.mkdir(parents=True, exist_ok=True)

    existed = target.exists()
    if append and existed:
        target.write_text(target.read_text().rstrip() + "\n\n" + content + "\n")
        action = "appended"
    else:
        target.write_text(content)
        action = "overwritten" if existed else "created"

    return {"path": str(target.relative_to(REPO_ROOT)), "action": action}


def decompose_problem(*, raw_input: str) -> dict[str, Any]:
    domain = _detect_domain(raw_input)
    prior_decisions = check_decisions(query=raw_input, domain=domain)
    prior_errors = check_errors(query=raw_input, domain=domain)

    if prior_decisions["count"] and prior_errors["count"]:
        recommendation = "Review matching decisions and errors before creating new context."
    elif prior_errors["count"]:
        recommendation = "Matching error pattern found. Consider log_error on the existing pattern."
    elif prior_decisions["count"]:
        recommendation = "Prior decision exists. Verify whether it still applies before making changes."
    else:
        recommendation = "No prior art found. Clarify the problem, then create_decision or log_error as appropriate."

    return {
        "raw_input": raw_input,
        "detected_domain": domain,
        "prior_decisions": prior_decisions["matches"],
        "prior_errors": prior_errors["matches"],
        "recommended_action": recommendation,
    }


def _detect_domain(text: str) -> str | None:
    lowered = text.lower()
    voice_keywords = ["call", "voice", "retell", "transcript", "webhook", "post-call", "agent"]
    product_keywords = ["app", "ui", "page", "render", "calllock", "contractor", "web"]
    architecture_keywords = ["deploy", "docker", "coolify", "hetzner", "supabase", "inngest", "python", "typescript"]

    scores = {
        "voice-pipeline": sum(1 for keyword in voice_keywords if keyword in lowered),
        "product": sum(1 for keyword in product_keywords if keyword in lowered),
        "architecture": sum(1 for keyword in architecture_keywords if keyword in lowered),
    }
    best_domain = max(scores, key=scores.get)
    return best_domain if scores[best_domain] > 0 else None
