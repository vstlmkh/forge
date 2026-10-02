---
name: agile-grooming
description: How the PM turns a raw request into implementable tickets — decomposition into epics, stories and single-scope tasks, writing acceptance criteria an agent can actually satisfy, prioritising, and triaging bugs. Load before creating or refining anything in the tracker.
---

# Grooming

Turning "add price per day to the plans page" into tickets an agent can execute
without guessing. This is `pm` work.

## Before you write anything

**Consult the knowledge base, then read the code.** A ticket written without
looking at either will send an engineer down the wrong path, and the engineer
will follow it — that is the failure mode this step prevents.

```bash
python3 .claude/scripts/forge.py scopes             # the shape of this project
python3 .claude/scripts/kb.py find <keyword> [...]
python3 .claude/scripts/kb.py related "<basename>"  # one hop along the graph
cat docs/knowledge/INDEX.md                         # the coverage map
```

The knowledge base is where the business rules, integration behaviour,
architectural decisions and past incidents live. Load `project-knowledge` for the
procedure. Three things come out of the consult step and all three belong in the
ticket:

- the note basenames in `docs:`, so the engineer and `qa` read them too;
- the substance in `## Implementation notes` — the rule the change must obey,
  the endpoint shape already agreed, the incident this nearly repeats;
- an honest **gap**, when `find` returns nothing. Say so in
  `## Implementation notes` and expect the ticket to produce the missing note.

Where the knowledge base and the code disagree, the **code wins**. Say so in the
ticket rather than quietly picking one, and treat correcting the note as part of
the work.

- What do we already know? Name the notes in `docs:` and their substance in
  `## Implementation notes`.
- What already exists that solves part of this? Name the files in
  `## Implementation notes`.
- Which scopes are involved? That decides how many tasks you create.
- What is genuinely ambiguous? Ask the user **now**, in one batched set of
  questions. Do not encode a guess as a requirement; if you must proceed on an
  assumption, mark it `[ASSUMPTION]` in the ticket body so it is visible.

## Choosing the shape

| Situation | Shape |
|---|---|
| One change, one scope, under about a day | a single `task` under an existing epic |
| User-visible value spanning two scopes | a `story` with one task per scope |
| A theme that will produce several stories over weeks | an `epic` |
| A defect | a `bug` — not a task |

Do not create an epic for a single story, or a story for a single task. Empty
containers are noise on the board.

## The single-scope rule

> A task's `scope` is exactly one of the scopes in `forge.json`.

Anything touching two scopes is **two tasks under one story**, with the consumer
task `blocked_by` the producer one. This is not bureaucracy: a task carries one
branch, one PR and one merge sha, and every one of those becomes ambiguous the
moment a task spans two repositories.

When you split, say in each task's `## Implementation notes` what the contract
between them is — the endpoint shape, the field name, the response type — so the
two engineers do not have to negotiate through you.

## Acceptance criteria

The criteria are the contract, and under the test-first cycle they are also the
test plan: `qa` reads them in `writing_tests` and turns each one into a failing
test *before* an engineer starts. A criterion you cannot imagine a test calling
is a criterion `qa` will hand straight back to you.

An engineer satisfies them literally, and QA verifies them literally.

- **Observable.** Something you can point at: a response field, a rendered
  element, a command's exit code. Not "the code is clean".
- **Verifiable by a command where possible.** If a criterion can be a command,
  write the command.
- **Complete.** If it is not in the criteria, it will not be built. Error paths,
  empty states, and the migration/backfill question all need a line or an
  explicit sentence in `## Out of scope`.
- **Independent of implementation.** Say what must be true, not which class to
  create. Put implementation opinions in `## Implementation notes`, where they
  read as guidance rather than as a requirement.
- **Testable, one criterion at a time.** Write each so that a single test can
  make it fail. A criterion joining two behaviours with "and" becomes one test
  that cannot say which half broke — split it.
- **Honest about the untestable.** A ticket whose deliverable is a config value,
  a workflow file or a docs change has nothing for a test to call. Say so in
  `## Implementation notes`; `qa` will record a `NO-TEST` waiver naming a
  substitute check, and knowing that up front stops it inventing a hollow test.

Bad: `- [ ] Add price per day.`
Good: `- [ ] GET /api/subscriptions returns price_per_day on every plan, as a minor-unit integer, computed as price / billing_period_days and rounded half-up.`

## The documentation contract

Every task and bug carries `docs:` and `docs_waiver`. Fill them at grooming:

```yaml
docs:
  - shared/api-contract/{api-contract} subscriptions endpoint - 2026-10-03.md
  - backend/business-rule/{business-rule} subscription proration - 2026-10-03.md
docs_waiver: null
```

`docs:` is not a bibliography — it is the reading list you are handing the
engineer, and `qa` reads it too. List what genuinely bears on the work; a ticket
pointing at six notes points at none.

When the ticket cannot produce durable knowledge — a formatting sweep, a
dependency bump, a config value — write the honest waiver instead:

```yaml
docs: []
docs_waiver: NO-DOCS (config-only change; no rule, behaviour or decision established)
```

Invariant 15 in `SCHEMA.md` makes one of the two mandatory by `review`, and a
`PreToolUse` hook refuses a brand-new ticket that has no `docs:` field at all.
This is the same idiom as `NO-TEST` and `SKIPPED`: the framework does not demand
that everything be documented, it demands that a decision not to document be
visible and argued.

Then fill `## Verification` from `python3 .claude/scripts/forge.py checks
<scope>` — the exact commands for that scope, with `SKIPPED (see TASK-000X)`
written out for the checks that are not available yet. Do not invent a command
that is not in the matrix.

## Sizing

If a task cannot plausibly be finished and verified in one working session,
split it. Signals that it is too big: more than about six acceptance criteria,
a criterion containing "and also", or `## Implementation notes` describing a
sequence of stages. There are no story points here — the split is the estimate.

## Priority

| | Meaning |
|---|---|
| `P0` | Production is broken or losing data. Everything else stops. |
| `P1` | Blocks other work, or is a security or deploy-safety issue. |
| `P2` | Normal planned work. The default. |
| `P3` | Worth doing, nobody is waiting. |

Priority orders the **Ready** column on the board, so inflation directly costs
you the ability to steer. If everything is P1, `/agile:next` is a coin flip.

## Dependencies

Use `blocked_by` only for a hard ordering — B genuinely cannot start until A is
merged. A preference for doing A first is not a dependency; it is a priority.
`lint` rejects cycles and refuses to let a task be `writing_tests` or
`in_progress` while a dependency is open — writing tests against a moving
dependency wastes the same work twice.

## Bug triage

A bug arrives at `status: triage`. Triage means deciding four things and moving
it on:

1. **Reproduce it, or try.** No reproduction and no evidence →
   `cannot_reproduce` with your attempt recorded in `## Log`. Do not leave it
   sitting in triage.
2. **`scope`** — which scope owns the defect. If it is genuinely several, the
   bug stays `blocked`, and you create one task per scope with
   `parent: BUG-XXXX`, listing them in `spawned_tasks`. The bug closes only when
   they all do. This is the *only* bug-to-task conversion path.
3. **`severity`** — what is broken, independent of schedule:
   `S1` outage or data loss · `S2` a major flow is broken · `S3` degraded but
   usable · `S4` cosmetic.
4. **`priority`** — when we will fix it. Severity and priority are different
   axes; an S4 on the pricing page can outrank an S2 in an admin screen.

Then `triage -> todo`. An `S1` jumps the queue and may skip grooming entirely —
say so in `## Log`.

Fill `## Steps to reproduce`, `## Expected`, `## Actual` and `## Evidence`
before moving on. Search the knowledge base's `*/troubleshooting/` while you
triage — a defect that has happened before is already documented, with its root
cause and its detection command, and that note belongs in `docs:` before anyone
starts. Leave `## Root cause` empty; the engineer owns it and `lint` will refuse
to let the bug reach `review` without it.

## Rolling up

When every task under a story is `done`, move the story to `done`. When every
story under an epic is `done`, move the epic. `/agile:board` surfaces the
candidates in the backlog tree. Nothing does this automatically — it is a
judgement call about whether the story's own acceptance criteria are actually
met, not just its children's.

## Finishing

```bash
python3 .claude/scripts/agile.py lint
python3 .claude/scripts/kb.py lint
git add docs && git commit -m "chore(agile): opens STORY-014 with TASK-0231, TASK-0232"
```

Then tell the user what you created and what you assumed — in two or three
lines, with the IDs. They should not have to open the board to find out what
just happened.
