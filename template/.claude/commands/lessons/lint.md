---
description: Validate the lessons layer and the tracker's links into it, and regenerate the index
---

```bash
python3 .claude/scripts/lessons.py lint
python3 .claude/scripts/lessons.py index
python3 .claude/scripts/agile.py lint
```

Exit 2 means a rule drifted: a skeleton body, a rule that no longer fits on a
line, a duplicate, a ticket citing a lesson that does not resolve, or a rule
nobody has confirmed inside `policy.lesson_stale_days`.

Report each issue with the fix you propose. Do not resolve a `WARN` that is a
judgement — whether two rules are the same rule, and whether a stale one should
be confirmed or retired, is what `/lessons:retro` exists to decide with a human
in the loop. Deleting the rule is never the fix: tickets cite the id.

`docs/lessons/INDEX.md` is generated; never edit it by hand.
