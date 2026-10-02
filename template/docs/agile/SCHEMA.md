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
status: todo             # todo | writing_tests | in_progress | review | verify | done | blocked | cancelled
parent: STORY-014        # STORY-* | EPIC-* | BUG-* — never null
scope: backend           # EXACTLY ONE scope from forge.json
priority: P2
assignee: null           # null | pm | qa | the agent that owns the scope
                         # qa holds it in writing_tests, review and verify
claimed_at: null         # ISO-8601 UTC, e.g. 2026-10-03T11:22:03Z
branch: null             # feat/add-price-per-day
pr: null                 # https://github.com/<owner>/<repo>/pull/91
merge_sha: null          # merge sha on the scope's tracked branch, set at close
blocked_by: []           # [TASK-0230]
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
todo          -> writing_tests | blocked | cancelled
writing_tests -> in_progress | todo | blocked | cancelled   (todo releases the claim)
in_progress   -> review | writing_tests | blocked | todo    (writing_tests = the tests are wrong)
review        -> verify | in_progress                       (in_progress = changes requested)
verify        -> done | in_progress                         (in_progress = the user rejected it)
blocked       -> todo | cancelled
done          -> in_progress                                (reopen only; requires a Log entry)
cancelled     -> todo
```

**There is no `todo -> in_progress`.** Every ticket passes through
`writing_tests` — that is what makes the cycle test-first rather than
test-eventually. A ticket whose acceptance criteria genuinely cannot be
expressed as an automated test still passes through the stage: `qa` records a
`NO-TEST (<reason>)` waiver in `## Log` and moves it straight on. See
`agile-dod`.

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
| `todo -> writing_tests`, `writing_tests -> in_progress` | `qa` |
| `in_progress -> review`, `in_progress -> writing_tests` (the tests are wrong) | the agent that owns that scope |
| `review -> verify`, `review -> in_progress` (rejection) | `qa` |
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
4. `status in {writing_tests, in_progress, review, verify}` ⟹ `assignee` and `claimed_at` are set.
5. `status in {in_progress, review, verify}` ⟹ `branch` is set — `qa` cuts the branch in `writing_tests` and the engineer continues on it. `status in {review, verify}` ⟹ `pr` is set too (unless the project set `git.pull_requests: false`).
6. `status == done` and the scope has a repository ⟹ `merge_sha` is set, is a valid sha, and is reachable from that repository's tracked branch.
7. `assignee` matches `scope`: only an agent listed for that scope in `forge.json` may hold it. `qa` may hold an artifact only in `writing_tests`, `review` or `verify`, and `writing_tests` may be held by nobody else.
8. Every `parent`, `blocked_by`, `regression_of` and `spawned_tasks` entry resolves to an existing artifact. `blocked_by` is acyclic.
9. A task may not be `writing_tests` or `in_progress` while any `blocked_by` target is unfinished — writing tests against a moving dependency wastes the same work twice.
10. A bug in `review`/`verify` has a filled `## Root cause`. A section whose only content is an italic placeholder (`_to be filled_`), `TBD`, `TODO`, `N/A` or a bare bullet counts as **empty** — write the real answer or leave the heading bare. `wontfix`/`cannot_reproduce` require a `## Log` justification.
11. A bug with `spawned_tasks` cannot be `done` until all of them are.
12. **One working tree per repository:** at most one task/bug may be in `writing_tests`, `in_progress` or `review` among all scopes that share a repository. The test-writing stage holds the tree just as firmly as implementation does — `qa` is committing to a branch in it.
13. A claim older than `policy.stale_claim_hours` (default 24h) is reported as a `WARN` (stale). No automatic reclaim — `pm` decides.
14. Every entry in `docs` resolves to a note under the knowledge base — by basename, by kb-relative path or by repo-relative path, and unambiguously. `docs_waiver`, when set, matches `NO-DOCS (<reason>)` exactly, and never coexists with a non-empty `docs`.
15. `status in {review, verify, done}` ⟹ `docs` is non-empty **or** `docs_waiver` is set. The knowledge base is consulted at grooming and actualised at close; a ticket that reaches review having recorded neither has skipped that gate, and the waiver is what makes skipping it an explicit, reviewable claim rather than an omission. See §9.

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
