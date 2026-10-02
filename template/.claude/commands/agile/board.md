---
description: Regenerate the board, run both validators and report any drift
---

Show the current state of the tracker.

```bash
python3 .claude/scripts/agile.py index
python3 .claude/scripts/agile.py lint
python3 .claude/scripts/kb.py index
python3 .claude/scripts/kb.py lint
```

Then read `docs/agile/INDEX.md` and report:

- what is in flight, with who holds it and how long ago it was claimed;
- what is ready, in priority order;
- what is blocked and on what;
- any untriaged bugs;
- every `lint` issue from either validator, verbatim, with what it would take to
  fix;
- the knowledge base in one line: how many notes, and which coverage cells in
  `docs/knowledge/INDEX.md` are still `_0_` for the areas currently in flight. A
  ticket in flight whose subject has no note is a gap about to be discovered the
  expensive way;
- any story or epic whose children are all `done` and which is a candidate for
  rolling up.

If `lint` exits 2, that is the headline — lead with it. Do not fix the issues
unless the user asks; report them and say which agent owns each fix.

Keep it short. The user can open the board; what they want from you is the
judgement, not the table.
