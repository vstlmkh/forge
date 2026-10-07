---
description: Review what the project has learned — merge duplicates, retire what no longer bites, and keep the hand-off inside its budget
---

A retrospective over the lessons layer. Load `agile-lessons` first.

```bash
python3 .claude/scripts/lessons.py audit
python3 .claude/scripts/lessons.py lint
```

`audit` prints the decision queue and no verdicts, because every verdict here is
a judgement. Work through it:

- **Past the budget.** A scope with more active rules than
  `policy.lesson_budget` is handing out some and hiding the rest. Those are not
  surplus rules — they are rules the ranking decided are worth less than the
  ones above them. Either they earn a confirmation, or they merge into a rule
  that already carries one, or they retire. Leaving them is choosing to have
  them silently ignored.
- **Duplicates.** Two rules saying the same thing split the evidence between
  them and sink both out of the hand-off. `supersede` the weaker one — never
  delete it; tickets cite the id.
- **Stale.** A rule nobody has confirmed in `policy.lesson_stale_days` is
  charging every agent context on every turn for a failure that may no longer
  happen. Ask what changed: if a check moved into CI, the rule has been replaced
  by a machine and should retire, with that reason in `## Evidence`.
- **Never confirmed.** One bounce is an incident; the rule it produced may have
  been a guess about a pattern. Look for a second occurrence in the tickets
  closed since. If there is none and the rule is old, it is a candidate for
  retirement, and saying so is more honest than letting it rot inside the
  budget.
- **Wrongly scoped.** A rule filed under one scope that has been confirmed by
  tickets in another belongs in `all`. A rule in `all` that only ever bites one
  scope is costing every other agent a line for nothing.

**Present the proposed changes and get sign-off before applying them.** This
command rewrites what every agent reads at the start of every gate; a bad merge
here is a rule that silently stops being enforced.

Then apply, one call per decision:

```bash
python3 .claude/scripts/lessons.py confirm   <LESSON-NNNN> --ticket <TICKET-ID>
python3 .claude/scripts/lessons.py retire    <LESSON-NNNN> --reason "<what changed>"
python3 .claude/scripts/lessons.py supersede <LESSON-NNNN> --by <LESSON-NNNN>
python3 .claude/scripts/lessons.py index
```

Finish with `lessons.py lint` clean and a short report: what each scope now
hands out, what was retired and why, and which scopes are still over budget.
