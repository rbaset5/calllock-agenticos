---
name: kb-ingest
description: Process new raw sources into the CallLock Research Wiki. Use when new files are added to kb/raw/ and need to be compiled into wiki articles.
---

# /kb-ingest

Process new files in `kb/raw/` into compiled wiki articles in `kb/wiki/`.

## Steps

1. **Find unprocessed sources.** Read `kb/raw/_index.md` to see what's already been processed. Glob `kb/raw/` for all files (excluding `_index.md`). Any file in the directory but not in the index is unprocessed.

2. **Read each unprocessed source.** Read the full content of each new raw file.

3. **Determine dossier type.** Based on the content:
   - `competitors` — companies, products, or services in the voice AI / answering service space
   - `voice-ai` — technical papers, implementation patterns, API docs, benchmarks
   - `playbooks` — sales strategies, objection handling, qualification logic, GTM, market insights
   - If ambiguous, ask the user which dossier fits best.

4. **Create or update the wiki article.** For each source:
   - Derive an article ID from the title slug (e.g., `competitor-retell-ai`)
   - Check if `kb/wiki/{dossier}/{id}.md` already exists
   - If it exists, overwrite it entirely (idempotent)
   - If new, create the file with this format:

   ```markdown
   ---
   id: {id}
   title: {title}
   dossier: {dossier}
   tags: [{relevant, tags}]
   source_refs:
     - raw/{filename}
   compiled_at: {ISO 8601 timestamp}
   confidence: {high|medium|low}
   ---

   # {Title}

   {Compiled content — summarize key facts, extract actionable intelligence,
   note what matters for CallLock specifically. Use [[wiki-links]] to reference
   other articles in kb/wiki/. Write for a founder making product decisions,
   not for an academic audience.}

   ## See Also

   - [[{related articles if any exist}]]
   ```

   - `confidence`: high = multiple corroborating sources, medium = single source, low = inferred/speculative

5. **Update raw/_index.md.** Add a row for each processed file:
   ```
   | {date} | {filename} | {tags} | wiki/{dossier}/{id}.md |
   ```

6. **Update wiki/_index.md.** Replace the relevant dossier section's article list. Update the stats at the bottom (total articles, raw sources count, last ingest timestamp).

7. **Report.** Tell the user what was ingested, which dossier each source went to, and any new connections to existing articles.
