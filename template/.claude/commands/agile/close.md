---
description: Merge the PR, record the merge sha (and bump the submodule pointer) and close the ticket in one commit
argument-hint: [TASK-0001 or BUG-0042]
---

Close **$ARGUMENTS**. Do this yourself — do not delegate it to a subagent.

## 1. Preflight

```bash
python3 .claude/scripts/agile.py show $ARGUMENTS
python3 .claude/scripts/agile.py lint
python3 .claude/scripts/kb.py lint
python3 .claude/scripts/kb.py for-ticket $ARGUMENTS
python3 .claude/scripts/forge.py scopes
git status --short
git submodule status 2>/dev/null
```

Refuse to proceed, and say why, if:

- the ticket is not in `verify`;
- `branch` or `pr` is missing;
- `## Log` has no QA verdict;
- `## Log` carries no red-to-green evidence and no `NO-TEST` waiver — a ticket
  that reached `verify` without passing through `writing_tests` has skipped the
  test-first gate, and closing it silently launders that gap;
- `lint` reports an error on this ticket, from either validator;
- `docs:` is empty and there is no `docs_waiver: NO-DOCS (<reason>)` — closing a
  ticket that documented nothing and never said why launders exactly the gap the
  waiver exists to expose;
- the working tree has unrelated staged changes.

If merging this branch triggers a deployment, say so **before** merging and get
the user's explicit go-ahead. Check the live state rather than assuming it:

```bash
gh workflow list --repo <owner/name> --all
```

## 2. Merge and record

```bash
REPO=<repo path from forge.py repos, or . in a single-repo project>
BR=<its tracked branch>

gh pr merge <pr-url> --merge
git -C $REPO checkout $BR && git -C $REPO pull --ff-only
SHA=$(git -C $REPO rev-parse HEAD)
git -C $REPO merge-base --is-ancestor $SHA $BR || { echo "refusing to record"; exit 1; }
```

Then, on the ticket: set `merge_sha` to `$SHA`, `status: done`,
`assignee: null`, `updated` to today, and append a `## Log` line recording the
merge.

## 3. Actualise the knowledge base — part of closing, not a follow-up

For every note in the ticket's `docs:`:

- re-read it against what the work actually established, and **correct anything
  the work disproved**. A stale note is worse than a missing one: a missing note
  sends the next agent to the code, a wrong one sends it confidently the wrong
  way;
- add this ticket to `tickets:` if the work produced or confirmed the note — a
  note that was only read stays untouched;
- bump `updated:` to today. Never touch `created:` or the date in the filename;
- keep `## Related` current in both directions;
- a note the work has made wrong is **superseded, not deleted**:
  `status: superseded`, `superseded_by: <new basename>`, file kept.

```bash
python3 .claude/scripts/kb.py index
python3 .claude/scripts/kb.py lint
python3 .claude/scripts/agile.py index
python3 .claude/scripts/agile.py lint
```

Stage the knowledge base in the same commit as the close. It is part of the
ledger: a change that changed what we know should say so in the same breath.

```bash
# super-repo: stage the submodule too, so the pointer bump and the close are one commit
git add $REPO docs
git commit -m "chore: bumps $REPO to ${SHA:0:7} ($ARGUMENTS)"
# single repo:
# git add docs && git commit -m "chore(agile): closes $ARGUMENTS at ${SHA:0:7}"
git push
```

In a super-repo the pointer bump and the `done` transition are **one commit** —
that is what makes the log a ledger where every pointer move names the ticket
behind it. Push the code repository before the super-repo: a pointer to an
unpushed sha is unclonable.

## 4. After

Delete the merged branch. If this was the last open child of a story, tell the
user the story is a candidate for rolling up, and offer to run `pm` on it.

Report: the merged PR, the recorded sha, the ticket's final state, which
knowledge-base notes were actualised, and what is now unblocked on the board.
