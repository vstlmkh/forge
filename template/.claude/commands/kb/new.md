---
description: File a knowledge-base note for something a task revealed, correctly typed and cross-linked
argument-hint: [what was learned, optionally with a TICKET-ID]
---

File what was learned: **$ARGUMENTS**. Load `project-knowledge` first.

1. **Decompose.** List the discrete findings. One task usually yields more than
   one — a rule, an integration quirk, a fix. Do not merge them.
2. **Check for a near-duplicate** with `kb.py find` before creating anything.
   Updating an existing note beats a second note on the same subject.
3. **Classify** each finding by type. `overview` is not the default — see the
   table in `docs/knowledge/README.md`, and `kb.py types` for the sections each
   type requires.
4. Create each note through the script, never by hand:

```bash
python3 .claude/scripts/kb.py new <type> <scope> "<description>" \
  --ticket <TICKET-ID> --title "The finding as a sentence"
```

5. Fill every section. A leftover italic hint counts as empty and `lint` says so.
6. **Cross-link both ways** — your `## Related` and theirs, each line carrying
   the reason for the edge.
7. If a ticket is involved, list the note in its `docs:`.

```bash
python3 .claude/scripts/kb.py lint
python3 .claude/scripts/kb.py index
```

Report the paths created and the edges added, in a line each.
