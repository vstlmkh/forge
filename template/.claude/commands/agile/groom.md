---
description: Turn a raw request into groomed epics, stories and single-scope tasks
argument-hint: [what you want built, in one or two sentences]
---

Groom this request into tracker artifacts: **$ARGUMENTS**

Delegate to the `pm` subagent. Give it the request verbatim plus any context
from this conversation it would otherwise have to rediscover.

The PM must:

1. **Consult the knowledge base first**, then read the relevant code.
   `python3 .claude/scripts/kb.py find <keyword> [...]`, then one hop along each
   hit's `## Related`. The knowledge base holds the business rules, integration
   behaviour, decisions and past incidents a ticket must not contradict;
   grooming without it re-derives a rule wrongly or re-litigates a decision.
   Where the knowledge base and the code disagree, the code wins — say so, and
   fix the note.
2. Ask the user — in their own language, in one batched set of questions — about
   anything genuinely ambiguous. It must not encode a guess as a requirement;
   unavoidable assumptions are marked `[ASSUMPTION]` in the ticket body.
3. Choose the shape: a single task, a story with one task per scope, or a new
   epic. Never create an empty container. `python3 .claude/scripts/forge.py
   scopes` is the authority on which scopes exist.
4. Allocate IDs with `python3 .claude/scripts/agile.py next-id <kind>`.
5. Write complete frontmatter per `docs/agile/SCHEMA.md` and observable
   acceptance criteria, filling `## Verification` only with commands that
   `python3 .claude/scripts/forge.py checks <scope>` lists.
6. Fill `docs:` on every task and bug with the notes it read — the reading list
   the engineer and `qa` will work from — and put their substance in
   `## Implementation notes`. Where the consult found **nothing**, say so there
   too: that gap is what the ticket will fill. A ticket that genuinely cannot
   produce durable knowledge carries `docs: []` with
   `docs_waiver: NO-DOCS (<reason>)`.
7. Run `python3 .claude/scripts/agile.py lint` and
   `python3 .claude/scripts/kb.py lint` until both are clean.
8. Commit: `chore(agile): opens <IDs>`.

Then report to the user, in a few lines: the IDs created, the shape chosen and
why, which knowledge-base notes informed them, what the knowledge base turned
out not to know, and every assumption made.
