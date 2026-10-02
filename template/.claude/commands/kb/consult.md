---
description: Search the knowledge base for what we already know about a subject, and report the gaps
argument-hint: [keyword or subject, e.g. "stripe proration"]
---

Consult the knowledge base about **$ARGUMENTS**. Load `project-knowledge` first.

```bash
python3 .claude/scripts/kb.py find $ARGUMENTS
```

Then, for every hit: read it, and follow its `## Related` one hop with
`python3 .claude/scripts/kb.py related "<basename>"`. The graph is there so that
one relevant note leads to the rest — use it instead of running more searches.

If `find` exits 2, nothing matches. Report that as a **gap**, not as an answer,
and say which type and scope the missing note would have.

Report:

- what the knowledge base says, in your own words, with the note basenames;
- where it contradicts the code you can see — the code wins, and the note needs
  fixing;
- what is missing, and whether the current work should fill it.

Do not summarise notes the user did not ask about. Two or three lines per note.
