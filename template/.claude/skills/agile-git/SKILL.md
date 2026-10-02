---
name: agile-git
description: The git protocol — branch naming, commit style, PR creation, who may push where, and (in a super-repo) the submodule pointer-bump rules that keep the tracker coherent with the code it describes. Load before any git operation.
---

# Git protocol

The repositories this workspace spans, and the branch each tracks, are declared
in `forge.json`:

```bash
python3 .claude/scripts/forge.py repos    # name, path, tracked branch, submodule or not
python3 .claude/scripts/forge.py scopes   # which scope lives in which repo
```

Two shapes are supported and the difference matters only in the last section:

- **single repository** — tickets and code share one history. There is no
  pointer to bump; closing a ticket is a merge plus a tracker commit.
- **super-repo with submodules** — code changes happen inside a submodule and
  the super-repo records which commit of each it points at. Keeping those
  histories coherent is what the pointer-bump rules are for.

## Who may do what

| Actor | May run git in |
|---|---|
| `pm` | the tracker and the knowledge base only. Read-only in code repositories. |
| an engineer | its own scope's repository (commit, push, PR on the branch `qa` cut) and its own ticket file. Does not cut the branch. |
| `qa` | **in `writing_tests`:** cuts the ticket's branch, commits test files only, pushes that branch. **Everywhere else:** read-only — `git diff`, `git log`, `gh pr view/diff`. Never commits production code, and never pushes a tracked branch. |
| orchestrator | merges PRs, bumps submodule pointers, pushes. |

Merging and pointer-bumping are the orchestrator's alone. A subagent that merges
its own PR has skipped the gate.

**The branch belongs to the ticket, not to the actor.** `qa` cuts it in
`writing_tests` and puts the red test commit on it; the engineer continues on
that same branch and opens the PR from it. Two branches for one ticket means the
tests and the implementation are not in the same PR, which defeats the review
gate.

## Branch names

The prefixes a project allows are in `forge.json` (`git.branch_prefixes`);
the default set is `feat` · `fix` · `chore` · `style` · `refactor` · `docs` ·
`test` · `perf`, followed by a kebab-case description:

```
feat/add-price-per-day-to-subscription-resource
fix/onboarding-500-on-empty-answer-list
```

No ticket ID in the branch name — traceability comes from the commit trailer.

## Commit messages

Conventional Commits, with the verb form the project declared in
`git.commit_style`. The default, `conventional-third-person`, reads:

```
<type>: <third-person verb> <what>

<optional body: why, not what>

Refs: TASK-0231
```

- Subject ≤ 72 characters, lowercase after the colon, no trailing period.
- **The `Refs:` trailer is mandatory in every code commit** (unless the project
  set `git.require_refs_trailer: false`). It is the only link from a line of
  code back to the ticket that asked for it.

## Never commit

The project's list is `git.never_commit` in `forge.json` — typically `.env`,
dependency directories, build output and IDE files. If `git status` shows one of
them, stop and fix `.gitignore` rather than staging selectively and hoping.

Never use `--no-verify`. A pre-commit hook is a real gate; bypassing it defeats
the point.

## Engineer workflow

```bash
REPO=backend           # the repo of your scope; `.` in a single-repo project
BR=main                # its tracked branch

git -C $REPO checkout $BR
git -C $REPO pull --ff-only
git -C $REPO status --short          # must be clean before you branch
git -C $REPO checkout -b feat/<kebab-description>

# ... implement, run `forge.py checks <scope>` ...

git -C $REPO add <specific paths>    # never `git add -A` blindly
git -C $REPO commit -m "feat: adds ...

Refs: TASK-0231"
git -C $REPO push -u origin feat/<kebab-description>
gh pr create --repo <owner/name> --base $BR --head feat/<kebab-description> \
  --title "feat: adds ..." --body "<see template below>"
```

Then set `branch`, `pr` and `status: review` on the ticket, append a `## Log`
line, and commit that: `chore(agile): moves TASK-0231 to review`.

### PR body template

```markdown
## What
<one paragraph>

## Why
Refs: TASK-0231 — <ticket title>

## How to verify
<the exact commands from the ticket's ## Verification section, with their output>

## Checks run
- [x] <test command> — the tests qa wrote in writing_tests, red at <sha>, now green
- [x] <lint command>
- [ ] <ci check> — SKIPPED (not available yet, see TASK-000X)
```

## Tracker commits — exactly three kinds

1. `chore(agile): opens STORY-014 with TASK-0231, TASK-0232` — artifacts created.
2. `chore(agile): moves TASK-0231 to review` — a status or field transition.
   The test-first cycle adds two of these per ticket: `claims TASK-0231` when
   `qa` takes it into `writing_tests`, and `hands TASK-0231 to <engineer>` when
   the tests are red and committed.
3. `chore: bumps backend to a1b2c3d (TASK-0231)` — a submodule pointer bump
   (super-repo shape only).

A knowledge-base note rides along with the commit for the ticket that produced
it. A note that belongs to no ticket (an audit, a correction found in passing)
gets its own commit: `docs(kb): records the stripe webhook ordering quirk`.

Neither `INDEX.md` ever gets its own commit. The `Stop` hook regenerates them and
they ride along with whichever of the three is being made.

**Kinds 1 and 2 must leave the submodule pointers untouched.** Verify before
committing:

```bash
git diff --cached --submodule    # must be empty for a status-only commit
```

## Closing

Only in `/agile:close`, only by the orchestrator, only after the PR is merged.

### Single repository

```bash
gh pr merge <url> --merge
git checkout main && git pull --ff-only
SHA=$(git rev-parse HEAD)
git merge-base --is-ancestor $SHA main || { echo "refusing to record"; exit 1; }
# set merge_sha, status: done, assignee: null on the ticket, append to ## Log
python3 .claude/scripts/agile.py index
git add docs && git commit -m "chore(agile): closes TASK-0231 at ${SHA:0:7}" && git push
```

### Super-repo with submodules

```bash
REPO=backend; BR=master; TICKET=TASK-0231

gh pr merge <url> --merge
git -C $REPO checkout $BR && git -C $REPO pull --ff-only
SHA=$(git -C $REPO rev-parse HEAD)
git -C $REPO merge-base --is-ancestor $SHA $BR || { echo "refusing to bump"; exit 1; }

# set merge_sha, status: done, assignee: null on the ticket, append to ## Log
python3 .claude/scripts/agile.py index

git add $REPO docs
git commit -m "chore: bumps $REPO to ${SHA:0:7} ($TICKET)"
git push
```

Rules that make this safe:

- **Never record a feature-branch sha.** Only after the merge, and only a commit
  reachable from the tracked branch. `agile.py lint` re-checks this for every
  `done` ticket and reports drift in `INDEX.md`.
- **The pointer bump and the `done` transition are the same commit.** That is
  what makes the log a ledger: every pointer move names the ticket that caused
  it, and `git show <bump>` displays both the new sha and the closed ticket.
- **Push the submodule before the super-repo.** A super-repo pointer to an
  unpushed sha is unclonable for everyone else.
- **Never `git add <submodule>` opportunistically.** If `git submodule status`
  shows a moved pointer outside a close, that is an error to report, not a
  change to commit.

## Recovering from a dirty state

```bash
git submodule status                       # + prefix = pointer moved, U = conflict
git -C <repo> status --short --branch
git submodule foreach 'git status --short --branch'
```

If a repository is on a stray branch with uncommitted work that belongs to
nobody's ticket, **stop and report it**. Do not stash, reset or force-checkout
another agent's working tree.
