---
name: kb-query
description: Research questions against the CallLock Research Wiki. Use when asking questions about competitors, voice AI, or sales strategies that the wiki might have answers for.
---

# /kb-query

Answer research questions by navigating the CallLock Research Wiki.

## Steps

1. **Read the index.** Start at `kb/wiki/_index.md` to see all available articles and dossier categories.

2. **Identify relevant articles.** Based on the user's question, determine which articles are likely relevant. Read their content.

3. **Read deeper if needed.** Follow `## See Also` links to find related articles. Read `kb/kb.yaml` for dossier definitions if the question spans categories.

4. **Synthesize an answer.** Combine information from the articles into a clear, source-backed answer. Include inline citations like `(see [[competitors/retell-ai]])` so the user can drill deeper.

5. **Identify gaps.** If the wiki doesn't have enough information to fully answer the question, say so explicitly: "The wiki doesn't cover X yet. To fill this gap, add a source about X to kb/raw/ and run /kb-ingest."

6. **File back (optional).** If the user says "file this" or the answer represents a novel synthesis that would be useful for future queries:
   - Write the synthesis as a new article in the most relevant dossier directory
   - Use the article format from /kb-ingest (frontmatter, See Also section)
   - Set `confidence: medium` (single synthesis, not multiple sources)
   - Update `kb/wiki/_index.md` with the new article
   - Tell the user: "Filed as wiki/{dossier}/{id}.md"

## Tips

- At small wiki sizes (<20 articles), just read all articles. No need to be selective.
- Prioritize actionable intelligence over comprehensive summaries.
- When answering, frame insights in terms of what matters for CallLock's product decisions.
- If the question is better answered by the curated `knowledge/` directory (compliance, worker specs, voice contracts), point the user there instead.
