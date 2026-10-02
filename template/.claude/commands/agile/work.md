---
description: Run a ticket through the test-first cycle — QA writes failing tests, the engineer makes them pass, QA judges the result — stops at verify
argument-hint: [TASK-0001 or BUG-0042]
---

Take **$ARGUMENTS** from `todo` to `verify`.

The cycle is test-first, so `qa` runs twice and the engineer sits between them:

```
todo -> writing_tests (qa) -> in_progress (engineer) -> review (qa) -> verify (you)
```

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
  `in_progress` or `review`;
- the target repository's working tree is dirty, or sits on an unexpected branch.

If `docs:` is empty and there is no `docs_waiver`, the ticket was groomed without
consulting the knowledge base. That is not fatal — but say so, and bring in `pm`
rather than letting the cycle start blind. Read the notes it does list before you
dispatch anyone; you are about to hand the same reading list to two agents.

## 2. Write the tests — `qa`, before anyone implements

Dispatch `qa` with the ticket path. It claims the ticket into `writing_tests`,
cuts the branch, writes a test per acceptance criterion, **proves them red**,
commits the tests alone, pushes, and hands the ticket to the engineer in
`in_progress` with the red output in `## Log`.

If the claim edit fails, the ticket was taken by someone else. Stop and report
the lost race — do not force the claim.

Two legitimate outcomes are not a handover, and both stop the cycle here:

- **the criteria are too vague to test** — `qa` moves the ticket back to `todo`
  and names the criterion. Bring in `pm`, do not paper over it;
- **no automated test is possible** — `qa` records a
  `NO-TEST (<reason>) - the review gate falls back to: <check>` waiver and hands
  over anyway. That is fine; carry the named substitute check into step 4 and
  make sure QA actually runs it.

Read the red output before dispatching the engineer. If `qa` reports tests that
were never red, or red for a reason unrelated to the ticket, send it back — a
test that has not legitimately failed proves nothing when it passes.

## 3. Implement

Dispatch the subagent that owns the ticket's `scope` —
`python3 .claude/scripts/forge.py scopes` names it. Pass it the ticket path and
the branch.

It checks out `qa`'s branch, reads the notes in `docs:`, runs the tests to see
them fail, implements until they pass, runs every available check for that scope
plus the whole suite, commits with a `Refs:` trailer, pushes, opens a PR, files
the knowledge-base notes its work revealed, and sets `status: review`.

It must not cut a new branch, and it must not touch `qa`'s tests. If it reports
that a test is genuinely wrong, the legal move is
`in_progress -> writing_tests` — hand it back to `qa` rather than letting the
engineer edit the test.

## 4. Verify

Dispatch `qa` again with the ticket path and the PR URL. It runs its own tests,
**diffs the test files against its red commit to confirm they were not
weakened**, checks each acceptance criterion, runs every available check plus the
whole suite, records skipped ones honestly, judges the knowledge-base notes the
engineer filed — right type, real evidence, cross-linked, and any `NO-DOCS`
waiver actually argued — and either moves the ticket to `verify` or rejects it to
`in_progress` with the failing command and its output.

On a rejection, hand the QA findings back to the same engineer and repeat step 4.
**After two rejections, stop and bring the user in** — a third automated attempt
on the same ticket usually means the acceptance criteria are wrong, not the code.

## 5. Report

```bash
python3 .claude/scripts/agile.py lint
python3 .claude/scripts/kb.py lint
```

Tell the user: the final status, the PR URL, the red-to-green evidence, whether
the tests survived untouched, which checks passed, which were skipped and why,
any `NO-TEST` waiver and what was run instead, which knowledge-base notes were
filed or corrected (or the `NO-DOCS` waiver and why it stands), and what
`/agile:close $ARGUMENTS` would do next.

`verify` means the ticket is waiting on the user's acceptance.

**Do not merge, do not bump a submodule pointer, do not set `done`.** That is
`/agile:close`, and it is a separate decision.
