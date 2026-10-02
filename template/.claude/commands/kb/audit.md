---
description: Audit the whole knowledge base for gaps, misfilings, stale notes and broken links
---

Audit the knowledge base. Load `project-knowledge` and use its **audit**
capability.

```bash
python3 .claude/scripts/kb.py lint
python3 .claude/scripts/kb.py index
cat docs/knowledge/INDEX.md
```

The coverage table's `_0_` cells are the backlog. Then look for what the linter
cannot see:

- **gaps** — an integration, scheduled job, domain or incident-prone area with
  no note;
- **misfilings** — a business rule buried in an `overview`, a decision recorded
  as a runbook step, a `troubleshooting` note with no real root cause;
- **staleness** — notes that disagree with the code as it is now. Spot-check the
  paths each note names; a note pointing at a file that no longer exists is the
  cheapest signal there is;
- **dead ends** — orphans, one-sided edges, `## Related` sections that are still
  `_none yet_` when the subject clearly connects to something.

**Present the plan and get sign-off before bulk changes** — an audit can touch
every file in the tree. Then execute: `git mv` for renames (fixing every inbound
`[[wikilink]]`), `kb.py new` for gaps, `status: superseded` for notes the code
has outgrown, and repair `## Related` in both directions.

Finish with both linters clean and a coverage report: what was filled, what was
refiled, and what is still a gap and why.
