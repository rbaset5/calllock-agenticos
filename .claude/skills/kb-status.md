---
name: kb-status
description: Display CallLock Research Wiki statistics. Use to check the health and size of the knowledge base.
---

# /kb-status

Display statistics about the CallLock Research Wiki.

## Steps

1. **Count articles.** Glob `kb/wiki/**/*.md` (excluding `_index.md` files) and count per dossier:
   - `kb/wiki/competitors/*.md`
   - `kb/wiki/voice-ai/*.md`
   - `kb/wiki/playbooks/*.md`

2. **Count raw sources.** Glob `kb/raw/*` (excluding `_index.md`) for total raw file count.

3. **Find unprocessed sources.** Read `kb/raw/_index.md` and compare against the raw file list. Any file not in the index is unprocessed.

4. **Read checkpoint.** Read `kb/kb.yaml` for the `checkpoint_date` field.

5. **Output a summary:**

   ```
   CallLock Research Wiki
   ══════════════════════
   Competitors:  {n} articles
   Voice AI:     {n} articles
   Playbooks:    {n} articles
   ──────────────────────
   Total:        {n} articles
   Raw sources:  {n} ({m} unprocessed)
   Last ingest:  {date or "never"}

   Checkpoint:   {date} — {n}/3 decisions influenced
   ```

6. **If checkpoint date has passed** (after April 19, 2026), remind the user: "Checkpoint passed. Has this KB influenced 3+ concrete product decisions? If not, reassess whether it's worth maintaining."
