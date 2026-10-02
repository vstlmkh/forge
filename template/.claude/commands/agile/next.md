---
description: Pick the next ticket to work on, honouring priority, dependencies and the one-per-working-tree limit
---

Choose what to work on next.

```bash
python3 .claude/scripts/agile.py index
python3 .claude/scripts/agile.py lint
python3 .claude/scripts/forge.py scopes
```

Selection rules, in order:

1. Only tickets with `status: todo` and `assignee: null`.
2. Skip anything whose `blocked_by` targets are not `done` or `cancelled`.
3. **Skip any scope whose working tree is already occupied** — that is, any
   scope sharing a repository with a ticket in `writing_tests`, `in_progress` or
   `review`. Each repository has one checkout; a second concurrent ticket in it
   corrupts the first. This is a hard stop, not a preference. `writing_tests`
   counts — `qa` is committing to a branch in that tree just as an engineer
   would be.
4. Order by `priority` (P0 first), then by ID.
5. Prefer a ticket that unblocks others over an equally-prioritised leaf.

Report the pick with a one-line justification, and name the runners-up you
skipped and why — especially anything skipped because its working tree was
occupied.

If nothing is eligible, say so and say what would unblock the board: a
dependency to finish, a bug to triage, or an empty backlog that needs
`/agile:groom`.

Do **not** start work. Stop here and let the user run `/agile:work <ID>`, which
begins with `qa` writing the failing tests rather than with an engineer.
