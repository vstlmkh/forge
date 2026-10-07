---
name: agile-dod
description: The Definition of Done — what "verified" means, the honesty rule and the five waivers, the checklist a ticket must satisfy at review, and how to reject. The six gate contracts themselves are data, printed by `agile.py gates`; this skill is the reasoning around them. Load before declaring yourself ready for review, and before verifying.
---

# Definition of Done

A ticket is done when the work is verified by checks that **really ran**, not by
an assertion that it looks right.

The cycle is specification-first and then test-first. `qa` grills the request
into a numbered brief in `speccing`, writes the failing tests against that brief
in `writing_tests` **before** the engineer implements anything, and judges the
result against both in `review`.

## The contract is data; this file is not

Each of the six gates has the same contract — owner, entry, artifact, exit,
failure route, waiver, prohibitions, steps — and it lives in one place, the
`GATES` table in `agile.py`:

```bash
python3 .claude/scripts/agile.py gates          # all six
python3 .claude/scripts/agile.py gates 4        # one
python3 .claude/scripts/agile.py handoff <TICKET-ID> --gate <N>   # one, for a ticket
```

**Read it; do not recall it, and do not look for it here.** A second copy of a
gate's text in prose is a copy that drifts, and the agent obeys whichever one it
read last. What follows is what the table cannot hold: why the gates exist, what
"verified" means in detail at review, and what to do when something is
unavailable.

| | Gate | Status | Owner | What it defends against |
|---|---|---|---|---|
| G1 | brief, carryover, spec | `speccing` | `qa` | implementing an ambiguous request faithfully and wrongly |
| G2 | writing the tests | `writing_tests` | `qa` | a test that was never red |
| G3 | red to green | `in_progress` | the scope's engineer | a green suite that was edited into greenness |
| G4 | validation | `review` | `qa` | a criterion that is merely plausible from the diff |
| G5 | documentation and lessons | `review` | `qa` | the next agent re-deriving what this one learned, or repeating the bounce that taught it |
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

The same rule governs the waivers, and they are the same shape on purpose — a
gap that has been named, argued and made reviewable:

| Waiver | Means | Binding substitute |
|---|---|---|
| `SKIPPED (<reason> — see TASK-000X)` | the check does not exist here yet | the ticket that will create it |
| `NO-TEST (<reason>) - the review gate falls back to: <check>` | nothing callable to assert | the named check, run at review |
| `NO-DOCS (<reason>)` | the work established nothing durable | none — but the reason must survive scrutiny |
| `spec_waiver: NO-SPEC (<reason>)` | the ticket is too small to grill | none — and a ticket that needed a question is not small |
| `lessons_waiver: NO-LESSON (<reason>)` | the ticket taught nothing about working here | none — and a ticket that bounced taught something |
| `NO-TICKET (<reason>)` | a carryover row that will never become work | none — the row stays, so the decision stays visible |

None of them is a pass. All of them are claims somebody can disagree with, which
is exactly why they are written down.

A young project is missing large parts of its quality tooling. Pretending
otherwise is the single worst failure mode available to an agent here: it turns
`verify` into a rubber stamp and the whole framework into theatre.

## What "verified" means at review

The gate contract says *every agreed REQ proved by something you ran yourself*.
This is that sentence, expanded. `agile.py lint` covers the mechanical half and
`agile.py handback <ID> --gate 4` reports what it can see; the rest is judgement,
and it is why a gate has an owner rather than a hook.

1. **The tests written in `writing_tests` now pass**, and QA ran them itself.
   The red output and the green output sit together in `## Log`.
2. **Those tests are unmodified.** This is the load-bearing check of the whole
   cycle, and the one most worth attacking:

   ```bash
   git -C <repo> diff <red-commit>..HEAD -- <test paths>
   ```

   An empty diff is the expected result. A deleted assertion, a loosened
   matcher, a `skip`, an `only` narrowing the run, a widened tolerance or a
   changed expected value are defects in the work, not in the test. Any change
   is a rejection **unless** the engineer argued it in `## Log` and QA
   independently agrees the original test was wrong — in which case the honest
   route was `in_progress -> writing_tests`, and QA says so. Green tests that
   the engineer edited to become green prove nothing whatsoever.
3. **Every acceptance criterion is ticked and has an evidence line** in `## Log`
   naming the command that proved it or the file and line that shows it. A
   ticked box with no evidence is a failed gate.
4. **Every available check for the scope ran and passed**, plus the whole suite —
   not only the new tests. Paste the meaningful part of the output, not the word
   "passed". Unavailable rows are `SKIPPED` with their blocking ticket.
5. **A `NO-TEST` waiver is not a pass by itself**: the substitute check it named
   has been run and its real output is in `## Log`.
6. **No new lint or type errors relative to the base branch.** Pre-existing
   errors elsewhere are not this ticket's problem — say so rather than fixing
   them silently.
7. **The PR is open against the tracked branch and contains no unrelated files**,
   nothing from the never-commit list, and commit messages conform to
   `agile-git`.
8. **Every requirement still marked `assumed` is named in the verdict.** QA wrote
   the brief and is now judging against it; naming the assumptions is what keeps
   that weakness visible to the user at `verify` instead of invisible. `lint`
   already reports it as a `WARN` — do not pass it in silence.
9. **For a bug:** `## Root cause` is filled in, and the original
   `## Steps to reproduce` no longer reproduces.

Then the knowledge half, at gate 5:

10. **The knowledge the work revealed is filed, correctly** — one finding per
    note, under the right type, with real evidence, cross-linked in `## Related`
    both ways, the ticket listed in `tickets:` and `updated:` bumped. `kb.py
    lint` cannot see a misfiling; QA can, and a business rule buried in an
    `overview` note is a rejection. A note this work **disproved** is corrected,
    not left standing: two contradicting notes are worse than none.
11. **A `NO-DOCS` waiver is argued and true.** Legitimate for a formatting sweep,
    a dependency bump or a typo; a rejection on a ticket that changed behaviour,
    fixed a defect or chose between approaches. "No time to document" is not a
    reason, it is the gap the waiver exists to make visible.
12. **What the ticket taught about working here is recorded.** `lessons:` names
    the rule it produced or confirmed, or `lessons_waiver: NO-LESSON (<reason>)`
    says it taught nothing. Normal for a ticket that ran straight through; a
    rejection for one that went backwards at any gate. Confirming an existing
    rule beats a near-duplicate — `lessons.py list` before `lessons.py new`. The
    procedure is `agile-lessons`.
13. **`agile.py lint`, `kb.py lint` and `lessons.py lint` all exit 0.**

`qa` does not write the notes or the lesson the engineer owed and then approve
them. Filing is the engineer's job; judging is QA's. Doing both destroys the
separation the verdict rests on, exactly as writing the production code would.

## A bug is not a special case

The regression test **is** the `writing_tests` deliverable for a bug, and the red
output in `## Log` is the proof that it reproduces the defect.

Where the defect genuinely has nothing to call — a wrong value in a committed
config file, say — use the `NO-TEST` waiver with the reproduction command as the
substitute check, and record its output in `## Verification`. If the project has
no runnable test command at all for that scope, that is a bootstrap gap: say so,
file the ticket that fixes it, and record `SKIPPED` with its ID. Do not quietly
drop the requirement.

## Rejecting

QA rejects by moving the ticket back to `in_progress` and writing **one `## Log`
entry opening `REJECTED G4:` or `REJECTED G5:`** that carries what failed, the
exact command and its exact output, and the REQ it blocks.

The shape matters because of how the engineer is re-dispatched: with a plain
`agile.py handoff <ID> --gate 3`, which carries the last few log entries and
nothing else. **A finding reported only to the orchestrator does not reach the
engineer.** Never reject with a judgement alone, and never fix the production
code yourself — that collapses the separation that makes the verdict worth
anything.

The one thing QA may edit is a test it wrote itself, and only via
`writing_tests`, never silently while the ticket sits in `review`. If the
engineer argued the test is wrong and QA agrees, the honest move is to say so in
`## Log`, move the ticket back, fix the test, prove it red again, and hand it
over once more. Quietly correcting a test during review and then passing the
ticket is indistinguishable from the engineer having weakened it.
