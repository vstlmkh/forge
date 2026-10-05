---
name: agile-dod
description: The Definition of Done — the six gates a ticket passes through (the brief, the red tests, the implementation, validation, documentation and the board), where the per-scope matrix of runnable checks lives, and what to do when a check, a test or an answer is unavailable. Load before specifying a ticket, before writing tests, before declaring yourself ready for review, and before verifying.
---

# Definition of Done

A ticket is done when the work is verified by checks that **really ran**, not by
an assertion that it looks right.

The cycle is specification-first and then test-first. `qa` grills the request
into a numbered brief in `speccing`, writes the failing tests against that brief
in `writing_tests` **before** the engineer implements anything, and judges the
result against both in `review`.

There are therefore **six gates**, each with the same contract — owner, entry,
artifact, exit, failure route, waiver. The contract is data, not prose:

```bash
python3 .claude/scripts/agile.py gates          # all six
python3 .claude/scripts/agile.py gates 4        # one
```

**Read it; do not recall it**, for the same reason the check matrix is read
rather than remembered. What follows is the *reasoning* behind each gate — why
it exists and what it is defending against. The contract itself, and the
dispatch payload that carries it to an agent, both come out of the script:

```bash
python3 .claude/scripts/agile.py handoff <TICKET-ID> --gate <N>
```

| | Gate | Status | Owner | What it defends against |
|---|---|---|---|---|
| G1 | brief, carryover, spec | `speccing` | `qa` | implementing an ambiguous request faithfully and wrongly |
| G2 | writing the tests | `writing_tests` | `qa` | a test that was never red |
| G3 | red to green | `in_progress` | the scope's engineer | a green suite that was edited into greenness |
| G4 | validation | `review` | `qa` | a criterion that is merely plausible from the diff |
| G5 | documentation | `review` | `qa` | the next agent re-deriving what this one learned |
| G6 | board update | `review` | `pm` | deferred work quietly disappearing |

G5 and G6 run in parallel after G4, and they write disjoint files: G5 writes the
knowledge base and this ticket; G6 writes *other* tickets and the parent. `qa`
makes the `review -> verify` move once both have reported.

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
| `spec_waiver: NO-SPEC (<reason>)` | the ticket is too small to grill | none — and a ticket that needed a question is not small |
| `NO-TICKET (<reason>)` | a carryover row that will never become work | none — the row stays, so the decision stays visible |

None of the five is a pass. All five are claims somebody can disagree with,
which is exactly why they are written down.

A young project is missing large parts of its quality tooling. Pretending
otherwise is the single worst failure mode available to an agent here: it turns
`verify` into a rubber stamp and the whole framework into theatre.

## Gate 1 — the brief — `todo -> speccing -> writing_tests`

A request arrives underspecified. That is normal and is not `pm`'s failure: a
groomed ticket states a testable intent, and the detail that a test actually
needs — the expected value, the boundary, the error case — only surfaces when
somebody tries to write the test. Gate 1 is where that happens, **before** a
branch exists and before anyone has written code against a guess.

`qa` may move a ticket to `writing_tests` only when all of these hold.

1. **A spec exists at `<tracker>/specs/<ID>.md`**, created with
   `agile.py spec new <ID>` and never by hand, and the ticket's `spec:` names it.
2. **Every requirement the repository could answer was answered from the
   repository.** The knowledge base first (`kb.py for-ticket`, `kb.py find`),
   then the code. A question put to the user that a note already answers wastes
   the one resource the cycle cannot refill: the user's attention.
3. **Everything else was asked, not assumed.** The open questions go into
   `## Questions` in one batch, the spec's status becomes `questions`, and `qa`
   **stops**. It has no way to ask the user and must not invent one; the
   top-level session puts the batch to the user and dispatches `qa` again with
   the answers. A requirement `qa` had to decide alone is recorded `assumed`,
   never `agreed` — see the honesty rule.
4. **Everything deferred is in `## Carryover`,** not deleted. An unanswered
   question becomes a carryover row; it does not become an assumption.
5. **Each live requirement is tagged into the acceptance criteria** as
   `(REQ-NNNN)`. That tag is what lets gate 2 write one test per requirement and
   gate 4 produce one evidence line per requirement.
6. **The spec's status is `agreed`** — which `lint` reads as the gate's exit
   condition — and `agile.py lint` exits 0.

A request that cannot be specified even after a round of questions goes back to
`todo` for `pm` to reshape. Two rounds of questions is legitimate; a third means
the ticket is wrong, not the answers.

### When a spec is genuinely overkill

A ticket with nothing to grill — a typo, a version bump, a one-line config
value — carries `spec_waiver: NO-SPEC (<reason>)` and skips to `writing_tests`.
The test is whether a question could sensibly be asked about it. If one could,
the ticket is not small, and the waiver is a way of skipping the gate rather
than clearing it.

## Gate 2 — the red gate — `writing_tests -> in_progress`

`qa` may hand a ticket to an engineer only when **all** of these hold.

1. **A test exists for every `agreed` requirement in the brief**, committed on
   the ticket's branch, and `## Log` says which REQ each test covers. A
   requirement with no test is not ready to implement — either write the test or
   send the ticket back to `speccing` and say which requirement cannot be
   expressed as one.
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

## Gate 3 — red to green — `in_progress -> review`

The engineer's gate, and it is short because the brief and the red tests have
already said everything: implement until they pass, run every available check
for the scope plus the whole suite, open the PR, file what the work revealed,
and stop at `review`.

Two rules carry the weight. **The tests are not the engineer's to change** —
that is gate 4's load-bearing check, below. And **a requirement that is not in
the brief is not implemented**: if the work turns out to need one, the engineer
says so in `## Log` and hands back, because a requirement that enters at gate 3
was never grilled, never costed and never agreed.

## Gate 4 — validation — the evidence half of `review`

A ticket may clear gate 4 only when **all** of these hold. QA checks them;
`agile.py lint` covers the mechanical half.

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
12. **Every requirement still marked `assumed` in the brief is named in the
    verdict.** An assumption that nobody confirmed is the one weakness of this
    design — `qa` wrote the brief and is now judging against it — and naming it
    is what keeps the weakness visible to the user at `verify` instead of
    invisible. `lint` already reports it as a `WARN`; do not pass it in silence.

## Gate 5 — documentation — the knowledge half of `review`

13. **The knowledge the work revealed is filed, correctly.** This is the
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
14. **A `NO-DOCS` waiver, if present, is argued and true.** The shape is
    `docs_waiver: NO-DOCS (<why this work left nothing worth knowing>)` with
    `docs: []`. It is legitimate for a formatting sweep, a dependency bump or a
    typo. It is a rejection on a ticket that changed behaviour, fixed a defect,
    or chose between approaches — that work always leaves something a future
    agent needs. "No time to document" is not a reason; it is the gap the waiver
    exists to make visible.
15. **`python3 .claude/scripts/agile.py lint` and
    `python3 .claude/scripts/kb.py lint` both exit 0.**

`qa` does not write the notes the engineer owed and then approve them. Filing is
the engineer's job; judging is QA's. Doing both destroys the separation the
verdict rests on, exactly as writing the production code would.

## Gate 6 — the board — in parallel with gate 5

`pm`'s gate, and the only one it owns after `todo`. It reads the spec's
`## Carryover`, files one properly groomed ticket per row, and writes the new id
into the row's `Becomes` cell. A row that should never become work gets
`NO-TICKET (<reason>)` there instead, argued.

Two boundaries make this safe to run alongside gate 5. **`pm` transitions
nothing** — it creates other artifacts, and `qa` still makes the
`review -> verify` move; the rule that `pm` may not move a task past `todo` is
untouched. And **`pm` does not edit the ticket under review**, because `qa` is
writing its `## Log` at that very moment and two writers on one file lose each
other's work.

The gate exists because deferred work is the easiest thing in any process to
lose. A carryover row with no ticket and no argument is `lint` error at
`verify`, not a note to self.

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
