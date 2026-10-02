---
description: Validate the knowledge base and the tracker's links into it, and regenerate the index
---

```bash
python3 .claude/scripts/kb.py lint
python3 .claude/scripts/kb.py index
python3 .claude/scripts/agile.py lint
```

Exit 2 from either linter means the knowledge base or the tracker is
inconsistent. Report each issue with the fix you propose; do not fix anything
that needs a judgement call — a `WARN` about an orphan or a one-sided edge is a
question about the graph, and answering it by deleting the link is not a fix.

`docs/knowledge/INDEX.md` is generated; never edit it by hand.
