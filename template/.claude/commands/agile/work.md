---
description: Run a ticket through the six gates — QA specs it with the user, writes failing tests, the engineer makes them pass, QA validates and judges the docs, PM files the carryover — stops at verify
argument-hint: [TASK-0001 or BUG-0042]
---

Take **$ARGUMENTS** from `todo` to `verify`.

```
todo -> speccing (qa) -> writing_tests (qa) -> in_progress (engineer)
     -> review (qa validates + judges docs ‖ pm files carryover) -> verify (you)
```

Six gates, one contract each. Read it rather than recalling it:

```bash
python3 .claude/scripts/agile.py gates
```

## How you compose every prompt in this command

**You do not write dispatch prompts by hand.** For each gate:

```bash
python3 .claude/scripts/agile.py handoff $ARGUMENTS --gate <N>
```

Send that output to the subagent **verbatim**, and add only what the script
cannot know — the user's answers at gate 1, QA's findings on a rejection.

The layout it produces is the point, not a formatting preference. The binding
instructions sit in the first screen and are repeated, compressed, in the last;
the reference material sits between them as paths and commands rather than
pasted file contents. **An instruction buried in the middle of a long prompt is
an instruction that will not be followed** — that is why nothing binding is ever
put there, and why you must not "tidy" the payload by moving the anchor or
splicing your own preamble in front of the contract. Append your extra context
to the reference section, in the middle, where it belongs.

If `handoff` exits 2 it prints `BLOCKED` and names the transition that is
missing: the ticket is not where that gate runs. Fix the ticket's state or stop
— do not dispatch anyway.

## 1. Preflight — you do this yourself, before dispatching anyone

```bash
python3 .claude/scripts/agile.py show $ARGUMENTS
python3 .claude/scripts/agile.py lint
python3 .claude/scripts/kb.py for-ticket $ARGUMENTS
python3 .claude/scripts/forge.py scopes
git status --short
```

Stop and report instead of proceeding if any of these hold:

- the ticket is not `todo`, or `assignee` is not null;
- any `blocked_by` target is still open;
- another ticket occupying the same working tree is already `writing_tests`,
  `in_progress` or `review` — note that `speccing` does **not** occupy one, so a
  ticket being specified elsewhere is not a blocker;
- the target repository's working tree is dirty, or sits on an unexpected branch.

If `docs:` is empty and there is no `docs_waiver`, the ticket was groomed without
consulting the knowledge base. That is not fatal — but say so, and bring in `pm`
rather than letting the cycle start blind.

## 2. Gate 1 — the brief, and the only questions the user will be asked

Dispatch `qa` with the gate 1 payload. It claims the ticket into `speccing`,
scaffolds the spec, answers what the knowledge base and the code can answer, and
comes back with **a batch of open questions** — not with a finished spec.

**You** then put those questions to the user, with `AskUserQuestion`:

- **in one batch**, every question at once. A question at a time turns a
  two-minute decision into a ten-minute interrogation;
- **in the user's language**, verbatim as `qa` phrased them, with the
  requirement each one blocks;
- offering "defer this" as a real option. A deferred answer is carryover, which
  is a recorded decision — it is not a gap.

Dispatch `qa` again with the answers. It finishes the brief, moves anything
deferred or unanswered into `## Carryover`, writes the spec and the plan, tags
the acceptance criteria with their `(REQ-NNNN)`, and moves the ticket to
`writing_tests`.

Three legitimate outcomes are not a handover:

- **the request cannot be specified even after answers** — `qa` moves it back to
  `todo` and says why. Bring in `pm`; do not paper over it;
- **a second round of questions** is fine. **A third is not** — stop and tell the
  user the ticket is wrong, not the answers;
- **the ticket is too small to grill** — `qa` records
  `spec_waiver: NO-SPEC (<reason>)` and moves straight on. Check the reason is
  honest: if a question could sensibly have been asked, it was not too small.

Read the brief before you go on. Anything marked `assumed` is a decision `qa`
made alone — if it looks consequential, put it to the user now rather than
discovering it at `verify`.

## 3. Gate 2 — the failing tests

Dispatch `qa` with the gate 2 payload. It cuts the branch, writes a test per
`agreed` requirement, **proves them red**, commits the tests alone, pushes, and
hands the ticket to the engineer in `in_progress` with the red output in
`## Log`.

Read the red output before dispatching the engineer. If `qa` reports tests that
were never red, or red for a reason unrelated to the ticket, send it back — a
test that has not legitimately failed proves nothing when it passes. A
requirement that turns out untestable sends the ticket to `speccing`, not into
an invented assertion.

## 4. Gate 3 — implement

Dispatch the subagent that owns the ticket's `scope`; the gate 3 payload names
it. It checks out `qa`'s branch, reads the **spec** rather than the ticket's
log, runs the tests to see them fail, implements until they pass, runs every
available check for that scope plus the whole suite, commits with a `Refs:`
trailer, pushes, opens a PR, files the knowledge-base notes its work revealed,
and sets `status: review`.

It must not cut a new branch, touch `qa`'s tests, or implement a requirement the
brief does not carry. If it reports that a test is genuinely wrong, the legal
move is `in_progress -> writing_tests`; if it reports a *missing requirement*,
that is gate 1 reopening, and the user decides whether it is in scope or
carryover.

## 5. Gates 4, 5 and 6 — validate, document, file the carryover

Dispatch **`qa` (gates 4 and 5) and `pm` (gate 6) in the same message**, in
parallel. They write disjoint files — `qa` writes the knowledge base and this
ticket, `pm` writes *other* tickets and the parent — which is what makes running
them together safe. Do not let `pm` touch the ticket under review.

`qa` runs its own tests, **diffs the test files against its red commit to
confirm they were not weakened**, proves each requirement with evidence, runs
every available check plus the whole suite, records skipped ones honestly, names
any requirement still `assumed`, and judges the notes the engineer filed. `pm`
turns each carryover row into a groomed ticket and writes the id back into the
row.

`qa` makes the `review -> verify` move once both have reported, or rejects to
`in_progress` with the failing command and its output.

On a rejection, hand the QA findings back to the same engineer and repeat this
step. **After two rejections, stop and bring the user in** — a third automated
attempt on the same ticket usually means the brief is wrong, not the code.

## 6. Report

```bash
python3 .claude/scripts/agile.py lint
python3 .claude/scripts/kb.py lint
```

Tell the user: the final status, the PR URL, **the brief and what it cost** —
which requirements shipped, which were deferred and into which tickets, which
remain `assumed` — the red-to-green evidence, whether the tests survived
untouched, which checks passed, which were skipped and why, any `NO-TEST` waiver
and what was run instead, which knowledge-base notes were filed or corrected,
and what `/agile:close $ARGUMENTS` would do next.

`verify` means the ticket is waiting on the user's acceptance.

**Do not merge, do not bump a submodule pointer, do not set `done`.** That is
`/agile:close`, and it is a separate decision.
