# Tracker schema

The authoritative specification of every artifact under `docs/agile/`.
`.claude/scripts/agile.py lint` enforces the mechanical half of this document;
the prose half is enforced by the agents' skills. If the two ever disagree, the
script wins and this file is the bug.

The project-specific vocabulary — which scopes exist, which agent owns each one,
which repository it lives in — is **not** in this file. It is in `forge.json`:

```bash
python3 .claude/scripts/forge.py scopes
python3 .claude/scripts/forge.py repos
python3 .claude/scripts/forge.py checks <scope>
```

## 1. Artifact kinds

| Kind | Folder | ID | Purpose |
|---|---|---|---|
| `epic` | `backlog/` | `EPIC-001` | A theme. Groups stories. Never implemented directly. |
| `story` | `backlog/` | `STORY-014` | User-visible value. Groups tasks. Never implemented directly. |
| `task` | `tasks/` | `TASK-0231` | A unit of implementation work. Exactly one scope. |
| `bug` | `bugs/` | `BUG-0042` | A defect. Implemented directly, like a task. |

IDs are monotonic per kind, zero-padded (3 digits for epic/story, 4 for
task/bug), **never reused and never renumbered**. The filesystem is the ID
registry; allocate with:

```bash
python3 .claude/scripts/agile.py next-id task
```

Filename: `<ID>-<kebab-slug>.md`, e.g. `TASK-0231-add-price-per-day-field.md`.

## 2. Frontmatter grammar (restricted on purpose)

The parser in `agile.py` is stdlib-only. Only these three forms are legal:

```yaml
key: scalar
key: [a, b]
key:
  - a
  - b
```

Plus full-line `#` comments. **Nested maps, multiline scalars (`|`, `>`),
anchors and aliases are forbidden.** `null` and an empty value both mean null.
Every field below fits the grammar; do not add one that does not.

## 3. Fields

### 3.1 Epic and story

```yaml
---
id: STORY-014
type: story              # epic | story
title: Show price-per-day on subscription plans
status: groomed          # draft | groomed | in_progress | done | cancelled
parent: EPIC-003         # the epic for a story; null for an epic
priority: P2             # P0 | P1 | P2 | P3
scope: [backend, frontend]   # informational rollup; the tasks carry the real scope
labels: [billing]
created: 2026-10-03
updated: 2026-10-03
---
```

Body sections: `## Why`, `## Acceptance criteria`, `## Out of scope`, `## Notes`.

### 3.2 Task

```yaml
---
id: TASK-0231
type: task
title: Add price_per_day to the subscription resource
status: todo             # todo | speccing | writing_tests | in_progress | review | verify | done | blocked | cancelled
parent: STORY-014        # STORY-* | EPIC-* | BUG-* — never null
scope: backend           # EXACTLY ONE scope from forge.json
priority: P2
assignee: null           # null | pm | qa | the agent that owns the scope
                         # qa holds it in speccing, writing_tests, review and verify
claimed_at: null         # ISO-8601 UTC, e.g. 2026-10-03T11:22:03Z
branch: null             # feat/add-price-per-day
pr: null                 # https://github.com/<owner>/<repo>/pull/91
merge_sha: null          # merge sha on the scope's tracked branch, set at close
blocked_by: []           # [TASK-0230]
spec: null               # null | specs/TASK-0231.md - the agreed brief, see §10
spec_waiver: null        # null | NO-SPEC (<reason>) - only when spec: is null
docs:                    # knowledge-base notes read at grooming and actualised at close
  - backend/business-rule/{business-rule} subscription proration - 2026-10-03.md
docs_waiver: null        # null | NO-DOCS (<reason>) - only when docs: is empty
labels: [billing]
created: 2026-10-03
updated: 2026-10-03
---
```

Body sections: `## Goal`, `## Acceptance criteria`, `## Implementation notes`,
`## Verification`, `## Log`.

Each acceptance criterion of a specified ticket carries the requirement it
comes from: `- [ ] (REQ-0002) the response includes price_per_day`. That tag is
what lets `qa` write one test per requirement and produce one evidence line per
requirement, and `lint` checks it — see §10.

### 3.3 Bug

Everything a task has, plus:

```yaml
status: triage           # + triage | wontfix | cannot_reproduce
severity: S2             # S1 outage/data loss | S2 major broken | S3 degraded | S4 cosmetic
found_in: 4f01aca        # a sha, or an environment name (prod / dev)
reported_by: qa          # qa | user | <agent name>
regression_of: null      # TASK-0198, if known
spawned_tasks: []        # [TASK-0240] — only when the fix spans several scopes
```

Body sections: `## Steps to reproduce`, `## Expected`, `## Actual`,
`## Evidence`, `## Root cause`, `## Verification`, `## Log`.

## 4. The single-scope rule

> `scope` on a task or bug is **exactly one** value. Anything that touches two
> scopes is two tasks under one story.

This is what keeps `branch`, `pr`, `merge_sha` and the claim single-valued.
`agile.py lint` rejects a list-valued `scope` on a task or bug.

## 5. Status transitions

Any transition not listed is illegal. Every transition must be accompanied by an
appended line in `## Log`.

**Epic / story**

```
draft       -> groomed | cancelled
groomed     -> in_progress | draft | cancelled
in_progress -> done | groomed | cancelled
done        -> in_progress        (reopen only)
cancelled   -> draft              (revive only)
```

**Task**

```
todo          -> speccing | blocked | cancelled
speccing      -> writing_tests | todo | blocked | cancelled (todo releases the claim)
writing_tests -> in_progress | speccing | todo | blocked | cancelled
in_progress   -> review | writing_tests | blocked | todo    (writing_tests = the tests are wrong)
review        -> verify | in_progress                       (in_progress = changes requested)
verify        -> done | in_progress                         (in_progress = the user rejected it)
blocked       -> todo | cancelled
done          -> in_progress                                (reopen only; requires a Log entry)
cancelled     -> todo
```

**There is no `todo -> writing_tests` and no `todo -> in_progress`.** Every
ticket is specified before it is tested and tested before it is implemented.
`speccing` is where `qa` turns the request into a numbered brief, asking the
user through the top-level session rather than guessing (§10); `writing_tests`
is where that brief becomes executable. A ticket too small to grill carries
`spec_waiver: NO-SPEC (<reason>)`; one whose criteria genuinely cannot be
automated carries `NO-TEST (<reason>)` in `## Log`. Both still pass through the
stage, because a waiver is a claim somebody can disagree with and a skipped
stage is not. See `agile-dod`.

`writing_tests -> speccing` is the honest route when the brief, rather than the
test, turns out to be wrong: it keeps the claim and the spec file, where
`-> todo` would throw both away.

A project upgrading into the spec gate mid-ticket sets `policy.spec_first:
false` in `forge.json`; that restores `todo -> writing_tests` and downgrades
the spec invariants to warnings until the board has drained.

**Bug** — the task graph plus:

```
triage             -> todo | wontfix | cannot_reproduce | blocked
wontfix            -> triage
cannot_reproduce   -> triage
```

Who may perform which transition:

| Transition | Owner |
|---|---|
| create, `draft -> groomed`, `triage -> todo`, priority/severity | `pm` |
| `todo -> speccing`, `speccing -> writing_tests`, `writing_tests -> in_progress` | `qa` |
| `in_progress -> review`, `in_progress -> writing_tests` (the tests are wrong) | the agent that owns that scope |
| `review -> verify`, `review -> in_progress` (rejection) | `qa` |
| filing the carryover tickets at gate 6, while the ticket sits in `review` | `pm` — it creates other artifacts and transitions none |
| `verify -> done` | the orchestrator, in `/agile:close` only |
| `verify -> in_progress` | the user, on rejecting the work |
| `-> blocked`, `-> cancelled`, `-> wontfix`, `-> cannot_reproduce` | `pm` |

`verify` means **awaiting the user's acceptance**: `qa` has confirmed the tests
it wrote now pass and the Definition of Done is met, and nothing further happens
automatically. `assignee` stays `qa` there — it records who last held the ticket,
not who is expected to act.

## 6. Field invariants (enforced by `agile.py lint`)

1. `id` is unique, matches its kind's prefix and padding, and the filename starts with it.
2. `type` matches the folder (`epic`/`story` → `backlog/`, `task` → `tasks/`, `bug` → `bugs/`).
3. An epic has `parent: null`; a story's parent is an epic; a task/bug's parent is a story, epic or bug.
4. `status in {speccing, writing_tests, in_progress, review, verify}` ⟹ `assignee` and `claimed_at` are set.
5. `status in {in_progress, review, verify}` ⟹ `branch` is set — `qa` cuts the branch in `writing_tests` and the engineer continues on it. `status in {review, verify}` ⟹ `pr` is set too (unless the project set `git.pull_requests: false`).
6. `status == done` and the scope has a repository ⟹ `merge_sha` is set, is a valid sha, and is reachable from that repository's tracked branch.
7. `assignee` matches `scope`: only an agent listed for that scope in `forge.json` may hold it. `qa` may hold an artifact only in `speccing`, `writing_tests`, `review` or `verify`, and `speccing` and `writing_tests` may be held by nobody else.
8. Every `parent`, `blocked_by`, `regression_of` and `spawned_tasks` entry resolves to an existing artifact. `blocked_by` is acyclic.
9. A task may not be `writing_tests` or `in_progress` while any `blocked_by` target is unfinished — writing tests against a moving dependency wastes the same work twice. `speccing` is exempt and reported as a `WARN` instead: settling a brief while a dependency moves is cheap, and often the fastest way to find out what the dependency has to settle.
10. A bug in `review`/`verify` has a filled `## Root cause`. A section whose only content is an italic placeholder (`_to be filled_`), `TBD`, `TODO`, `N/A` or a bare bullet counts as **empty** — write the real answer or leave the heading bare. `wontfix`/`cannot_reproduce` require a `## Log` justification.
11. A bug with `spawned_tasks` cannot be `done` until all of them are.
12. **One working tree per repository:** at most one task/bug may be in `writing_tests`, `in_progress` or `review` among all scopes that share a repository. The test-writing stage holds the tree just as firmly as implementation does — `qa` is committing to a branch in it. **`speccing` deliberately does not count**: it cuts no branch and writes nothing outside the tracker, so the next ticket can be specified while this one is being implemented. Do not "tighten" this — the pipelining is the point, and this invariant is about git checkouts, not about attention.
13. A claim older than `policy.stale_claim_hours` (default 24h) is reported as a `WARN` (stale). No automatic reclaim — `pm` decides.
14. Every entry in `docs` resolves to a note under the knowledge base — by basename, by kb-relative path or by repo-relative path, and unambiguously. `docs_waiver`, when set, matches `NO-DOCS (<reason>)` exactly, and never coexists with a non-empty `docs`.
15. `status in {review, verify, done}` ⟹ `docs` is non-empty **or** `docs_waiver` is set. The knowledge base is consulted at grooming and actualised at close; a ticket that reaches review having recorded neither has skipped that gate, and the waiver is what makes skipping it an explicit, reviewable claim rather than an omission. See §9.

16. `status in {writing_tests, in_progress, review, verify}` ⟹ `spec` names an existing spec file whose own `status:` is `agreed`, **or** `spec_waiver` reads `NO-SPEC (<reason>)`. The two never coexist. When `policy.spec_first` is false these are `WARN`s and a single summary `WARN` names the tickets that would otherwise fail.
17. `spec`, when set, is exactly `specs/<ID>.md`. The field exists so that "this ticket has no spec" can be said out loud; it is not a choice of layout.
18. Every spec file names an existing task or bug, and that ticket's `spec:` names it back — the same two-way link as `docs:`/`tickets:` in §9. An orphan spec is an error: it outlived a ticket that was renamed or deleted.
19. Every requirement in a spec's `## Brief` that is `agreed` or `assumed` appears in the ticket's `## Acceptance criteria`, tagged `(REQ-NNNN)`. A brief nothing downstream mentions is decoration.
20. The spec's own rules — sections, requirement ids, the carryover contract — are in §10 and are enforced against the spec's path, not the ticket's.

## 7. INDEX.md

Generated. Never edited by hand — a `PreToolUse` hook denies writes to it, and a
`Stop` hook regenerates it once per turn. On a merge conflict, take either side
and re-run `python3 .claude/scripts/agile.py index`.

## 8. `agile.py` contract

| Command | Writes | Stdout | Exit |
|---|---|---|---|
| `index` | `docs/agile/INDEX.md` only | one-line counts summary | 0 clean · 2 issues found (index still written) · 1 fatal |
| `lint` | nothing | `PATH:FIELD: LEVEL: MESSAGE` per issue | 0 clean · 2 issues · 1 fatal |
| `next-id <kind>` | nothing | the next id, e.g. `TASK-0232` | 0 · 1 bad argument |
| `show <ID>` | nothing | JSON `{path, frontmatter}` | 0 · 1 not found |
| `spec new <ID>` | `docs/agile/specs/<ID>.md` | the path, then (on stderr) the `spec:` edit to make | 0 · 1 no such ticket · 3 the spec already exists |
| `spec show <ID>` | nothing | JSON `{path, frontmatter, brief, questions, carryover}` | 0 · 1 not found |
| `spec check <ID>` | nothing | `PATH:FIELD: LEVEL: MESSAGE` for that spec | 0 clean · 2 issues · 1 not found |
| `next-req <ID>` | nothing | the next free requirement id, e.g. `REQ-0005` | 0 · 1 no spec |
| `gates [N]` | nothing | the gate contract(s) | 0 · 1 no such gate |
| `handoff <ID> --gate <N>` | nothing | the dispatch payload for that gate | 0 · 2 the ticket cannot legally reach that gate (payload still printed, headed `BLOCKED`) · 1 bad argument |

`spec new` writes the file and then prints the edit to make on the ticket
rather than making it. `agile.py` has never written a ticket and must not
start: the claim is a compare-and-swap `Edit`, and a script rewriting
frontmatter behind an agent's back breaks it.

`index` is byte-stable: running it twice with no data change leaves a zero diff.
The repo root is found by walking up for `forge.json`; override with `--root`.

## 9. The tie to the knowledge base

`docs/agile/` records what we are doing; `docs/knowledge/` records what we know.
The link between them is two fields, and it is checked in both directions.

| Direction | Field | Meaning |
|---|---|---|
| ticket → note | `docs` on a task or bug | the notes read at grooming and actualised at close |
| note → ticket | `tickets` in the note's frontmatter | the tickets that **produced or last confirmed** the note |

The asymmetry is deliberate. A ticket may legitimately *read* a note without
touching it, so `docs` listing a note that does not list the ticket back is
normal — `kb.py for-ticket <ID>` reports it as *read but not claimed*, not as
an error. The reverse, a note claiming a ticket that never listed it, means
somebody documented work outside the cycle; that is worth a look.

Notes are specified in [`../knowledge/README.md`](../knowledge/README.md) and
validated by `.claude/scripts/kb.py`, which shares this file's frontmatter
parser. The procedure the agents follow is
`.claude/skills/project-knowledge/SKILL.md`.

| Command | Writes | Stdout | Exit |
|---|---|---|---|
| `kb.py index` | `docs/knowledge/INDEX.md` only | one-line counts summary | 0 clean · 2 issues · 1 fatal |
| `kb.py lint` | nothing | `PATH:FIELD: LEVEL: MESSAGE` per issue | 0 clean · 2 issues · 1 fatal |
| `kb.py new <type> <scope> "<description>"` | one note | the path it created | 0 · 1 bad argument |
| `kb.py find <kw>...` | nothing | matching notes, one per line | 0 hits · 2 no match · 1 bad argument |
| `kb.py for-ticket <ID>` | nothing | the ticket's notes and its backrefs | 0 · 2 unresolvable entry |
| `kb.py show`/`related`/`types` | nothing | JSON / the graph / the vocabulary | 0 · 1 not found |

## 10. The spec artifact

A ticket says what to do. Its spec says what "done" means, in numbered
requirements that the tests, the evidence and the carryover tickets all point
back at. It lives at `docs/agile/specs/<TICKET-ID>.md`, is created by
`agile.py spec new` and never by hand, and is written by `qa` at gate 1 — see
`agile-dod` and `agile.py gates`.

### 10.1 Frontmatter

```yaml
---
id: TASK-0231
type: spec
ticket: TASK-0231        # always equal to id; the back-link lint checks
status: drafting         # drafting | questions | agreed | superseded
created: 2026-10-05
updated: 2026-10-05
---
```

`status` is the gate's exit condition made checkable. `questions` means the
batch in `## Questions` is waiting on the user; `agreed` means every one of
them has a real answer. Nothing may reach `writing_tests` against a spec that
is not `agreed`.

### 10.2 Sections

| Section | Holds | Shape |
|---|---|---|
| `## Brief` | the requirements | `\| ID \| Requirement \| Status \| Source \|` |
| `## Questions` | what the repository could not answer | `\| Q \| Blocks \| Question \| Answer \|` |
| `## Carryover` | what was deliberately deferred | `\| ID \| Deferred because \| Becomes \|` |
| `## Spec` | behaviour, boundaries, contracts | prose, written against the REQ ids |
| `## Plan` | gates 2–6 instantiated | `\| Gate \| Owner \| Artifact \| Exit \|` |

A requirement id is `REQ-` plus four digits, allocated with
`agile.py next-req <ID>`, unique within the spec, **never reused and never
renumbered**. A requirement that is dropped keeps its row with
`Status: dropped`, so a REQ id written into a test name or a commit message
stays meaningful for as long as the repository does.

`Status` is one of `agreed` (the user said so), `assumed` (qa had to decide,
and nobody confirmed it), `question` (still open), `deferred` (carried over) or
`dropped`. `Source` records where the requirement came from: `user`, `kb:<note
basename>`, `code:<path:line>`, or `ticket`.

**`assumed` is not a quiet synonym for `agreed`.** It is the audit trail for
the one real weakness of this design — that `qa` both writes the brief and
judges the result against it. An `assumed` row that survives past `speccing` is
reported as a `WARN` and is an explicit talking point at gate 4.

### 10.3 Rules enforced against the spec's own path

1. It parses; `type: spec`; `id == ticket`; the filename is `<ticket>.md`; the ticket exists and points back.
2. All five sections are present.
3. `## Brief` holds at least one real requirement row — a table header is not content.
4. Every requirement id matches `REQ-NNNN` and is unique in the file.
5. Every `Status` cell is one of the five values above.
6. `status: agreed` ⟹ no `question` row and no unanswered row in `## Questions`.
7. A `deferred` requirement appears in `## Carryover`, and every carried row is `deferred` in the brief — the two are one list seen from two sides.
8. At `verify`, every carryover row names a resolvable ticket id or reads `NO-TICKET (<reason>)`. That is gate 6's machine check.
9. An `assumed` requirement past `speccing` is a `WARN`.
10. `status: agreed` ⟹ `## Plan` names G2 through G6.

Rules 1–10 are implemented in `validate_specs()` in
`.claude/scripts/agile.py`. When the script and this section disagree, the
script wins and this section is the bug.
