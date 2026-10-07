---
name: agile-artifacts
description: Reading a ticket and editing one you already hold — the frontmatter grammar, which fields are yours to change, the legal status transitions, the one-working-tree rule, and the generated boards you must never edit. Load before touching any file under the tracker. Creating a ticket or claiming one out of `todo` is `agile-claims`, which only `pm` and `qa` need.
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
python3 .claude/scripts/agile.py show TASK-0009    # -> JSON {path, frontmatter}
python3 .claude/scripts/agile.py spec show TASK-0009  # -> JSON {brief, questions, carryover}
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

## Editing a ticket you have claimed

You may change: `status`, `branch`, `pr`, `spec`, `docs`, `docs_waiver`,
`## Log`, `## Root cause`, `## Implementation notes`, and tick
`## Acceptance criteria` boxes you have genuinely satisfied. Adding to `docs` is
how you record a note your own work produced — you extend that list, you do not
clear what `pm` put there. You may **not** change `id`, `type`, `parent`,
`scope`, `priority`, `severity`, or the acceptance criteria text itself. If the
criteria are wrong or the scope is bigger than stated, say so in `## Log` and
hand it back to `pm` — do not quietly redefine the ticket to match what you
built.

The spec is not yours either. `qa` writes it in `speccing` and nobody writes it
afterwards; the rules are in `agile-claims`.

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
  incomplete. It is also the *only* channel between gates: a dispatch payload
  carries the last few entries and nothing the orchestrator typed, so a finding
  you do not write down does not reach the next agent.
- **Bump `updated`** to today's date on every edit.

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

## Frontmatter grammar

The parser is stdlib-only and deliberately limited: `key: scalar`,
`key: [a, b]`, and `key:` followed by indented `- item` lines. **No nested maps,
no `|` or `>` blocks, no anchors.** If you need structure, it belongs in the
body, not the frontmatter.
