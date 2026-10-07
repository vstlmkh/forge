---
description: Record what a bounced gate just taught, as one imperative line
---

Load `agile-lessons`. Before filing anything, look for a rule that already says
it — confirming one beats a near-duplicate, because `confirmations` is the
ranking key and two half-confirmed rules sink each other out of the hand-off:

```bash
python3 .claude/scripts/lessons.py list --scope <scope>
python3 .claude/scripts/lessons.py confirm <LESSON-NNNN> --ticket <TICKET-ID>
```

If nothing fits:

```bash
python3 .claude/scripts/lessons.py new "<two to five words>" \
    --scope <scope|all> --roles <role,role|all> --gate <N> --ticket <TICKET-ID> \
    --rule "<one imperative line>"
```

Then fill `## Why`, `## How to apply` and `## Evidence` — `lint` rejects the
skeleton — and put the id in the ticket's `lessons:`.

The rule is the artefact. Write it as an instruction, in the imperative, naming
the action; everything that needs a paragraph goes in the body, which most
readers will never open. `## Why` names the failure it prevents: a rule whose
reason is invisible gets optimised away by the next agent, which is how the
project unlearned it the first time.

A fact about the product is **not** a lesson — that is `kb.py new`. The test is
who the rule binds: the system, or whoever works on it.
