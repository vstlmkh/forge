---
name: agile-artifacts
description: The rules for reading and writing tickets in the Markdown tracker — frontmatter schema, ID allocation, legal status transitions, and the compare-and-swap claim protocol that keeps parallel agents from stealing each other's work. Load this before touching any file under the tracker. Every role agent needs it.
---

# Working with tracker artifacts

`docs/agile/SCHEMA.md` is the specification. This skill is the operating manual:
what to run, in what order, and what will bite you.

## The one-paragraph model

Four artifact kinds live in the tracker: `epic` and `story` in `backlog/`
(planning containers, never implemented directly), `task` in `tasks/` and `bug`
in `bugs/` (units of work with a lifecycle, a branch and a PR). `INDEX.md` is a
board **generated** from their frontmatter. The generator, validator and ID
allocator is one script: `.claude/scripts/agile.py`.

## Commands you will actually run

```bash
python3 .claude/scripts/agile.py lint              # validate everything; exit 2 = issues
python3 .claude/scripts/agile.py index             # regenerate the board
python3 .claude/scripts/agile.py next-id task      # -> TASK-0009
python3 .claude/scripts/agile.py show TASK-0009    # -> JSON {path, frontmatter}
python3 .claude/scripts/agile.py spec new TASK-0009   # scaffold the ticket's spec
python3 .claude/scripts/agile.py spec show TASK-0009  # -> JSON {brief, questions, carryover}
python3 .claude/scripts/agile.py next-req TASK-0009   # -> REQ-0004
python3 .claude/scripts/agile.py gates             # the six gates and their contracts
python3 .claude/scripts/kb.py for-ticket TASK-0009 # the ticket's knowledge-base reading list
python3 .claude/scripts/kb.py lint                 # validate the knowledge base; exit 2 = issues
python3 .claude/scripts/forge.py scopes            # the legal scopes and who owns each
```

Run `lint` **before** you hand work back. An exit code of 2 with your ticket
named in the output means you are not done.

## The vocabulary is per-project

`scope`, the agent that may hold a scope, and the repository a scope lives in
all come from `forge.json`. Never assume the scopes of another project you have
seen; run `forge.py scopes`. Adding a scope is an edit to `forge.json` plus an
agent file — not a convention you can invent inside a ticket.

## The two fields that point at the knowledge base

Every task and bug carries them, and `lint` enforces both (SCHEMA §9,
invariants 14-15):

```yaml
docs:                    # the knowledge-base notes read at grooming, actualised at close
  - shared/api-contract/{api-contract} subscriptions endpoint - 2026-10-03.md
docs_waiver: null        # or NO-DOCS (<reason>), and then docs: must be empty
```

An entry may be a basename, a kb-relative path or a repo-relative path, as
long as it resolves unambiguously. `status in {review, verify, done}` requires
one of the two to be filled — a ticket that documented nothing and never said
why does not close. Load `project-knowledge` for what goes in a note and when.

## Never edit INDEX.md

Neither of them — the tracker's nor the knowledge base's. Both are regenerated
from their sources. A `PreToolUse` hook denies writes to them, and a `Stop` hook
regenerates both once per turn. If you find yourself wanting to edit the board,
edit the ticket instead. On a merge conflict in `INDEX.md`, take either side and
re-run `agile.py index`.

## Creating an artifact

1. `agile.py next-id <kind>` — never guess an ID, never reuse one.
2. Write `<tracker>/<folder>/<ID>-<kebab-slug>.md` with the full frontmatter
   block from `SCHEMA.md`. **Every field, including the null ones.** A missing
   field is a lint error, not a shortcut — and a new task or bug with no `docs:`
   or no `spec:` is refused outright by a `PreToolUse` hook, because those two
   fields are what make the consult step and the grilling step happen at all.
3. `created` and `updated` are today's date — get it from `date +%F`, do not
   assume.
4. `agile.py lint`, then commit:
   `chore(agile): opens STORY-014 with TASK-0231, TASK-0232`.

Only `pm` creates artifacts. The one exception is `qa`, which files bugs — and
`qa` must call `next-id bug` immediately before writing the file, with the write
as the last thing it does, so the window for an ID collision stays near zero.

## The claim protocol — a compare-and-swap, not a lock

**`qa` claims, not the engineer.** A ticket leaves `todo` into `speccing`, held
by `qa`, which grills it into a brief, writes the failing tests against that
brief in `writing_tests`, and only then hands the ticket to an engineer in
`in_progress`. An engineer never claims out of `todo`; by the time it sees a
ticket, the claim already exists, the brief is agreed and the branch already has
a red test commit on it.

There is no central lock file. The claim is a single `Edit` whose `old_string`
is the contiguous unclaimed block. Because `Edit` requires an exact match, a
racing second agent's edit **fails** — and that failure is the lock.

1. Read the ticket. Abort unless `status: todo`, `assignee: null`, and every
   `blocked_by` target is `done` or `cancelled`.
2. One `Edit`, `old_string` covering the whole contiguous block from `status:`
   through `claimed_at:`:

   ```
   status: todo
   parent: STORY-014
   scope: backend
   priority: P2
   assignee: null
   claimed_at: null
   ```

   `new_string` — same block with `status: speccing`, `assignee: qa`, and
   `date -u +%Y-%m-%dT%H:%M:%SZ`.
3. **If the Edit fails, you lost the race.** Do not retry, do not re-read and
   force it through. Report the loss and pick another ticket.
4. Commit immediately so the claim is published:
   `chore(agile): claims TASK-0231`.
5. Re-read the file and confirm your own name is in `assignee` before starting
   work.

`speccing -> writing_tests` is a second edit of the same block, by the same
agent — the claim does not change hands, the stage does.

The handover to the engineer is a third edit of the same block:
`writing_tests -> in_progress`, `assignee` to the engineer that owns the scope,
`claimed_at` refreshed. `branch` must already be filled in — the engineer
continues on `qa`'s branch rather than cutting its own.

Releasing a claim is the first edit in reverse: back to `todo`, assignee and
`claimed_at` to `null`, with a `## Log` line saying why.

## One working tree per repository

Each repository in `forge.json` has exactly one git checkout. Two agents cannot
be on two branches in the same one, no matter how cleanly their tickets claim.
`lint` enforces the consequence: **at most one task or bug per working tree may
be `writing_tests`, `in_progress` or `review`.** The test-writing stage holds the
tree just as firmly as implementation — `qa` is committing to a branch in it.

**`speccing` deliberately does not count.** It cuts no branch and writes nothing
outside the tracker, so the next ticket can be specified while this one is being
implemented. That is the one piece of real parallelism the cycle offers in a
monorepo, and it is not an oversight to be tidied away.

In a monorepo that means one ticket at a time, full stop. In a multi-repo
workspace it means one ticket per repository, so the real parallelism is one
agent per repository and nothing more. `forge.py repos` tells you which is which.

## Status transitions

The legal edges are in `SCHEMA.md` §5, along with who owns each one. Rules that
catch people out:

- **You may not close your own work.** An engineer stops at `review`. QA moves
  `review -> verify`, which means *awaiting the user's acceptance*. Only the
  orchestrator, inside `/agile:close`, sets `done`.
- **There is no `todo -> writing_tests` and no `todo -> in_progress`.** Every
  ticket is specified before it is tested and tested before it is implemented. A
  ticket too small to grill still passes through `speccing`, carrying
  `spec_waiver: NO-SPEC (<reason>)`; one whose requirements cannot be expressed
  as a test still passes through `writing_tests`, carrying `NO-TEST (<reason>)`.
  See `agile-dod`.
- **`writing_tests -> speccing`** is the honest move when the brief, rather than
  the test, turns out to be wrong. It keeps the claim and the spec file where
  `-> todo` would throw both away.
- **An engineer may hand a ticket back to `writing_tests`** when a test is
  genuinely wrong. That is a legitimate edge, and it is the only sanctioned
  alternative to editing `qa`'s tests — which is never allowed.
- **Every transition appends a `## Log` line** — `<ISO timestamp> <agent>: <what
  changed and why>`. The log is the audit trail; a status change without one is
  incomplete.
- **Bump `updated`** to today's date on every edit.

## Editing a ticket you have claimed

You may change: `status`, `branch`, `pr`, `spec`, `docs`, `docs_waiver`,
`## Log`, `## Root cause`, `## Implementation notes`, and tick
`## Acceptance criteria` boxes you have genuinely satisfied. Adding to `docs` is how you record a note
your own work produced — you extend that list, you do not clear what `pm` put
there. You may **not** change `id`, `type`, `parent`, `scope`, `priority`,
`severity`, or the acceptance criteria text itself. If the criteria are wrong or
the scope is bigger than stated, say so in `## Log` and hand it back to `pm` —
do not quietly redefine the ticket to match what you built.

## The spec is the contract

A task or bug carries `spec:` — either `specs/<ID>.md` or `null` with
`spec_waiver: NO-SPEC (<reason>)`. The file is **created by the script, never by
hand**, for the same reason a knowledge-base note is:

```bash
python3 .claude/scripts/agile.py spec new TASK-0231   # then set the spec: it prints
```

A `PreToolUse` hook denies a spec file that is not named after an existing
ticket, and `lint` reports an orphan spec as an error — a spec that outlived its
ticket is a document nobody will ever reconcile.

Inside it, requirement ids are allocated with `agile.py next-req <ID>`. They are
**per-ticket, never reused and never renumbered**, exactly like artifact ids: a
requirement that is dropped keeps its row with `Status: dropped`, so a REQ id
written into a test name or a commit message stays meaningful. The full
specification is `SCHEMA.md` §10.

Who may write what:

| | May write |
|---|---|
| `qa`, in `speccing` | the whole file |
| `qa`, later | nothing — a brief that moves after the tests were written is not a brief |
| `pm`, at gate 6 | the `Becomes` cell of a `## Carryover` row, and nothing else |
| anyone else | nothing |

**Gates 5 and 6 run at the same time, and that is only safe because their file
sets are disjoint.** At gate 5 `qa` writes the knowledge base and this ticket's
`## Log`; at gate 6 `pm` writes *other* tickets, the parent, and those carryover
cells. Neither touches the other's files, and `pm` in particular does not edit
the ticket under review.

## Frontmatter grammar

The parser is stdlib-only and deliberately limited: `key: scalar`,
`key: [a, b]`, and `key:` followed by indented `- item` lines. **No nested maps,
no `|` or `>` blocks, no anchors.** If you need structure, it belongs in the
body, not the frontmatter.
