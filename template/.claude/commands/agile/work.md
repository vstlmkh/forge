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

**You do not write dispatch prompts by hand, and you do not relay anything by
hand either.** For each gate:

```bash
python3 .claude/scripts/agile.py handoff $ARGUMENTS --gate <N>
```

Send that output to the subagent **verbatim, and send nothing else**. Everything
a gate needs is in it, because everything a gate needs is in the repository:
the contract, the rules this project has already paid for, the ticket's notes,
the spec's brief, the answers the user gave at gate 1, and the last few `## Log`
entries — including a rejection written by the gate that sent the work back.

That is the rule, not a style preference. A fact that reaches a subagent only
through your message reaches it exactly once and survives only as long as your
context does; the same fact written into the ticket, the spec or the lessons
layer is in git. **If you find yourself wanting to add a paragraph, the paragraph
belongs in a file** — put it there and re-run `handoff`.

The layout it produces is the point too. The binding instructions sit in the
first screen and are repeated, compressed, in the last; the reference material
sits between them as paths and commands rather than pasted file contents. **An
instruction buried in the middle of a long prompt is an instruction that will not
be followed** — so do not "tidy" the payload by moving the anchor or splicing a
preamble in front of the contract.

If `handoff` exits 2 it prints `BLOCKED` and names the transition that is
missing: the ticket is not where that gate runs. Fix the ticket's state or stop
— do not dispatch anyway.

## How you check every gate before you believe it

```bash
python3 .claude/scripts/agile.py handback $ARGUMENTS --gate <N>
```

Run it after every dispatch, before the next one. It reads the repository rather
than the report: did the status move, is the branch there, is the PR recorded,
is there an evidence line per requirement, is `lint` clean for this ticket. Exit
2 means the gate did not land whatever the subagent said, and the move is to send
it back — not to dispatch the next gate over a gap.

It runs nothing, and it says so: the lines marked `not checked here` are the ones
you still have to read the subagent's report for.

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

**Then write the answers down before you dispatch anybody:**

```bash
python3 .claude/scripts/agile.py spec answer $ARGUMENTS Q1="<what the user said>" Q2="..."
```

This is the one moment in the whole cycle where something the repository cannot
reconstruct — the user's own words — is passing through you. Written into
`## Questions` it is in git and the next payload renders it back; carried in your
next message it lasts exactly as long as this context does, and a compaction, an
interruption or a paraphrase loses it silently. A deferral is written
`Q3="DEFERRED - <the user's reason>"`, never left blank. The command refuses a
question id that does not exist, which is how a typo stops being a dropped
answer.

Then dispatch `qa` again with the **same command as before** —
`handoff $ARGUMENTS --gate 1` — now carrying the answers. It finishes the brief,
moves anything deferred into `## Carryover`, writes the spec and the plan, tags
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

Check it landed: `python3 .claude/scripts/agile.py handback $ARGUMENTS --gate 1`.

Read the brief before you go on. Anything marked `assumed` is a decision `qa`
made alone — if it looks consequential, put it to the user now rather than
discovering it at `verify`.

## 3. Gate 2 — the failing tests

Dispatch `qa` with the gate 2 payload. It cuts the branch, writes a test per
`agreed` requirement, **proves them red**, commits the tests alone, pushes, and
hands the ticket to the engineer in `in_progress` with the red output in
`## Log`.

Check it landed: `python3 .claude/scripts/agile.py handback $ARGUMENTS --gate 2`.

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

Check it landed: `python3 .claude/scripts/agile.py handback $ARGUMENTS --gate 3`.

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

Check they landed: `handback $ARGUMENTS --gate 4`, `--gate 5` and `--gate 6`.

`qa` makes the `review -> verify` move once both have reported, or rejects to
`in_progress` with the failing command and its output.

On a rejection, `qa` writes the finding into `## Log` as a `REJECTED G4:` or
`REJECTED G5:` entry carrying the command, its output and the requirement it
blocks. You re-dispatch the **same engineer with a plain
`handoff $ARGUMENTS --gate 3`** — the payload carries the last log entries, so
the finding travels in the ticket rather than in your message. If `qa` reported
something to you that is not in the ticket, that is the bug: send it back to
write it down rather than relaying it yourself.

**After two rejections, stop and bring the user in** — a third automated attempt
on the same ticket usually means the brief is wrong, not the code.

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
