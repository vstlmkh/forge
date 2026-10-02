---
name: agile-dod
description: The Definition of Done — the two gates of the test-first cycle (the red gate qa clears before an engineer starts, and the review gate before a ticket reaches verify), where the per-scope matrix of runnable checks lives, and what to do when a check or a test is unavailable. Load before writing tests, before declaring yourself ready for review, and before verifying.
---

# Definition of Done

A ticket is done when the work is verified by checks that **really ran**, not by
an assertion that it looks right.

The cycle is test-first. `qa` writes the failing tests in `writing_tests`
**before** the engineer implements anything, and judges the result against those
same tests in `review`. There are therefore two gates, not one: the red gate
below, and the review gate further down.

## The matrix lives in `forge.json`, not in this file

```bash
python3 .claude/scripts/forge.py checks            # every scope
python3 .claude/scripts/forge.py checks <scope>    # the rows that bind this ticket
```

Each row carries a command, the directory it runs from, and whether it is
available here *today*. **Read it; do not recall it.** A project's tooling
changes under you, and a remembered matrix is how a missing check gets reported
as a passing one.

When a bootstrap ticket makes a check available, flipping
`"available": false` to `true` in `forge.json` is part of **that ticket's own
acceptance criteria** — so the gate tightens itself as the tooling lands.

## The honesty rule

> An unavailable check is recorded as `SKIPPED (<reason> — see TASK-000X)` in the
> ticket's `## Log`. It is never reported as a pass, and it is never quietly
> omitted.

The same rule governs the three waivers, and they are the same shape on purpose
— a gap that has been named, argued and made reviewable:

| Waiver | Means | Binding substitute |
|---|---|---|
| `SKIPPED (<reason> — see TASK-000X)` | the check does not exist here yet | the ticket that will create it |
| `NO-TEST (<reason>) - the review gate falls back to: <check>` | nothing callable to assert | the named check, run at review |
| `NO-DOCS (<reason>)` | the work established nothing durable | none — but the reason must survive scrutiny |

None of the three is a pass. All three are claims somebody can disagree with,
which is exactly why they are written down.

A young project is missing large parts of its quality tooling. Pretending
otherwise is the single worst failure mode available to an agent here: it turns
`verify` into a rubber stamp and the whole framework into theatre.

## The red gate — `writing_tests -> in_progress`

`qa` may hand a ticket to an engineer only when **all** of these hold.

1. **A test exists for every acceptance criterion**, committed on the ticket's
   branch. A criterion with no test is not ready to implement — either write the
   test or hand the ticket back to `pm` as unimplementable as written.
2. **The tests fail, and they fail for the right reason.** Paste the real red
   output into `## Log`. A test that errors on a missing import or a typo proves
   nothing; it must fail on the assertion, describing the behaviour that does not
   exist yet. This is the whole point of the stage — a test that has never been
   red cannot be trusted when it is green.
3. **The tests assert the required behaviour, not an implementation.** No
   assertions about private methods, internal call order, or the shape of code
   the engineer has not written yet. If the test can only pass one way, it is a
   specification of that one way, and it will be wrong.
4. **The test commit contains no production code.** Only test files, fixtures and
   factories. `qa` writing the implementation defeats the separation that makes
   its later verdict worth anything.
5. **The branch is pushed** and `branch` is recorded on the ticket, so the
   engineer continues on it rather than starting a second one.
6. **The ticket's `docs:` has been read, and does not contradict the tests.**
   `python3 .claude/scripts/kb.py for-ticket <TICKET-ID>` lists the notes `pm`
   gathered; they often carry the expected value, field name or unit a test has
   to assert. A note that contradicts an acceptance criterion sends the ticket
   back to `todo` for `pm` to reconcile — never resolve it yourself by picking
   whichever the test is easier to write against. An empty `docs:` with no waiver
   means the consult step was skipped, and that is a finding too.
7. **`python3 .claude/scripts/agile.py lint` exits 0.**

### When a test is genuinely impossible

Some tickets have no callable behaviour to assert: a value in `.env.example`, a
linter config, a CI workflow file, a documentation change. Do not manufacture a
hollow test for these — a test that only restates the diff is worse than none,
because it will pass forever regardless of whether the thing works.

Instead, `qa` records a waiver in `## Log` and moves the ticket straight on:

```
NO-TEST (<why no automated test can assert this>) - the review gate falls back
to: <the concrete check that will be run instead>
```

The waiver must name the substitute check, and that check becomes binding at the
review gate exactly as a test would be. `NO-TEST` with no substitute is not a
waiver, it is a gap. Reach for it only when the answer to "what would the test
call?" is genuinely "nothing" — not when writing the test is merely awkward.

## The review gate — `review -> verify`

A ticket may move `review -> verify` only when **all** of these hold. QA checks
them; `agile.py lint` covers the mechanical half.

1. **The tests written in `writing_tests` now pass**, and QA ran them itself.
   Paste the green output next to the red output from the earlier stage, so the
   ticket carries the red-to-green transition in one place.
2. **Those tests are unmodified.** This is the load-bearing check of the whole
   cycle, and the one most worth attacking. Diff the test files between the red
   commit and the branch head:

   ```bash
   git -C <repo> diff <red-commit>..HEAD -- <test paths>
   ```

   An empty diff is the expected result. Any change is a rejection **unless** the
   engineer justified it in `## Log` and QA independently agrees the original test
   was wrong — in which case the honest route was `in_progress -> writing_tests`,
   and QA says so. A deleted assertion, a loosened matcher, a `skip`, an `only`
   narrowing the run, a widened tolerance or a changed expected value are all
   defects in the work, not in the test. Green tests that the engineer edited to
   become green prove nothing whatsoever.
3. **If the ticket carries a `NO-TEST` waiver**, the substitute check that the
   waiver named has been run, and its real output is in `## Log`. The waiver is
   not a pass by itself.
4. **Every acceptance criterion is ticked, and each has an evidence line in
   `## Log`** naming the command that proved it or the file and line that shows
   it. A ticked box with no evidence is a failed gate.
5. **Every available check for the ticket's scope has been run and passed.**
   `forge.py checks <scope>` is the list. Paste the meaningful part of the output
   into `## Log` — not "passed", the actual result.
6. **Every unavailable check is recorded as `SKIPPED`** with its blocking ticket
   ID.
7. **The whole suite passes, not only the new tests.** A ticket that turns its
   own tests green while breaking others is a rejection.
8. **The PR exists, is open against the tracked branch, and contains no
   unrelated files.** Nothing from the project's never-commit list is in the
   diff.
9. **No new lint or type errors relative to the base branch.** Pre-existing
   errors elsewhere in the repo are not this ticket's problem — say so rather
   than fixing them silently.
10. **Commit messages conform** to `agile-git`.
11. **For a bug:** `## Root cause` is filled in, and the original
    `## Steps to reproduce` has been re-run and no longer reproduces.
12. **The knowledge the work revealed is filed, correctly.** This is the
    documentation half of the gate, and it is judged the way the tests are:
    - every note in `docs:` resolves; the ones this work produced or confirmed
      list the ticket in `tickets:` and have `updated:` bumped to today;
    - each finding is filed under the **right type** — a business rule as
      `business-rule`, an incident as `troubleshooting`, an external system's
      behaviour as `integration`, a cross-boundary promise as `api-contract`.
      `kb.py lint` cannot see a misfiling; QA can, and a rule buried in an
      `overview` note is a rejection;
    - one finding per note, each with real evidence, each cross-linked in
      `## Related` in both directions;
    - a note this work **disproved** has been corrected, not left standing.
      Two contradicting notes are worse than none.
13. **A `NO-DOCS` waiver, if present, is argued and true.** The shape is
    `docs_waiver: NO-DOCS (<why this work left nothing worth knowing>)` with
    `docs: []`. It is legitimate for a formatting sweep, a dependency bump or a
    typo. It is a rejection on a ticket that changed behaviour, fixed a defect,
    or chose between approaches — that work always leaves something a future
    agent needs. "No time to document" is not a reason; it is the gap the waiver
    exists to make visible.
14. **`python3 .claude/scripts/agile.py lint` and
    `python3 .claude/scripts/kb.py lint` both exit 0.**

## Bug-specific addition

A bug fix needs a regression test — one that fails before the fix and passes
after it. Under the test-first cycle this is not a special case: the regression
test **is** the `writing_tests` deliverable for a bug, and the red output in
`## Log` is the proof that it reproduces the defect.

Where the defect genuinely has nothing to call — a wrong value in a committed
config file, for instance — use the `NO-TEST` waiver above with the reproduction
command as the substitute check, and record its output in `## Verification`.

If the project has no runnable test command at all for that scope, that is a
bootstrap gap: say so, file the ticket that fixes it, and record `SKIPPED` with
its ID. Do not quietly drop the requirement.

## Rejecting

QA rejects by moving the ticket back to `in_progress` and appending to `## Log`:
what failed, the exact command, and the exact output. Never reject with a
judgement alone. Never fix the production code yourself — that collapses the
separation that makes the verdict worth anything.

The one thing QA may edit is a test it wrote itself, and only via
`writing_tests`, never silently while the ticket sits in `review`. If the
engineer has argued the test is wrong and QA agrees, the honest move is to say
so in `## Log`, move the ticket back to `writing_tests`, fix the test, prove it
red again, and hand it over once more. Quietly correcting a test during review
and then passing the ticket is indistinguishable from the engineer having
weakened it.
