"""Skill promotion pipeline.

Extracts a reusable procedure from a completed run and saves it
as a markdown skill file in knowledge/worker-skills/{worker_id}/.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = REPO_ROOT / "knowledge" / "worker-skills"


def promote_skill(
    *,
    candidate: dict[str, Any],
    skill_title: str,
    skill_body: str,
    promoted_by: str = "founder",
    universal: bool = True,
) -> dict[str, str]:
    """Promote a skill candidate to a saved skill file."""
    worker_id = candidate["worker_id"]
    slug = _slugify(skill_title)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    worker_dir = SKILLS_DIR / worker_id
    worker_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
id: skill-{worker_id}-{slug}
title: "{skill_title}"
graph: worker-skills
owner: {worker_id}
last_reviewed: {now}
trust_level: curated
progressive_disclosure:
  summary_tokens: 40
  full_tokens: 200
worker_id: {worker_id}
created_from_run: {candidate.get('run_id', 'unknown')}
created_at: {now}
promoted_by: {promoted_by}
tenant_context: {candidate.get('tenant_id', 'unknown')}
universal: {str(universal).lower()}
---

{skill_body}
"""

    skill_path = worker_dir / f"{slug}.md"
    skill_path.write_text(content)

    try:
        from db import repository

        repository.update_skill_candidate(
            candidate["id"],
            {
                "status": "promoted",
                "promoted_by": promoted_by,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception:
        pass

    return {
        "path": str(skill_path.relative_to(REPO_ROOT)),
        "content": content,
    }


def dismiss_skill_candidate(
    candidate_id: str,
    *,
    reason: str = "",
    dismissed_by: str = "founder",
) -> dict[str, Any]:
    """Dismiss a skill candidate."""
    from db import repository

    return repository.update_skill_candidate(
        candidate_id,
        {
            "status": "dismissed",
            "dismiss_reason": reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def list_pending_candidates(
    *,
    tenant_id: str | None = None,
    worker_id: str | None = None,
) -> list[dict[str, Any]]:
    """List pending skill candidates for review."""
    from db import repository

    return repository.list_skill_candidates(
        tenant_id=tenant_id,
        status="pending",
        worker_id=worker_id,
    )


def _slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")
