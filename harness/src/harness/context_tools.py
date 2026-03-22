"""Agent context system tools.

Tools for the decomposition loop: capture decisions, log errors,
check prior art, and update knowledge. Designed to be exposed as
MCP tools alongside ceo_tools to the Hermes gateway.

File operations follow the same pattern as skill_promotion.py:
write markdown to repo, update index, return path + content.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DECISIONS_DIR = REPO_ROOT / "decisions"
ERRORS_DIR = REPO_ROOT / "errors"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_index(index_path: Path) -> str:
    if index_path.exists():
        return index_path.read_text()
    return ""


def _append_to_index(
    index_path: Path,
    *,
    section_header: str,
    entry_line: str,
) -> None:
    """Append an entry under a section in an _index.md file.

    If the section exists, append after the last non-blank line in it.
    If not, append the section + entry at the end.
    """
    content = _read_index(index_path)
    lines = content.splitlines()

    section_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f"## {section_header}"):
            section_idx = i
            break

    if section_idx is not None:
        # Find the last content line in this section (before next ## or EOF)
        insert_at = section_idx + 1
        for j in range(section_idx + 1, len(lines)):
            if lines[j].strip().startswith("## "):
                break
            if lines[j].strip():
                insert_at = j + 1

        # Replace "(none yet)" if present
        for j in range(section_idx + 1, min(insert_at + 1, len(lines))):
            if "(none yet)" in lines[j]:
                lines[j] = ""
                break

        lines.insert(insert_at, entry_line)
    else:
        lines.append("")
        lines.append(f"## {section_header}")
        lines.append("")
        lines.append(entry_line)

    index_path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Decision tools
# ---------------------------------------------------------------------------

DOMAIN_SECTIONS = {
    "voice-pipeline": "Voice Pipeline",
    "product": "Product",
    "architecture": "Architecture",
}


def check_decisions(
    *,
    query: str,
    domain: str | None = None,
) -> dict[str, Any]:
    """Search decisions/_index.md for prior decisions matching a query.

    Returns matching lines from the index so the agent can decide
    whether a new decision is needed or an existing one applies.
    """
    index_content = _read_index(DECISIONS_DIR / "_index.md")
    if not index_content:
        return {"matches": [], "note": "No decisions index found"}

    query_lower = query.lower()
    query_words = query_lower.split()
    matches = []

    in_domain = domain is None
    for line in index_content.splitlines():
        if line.strip().startswith("## "):
            section_name = line.strip().lstrip("# ").strip()
            if domain:
                in_domain = section_name.lower() == DOMAIN_SECTIONS.get(domain, "").lower()
            continue

        if not in_domain:
            continue

        line_lower = line.lower()
        if any(word in line_lower for word in query_words) and line.strip().startswith("- "):
            matches.append(line.strip())

    return {
        "query": query,
        "domain": domain,
        "matches": matches,
        "count": len(matches),
    }


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
    """Write a new decision record to decisions/{domain}/.

    Also updates decisions/_index.md with a one-line entry.
    Returns the path and content of the created file.
    """
    if domain not in DOMAIN_SECTIONS:
        return {"error": f"Unknown domain: {domain}. Use: {list(DOMAIN_SECTIONS.keys())}"}

    today = _today()
    slug = _slugify(title)
    dec_id = f"DEC-{today}-{slug}"
    filename = f"{dec_id}.md"

    domain_dir = DECISIONS_DIR / domain
    domain_dir.mkdir(parents=True, exist_ok=True)

    # Format options
    options_text = "\n".join(
        f"- **{opt.get('name', f'Option {i+1}')}:** {opt.get('description', '')}"
        for i, opt in enumerate(options)
    )

    content = f"""---
id: {dec_id}
domain: {domain}
status: {status}
---

# {title}

## Context
{context}

## Options Considered
{options_text}

## Decision
{decision}

## Consequences
{consequences}
"""

    file_path = domain_dir / filename
    file_path.write_text(content)

    # Update index
    summary = decision.split(".")[0].strip() if "." in decision else decision[:80]
    entry = f"- [{title}]({domain}/{filename}) — {summary}"
    _append_to_index(
        DECISIONS_DIR / "_index.md",
        section_header=DOMAIN_SECTIONS[domain],
        entry_line=entry,
    )

    return {
        "path": str(file_path.relative_to(REPO_ROOT)),
        "id": dec_id,
        "content": content,
    }


# ---------------------------------------------------------------------------
# Error tools
# ---------------------------------------------------------------------------

def check_errors(
    *,
    query: str,
    domain: str | None = None,
) -> dict[str, Any]:
    """Search errors/_index.md for known error patterns matching a query."""
    index_content = _read_index(ERRORS_DIR / "_index.md")
    if not index_content:
        return {"matches": [], "note": "No errors index found"}

    query_lower = query.lower()
    query_words = query_lower.split()
    matches = []

    in_domain = domain is None
    for line in index_content.splitlines():
        if line.strip().startswith("## "):
            section_name = line.strip().lstrip("# ").strip()
            if domain:
                in_domain = section_name.lower() == DOMAIN_SECTIONS.get(domain, "").lower()
            continue

        if not in_domain:
            continue

        line_lower = line.lower()
        if any(word in line_lower for word in query_words) and line.strip().startswith("- "):
            matches.append(line.strip())

    return {
        "query": query,
        "domain": domain,
        "matches": matches,
        "count": len(matches),
    }


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
    """Create or update an error pattern in errors/{domain}/.

    If an error with a similar slug already exists, bumps occurrences.
    Otherwise creates a new error file.
    Also updates errors/_index.md.
    """
    if domain not in DOMAIN_SECTIONS:
        return {"error": f"Unknown domain: {domain}. Use: {list(DOMAIN_SECTIONS.keys())}"}

    today = _today()
    slug = _slugify(title)
    domain_dir = ERRORS_DIR / domain
    domain_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing error with same slug
    existing = None
    for f in domain_dir.iterdir():
        if slug in f.name and f.suffix == ".md":
            existing = f
            break

    if existing:
        # Bump occurrences
        content = existing.read_text()
        occ_match = re.search(r"occurrences:\s*(\d+)", content)
        current_occ = int(occ_match.group(1)) if occ_match else 1
        new_occ = current_occ + 1

        content = re.sub(
            r"occurrences:\s*\d+",
            f"occurrences: {new_occ}",
            content,
        )

        # Append new occurrence date to symptoms
        content = content.rstrip() + f"\n\n### Occurrence {new_occ} ({today})\n{symptoms}\n"
        existing.write_text(content)

        should_extract = new_occ >= 3
        return {
            "path": str(existing.relative_to(REPO_ROOT)),
            "occurrences": new_occ,
            "action": "bumped",
            "should_extract_rule": should_extract,
            "note": "Pattern recurred 3+ times — extract rule into decisions/ or knowledge/"
            if should_extract
            else f"Occurrence {new_occ} logged",
        }

    # New error
    err_id = f"ERR-{today}-{slug}"
    filename = f"{err_id}.md"

    content = f"""---
id: {err_id}
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

    # Update index
    summary = symptoms.split(".")[0].strip() if "." in symptoms else symptoms[:80]
    entry = f"- [{title}]({domain}/{filename}) — {summary}"
    _append_to_index(
        ERRORS_DIR / "_index.md",
        section_header=DOMAIN_SECTIONS[domain],
        entry_line=entry,
    )

    return {
        "path": str(file_path.relative_to(REPO_ROOT)),
        "id": err_id,
        "content": content,
    }


# ---------------------------------------------------------------------------
# Knowledge tools
# ---------------------------------------------------------------------------

def update_knowledge(
    *,
    path: str,
    content: str,
    append: bool = False,
) -> dict[str, Any]:
    """Write or append to a knowledge file.

    Path is relative to knowledge/ (e.g., 'company/mission.md').
    If append=True, adds content to the end of the existing file.
    If append=False, overwrites (use with caution).
    """
    target = KNOWLEDGE_DIR / path
    if not target.suffix:
        target = target.with_suffix(".md")

    target.parent.mkdir(parents=True, exist_ok=True)

    if append and target.exists():
        existing = target.read_text()
        target.write_text(existing.rstrip() + "\n\n" + content + "\n")
        action = "appended"
    else:
        target.write_text(content)
        action = "created" if not target.exists() else "overwritten"

    return {
        "path": str(target.relative_to(REPO_ROOT)),
        "action": action,
    }


# ---------------------------------------------------------------------------
# Decomposition orchestrator
# ---------------------------------------------------------------------------

def decompose_problem(
    *,
    raw_input: str,
) -> dict[str, Any]:
    """Analyze raw problem input and route to the right context tool.

    This is a helper that returns a decomposition plan — the agent
    should then execute the recommended actions using the other tools.

    Returns a structured analysis with:
    - clarified_problem: restated problem
    - domain: which domain this falls under
    - prior_decisions: matching decisions from index
    - prior_errors: matching errors from index
    - recommended_action: what to do next
    """
    # Simple keyword-based domain detection
    domain = _detect_domain(raw_input)

    # Check for prior art
    prior_decisions = check_decisions(query=raw_input, domain=domain)
    prior_errors = check_errors(query=raw_input, domain=domain)

    has_prior_decisions = prior_decisions["count"] > 0
    has_prior_errors = prior_errors["count"] > 0

    if has_prior_errors and has_prior_decisions:
        action = "Review prior errors and decisions before proceeding. May need to update existing records."
    elif has_prior_errors:
        action = "Matching error pattern found. Bump occurrences or update status."
    elif has_prior_decisions:
        action = "Prior decision exists. Check if it still applies or needs superseding."
    else:
        action = "No prior art found. Clarify the problem, then create_decision or log_error as appropriate."

    return {
        "raw_input": raw_input,
        "detected_domain": domain,
        "prior_decisions": prior_decisions["matches"],
        "prior_errors": prior_errors["matches"],
        "recommended_action": action,
    }


def _detect_domain(text: str) -> str | None:
    text_lower = text.lower()
    voice_keywords = ["call", "voice", "retell", "extraction", "transcript", "webhook", "post-call", "agent"]
    product_keywords = ["app", "web", "calllock", "contractor", "display", "ui", "page"]
    arch_keywords = ["deploy", "supabase", "coolify", "hetzner", "docker", "inngest", "python", "typescript"]

    voice_score = sum(1 for w in voice_keywords if w in text_lower)
    product_score = sum(1 for w in product_keywords if w in text_lower)
    arch_score = sum(1 for w in arch_keywords if w in text_lower)

    scores = {"voice-pipeline": voice_score, "product": product_score, "architecture": arch_score}
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best if scores[best] > 0 else None
