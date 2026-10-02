# Using the framework

The agentic development framework for this workspace: role agents, a backlog, a
task tracker and a bug tracker, all in git.

- **What the tickets look like** → [`SCHEMA.md`](SCHEMA.md)
- **What the board looks like right now** → [`INDEX.md`](INDEX.md) (generated)
- **How it is wired** → `.claude/agents/`, `.claude/skills/`, `.claude/commands/`
- **What this project's shape is** → `forge.json`, read it with
  `python3 .claude/scripts/forge.py scopes`

---

## The shape of it

```
docs/agile/
├── backlog/   EPIC-*.md, STORY-*.md    planning containers
├── tasks/     TASK-*.md                units of implementation work
├── bugs/      BUG-*.md                 defects
├── INDEX.md                            the board — GENERATED, never edited
├── SCHEMA.md                           the specification
└── README.md                           this file
```

Everything is a Markdown file with YAML frontmatter, committed to the
repository. There is no external tracker, no API key and no sync job. A ticket
review is a `git diff`. `.claude/scripts/agile.py` regenerates the board from the
tickets and validates them; a hook runs it after every turn, and a second hook
denies any attempt to hand-edit `INDEX.md`.

## The agents

| Agent | Owns | Never |
|---|---|---|
| `pm` | the tracker and the knowledge base — grooming, decomposition, priority, bug triage | writes application code |
| one engineer per code scope | that scope's repository | touches another scope, merges, closes |
| `qa` | the tests and the verdict — writes the failing tests first, then runs the checks, records evidence, files bugs | writes production code, edits its own tests during `review`, closes a ticket |

`python3 .claude/scripts/forge.py scopes` lists the engineers this project
actually has.

Merging a PR, recording the merge sha and setting a ticket to `done` belong to
**you** — the top-level session — inside `/agile:close`. No subagent does any of
the three. That single reserved step is what keeps the gate real.

## The commands

| Command | What it does |
|---|---|
| `/agile:groom <request>` | PM turns a raw request into epics, stories and single-scope tasks |
| `/agile:board` | regenerates the board, validates it, reports drift |
| `/agile:next` | picks the next eligible ticket and explains the choice |
| `/agile:work <ID>` | QA writes failing tests → engineer → QA reviews, stopping at `verify` |
| `/agile:verify <ID>` | runs the QA review gate on its own |
| `/agile:close <ID>` | merges, records the sha, closes — one commit |
| `/agile:bug <symptom>` | files a bug with a reproduction and triages it |
| `/kb:consult`, `/kb:new`, `/kb:audit`, `/kb:lint` | the knowledge base |
| `/forge:doctor` | checks that the harness config still matches the repo |

## A normal day

```
/agile:board                      what is going on
/agile:next                       what should I do
/agile:work TASK-0005             do it — ends at verify with a PR open
/agile:close TASK-0005            merge, record, close
```

Starting something new:

```
/agile:groom "show price per day on the plans page"
   → STORY-014 with TASK-0231 (backend) and TASK-0232 (frontend, blocked_by TASK-0231)
/agile:work TASK-0231 ; /agile:close TASK-0231
/agile:work TASK-0232 ; /agile:close TASK-0232
   → then PM rolls STORY-014 to done
```

Something is broken:

```
/agile:bug "onboarding returns 500 when the answer list is empty"
   → BUG-0042, triaged to a scope, S2, P1
/agile:work BUG-0042 ; /agile:close BUG-0042
```

You can also drive the agents directly — "have the backend engineer look at
TASK-0001" — the commands are the well-lit path, not a cage.

## The lifecycle

The cycle is test-first: `qa` writes the failing tests before anyone implements
anything, and judges the result against those same tests afterwards.

```
       pm            qa              engineer           qa           you
raw ──► todo ──► writing_tests ──► in_progress ──PR──► review ──► verify ──► done
                     ▲   red tests      │  ▲              │          │
                     └──test is wrong───┘  └───rejected────┴──────────┘
```

- **`writing_tests`** — `qa` claims the ticket, cuts the branch, writes a test
  per acceptance criterion, proves them red, and commits the tests alone.
- **`in_progress`** — the engineer continues on that branch and implements until
  the tests pass. It may not edit them; if a test is genuinely wrong it hands the
  ticket back to `writing_tests` and argues its case in `## Log`.
- **`review`** — `qa` runs its tests, diffs them against its red commit to prove
  they were not weakened, and checks the Definition of Done.
- **`verify`** — awaiting *your* acceptance. Nothing happens automatically here.

There is no `todo -> in_progress`: every ticket passes through `writing_tests`.
Where no automated test is possible — a value in `.env.example`, a linter config,
a workflow file — `qa` records a `NO-TEST (<reason>)` waiver naming the check
that will substitute for it, and that check becomes binding at the review gate.

A ticket that has not been through `qa` cannot reach `verify`, and a ticket that
is not in `verify` cannot be closed. Both rules are checked by the validator, not
just by convention.

## Three constraints worth knowing before you start

**A task has exactly one scope.** Anything touching two scopes is two tasks
under one story. A task carries one branch, one PR and one merge sha, and all
three become ambiguous the moment it spans two repositories.

**Parallelism is bounded by working trees.** Each repository in `forge.json` has
one git checkout, so the validator enforces at most one active ticket per
repository. In a monorepo that is one ticket at a time; in a multi-repo
workspace it is one agent per repository. There is no swarm.

**Claims are compare-and-swap, not locks.** An agent claims a ticket with a
single exact-match edit on the unclaimed frontmatter block. If another agent got
there first, the edit fails, and that failure *is* the lock. A failed claim means
pick another ticket — never force it through.

## What the gate can actually check today

```bash
python3 .claude/scripts/forge.py checks
```

That matrix is the authority, and it lives in `forge.json` so that flipping a
row is a reviewable diff. **An unavailable check is recorded as
`SKIPPED (<reason> — see TASK-000X)`, never as a pass.** When a bootstrap ticket
makes a check real, flipping its `available` flag is part of that ticket's own
acceptance criteria — so the gate tightens itself as the tooling lands.

## Ticket hygiene, in four rules

1. **Never edit `INDEX.md`.** Edit the ticket; the board regenerates. A hook will
   stop you anyway.
2. **Every status change appends a `## Log` line** — timestamp, agent, what
   changed and why. The log is the audit trail.
3. **Evidence, not assertions.** A ticked acceptance box needs a command and its
   output, or a file and a line, in `## Log`.
4. **Allocate IDs with the script.** `agile.py next-id task`. Never guess, never
   reuse.

## The scripts

```bash
python3 .claude/scripts/agile.py lint          # validate; exit 2 means issues
python3 .claude/scripts/agile.py index         # regenerate INDEX.md
python3 .claude/scripts/agile.py next-id task  # → TASK-0009
python3 .claude/scripts/agile.py show BUG-0001 # → JSON {path, frontmatter}
python3 .claude/scripts/kb.py lint             # the knowledge base
python3 .claude/scripts/forge.py doctor        # the harness itself
```

Stdlib-only Python 3, no dependencies. `index` is byte-stable — running it twice
leaves a zero diff, which is why it is safe to run after every turn. If
`INDEX.md` ever conflicts in a merge, take either side and re-run `index`.

## Extending it

- **A new check becomes available** → flip its row in `forge.json` under
  `checks.<scope>`. That is the one place QA reads.
- **A new scope** → add it to `forge.json` (`scopes`, `checks`, and a repository
  if it has one) and add `.claude/agents/<agent>.md`. `forge.py doctor` tells
  you what is still missing.
- **A new rule should be mechanically enforced** → add it to `validate()` in
  `.claude/scripts/agile.py` *and* to `SCHEMA.md` §6. A rule that lives only in
  prose will be broken.
- **A new field** → `SCHEMA.md`, the required-fields list in the script, and the
  templates in the skills. Keep it inside the restricted frontmatter grammar:
  flat keys and flat lists, nothing nested.

## What was deliberately left out

Sprints, story points, velocity and burndown charts — nothing here consumes them.
Archiving closed tickets — the board caps its "Recently done" list instead.
Automatic reclaiming of stale claims — the validator flags a claim older than the
configured window and leaves the decision to `pm`, because silently taking over
someone's half-finished branch is worse than a stale ticket. Git worktrees for
parallelism inside one repository — they interact badly with submodule pointers
and with bind-mounted containers.
