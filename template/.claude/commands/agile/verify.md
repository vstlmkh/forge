---
description: Run the QA review gate against a ticket on its own
argument-hint: [TASK-0001 or BUG-0042]
---

Verify **$ARGUMENTS** against its acceptance criteria and the Definition of Done.

Use this to re-verify after a rejection, or to verify a change that was made by
hand rather than through `/agile:work`.

```bash
python3 .claude/scripts/agile.py show $ARGUMENTS
```

Dispatch the `qa` subagent with the ticket path and, if there is one, the PR URL.

QA must:

- run the tests it wrote in `writing_tests` and confirm they now pass;
- **diff those test files against its own red commit and confirm they were not
  weakened** — `git -C <repo> diff <red-commit>..HEAD -- <test paths>`. An empty
  diff is the expected result; a loosened matcher, a deleted assertion, a `skip`
  or a changed expected value is a rejection. This is the load-bearing check of
  the cycle;
- judge the documentation half of the gate as well: every note in `docs:`
  resolves and is correctly typed, the ones this work produced list the ticket
  and have `updated:` bumped, findings are cross-linked in `## Related`, and any
  `NO-DOCS` waiver is argued rather than asserted. QA judges the notes; it does
  not write the engineer's notes and then approve them;
- if the ticket carries a `NO-TEST` waiver, run the substitute check the waiver
  named and paste its output — the waiver is not itself a pass;
- check each acceptance criterion individually, by running a command or pointing
  at a file and line — never by reading the diff and finding it plausible;
- run every available check for the ticket's scope
  (`python3 .claude/scripts/forge.py checks <scope>`), plus the whole suite
  rather than only the new tests, and paste the real output;
- record every unavailable check as `SKIPPED (<reason> — see TASK-000X)`;
- confirm the diff is clean of unrelated and ignored files, and that the commits
  carry a `Refs:` trailer;
- for a bug, confirm `## Root cause` is filled and re-run the reproduction;
- write the verdict into `## Log`, with the red and green output together, and
  move the ticket to `verify` or back to `in_progress`.

QA never edits production code. If a one-line change would make a check pass,
that is still a rejection. It may not edit its own tests either while the ticket
is in `review` — a wrong test means moving the ticket back to `writing_tests` and
saying so, not a quiet correction.

If the ticket never went through `writing_tests` — a change made by hand, or one
closed before this cycle existed — say so explicitly in the verdict. There is no
red-to-green evidence to check in that case, and the verdict is weaker for it.

`verify` means the ticket is awaiting the user's acceptance, not that it is done.

Report the verdict, the evidence per criterion, and — on a rejection — exactly
what has to change.
