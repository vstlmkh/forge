---
name: agile-claims
description: Creating tracker artifacts and taking hold of one — ID allocation, the full frontmatter block, the compare-and-swap claim protocol that keeps parallel agents from stealing each other's work, and who may write which part of a spec. Load this only if you create tickets or claim them: `pm` and `qa` do, an engineer never does. Editing a ticket you already hold is `agile-artifacts`.
---

# Creating and claiming

`agile-artifacts` covers reading a ticket and editing one you already hold —
every agent needs that. This covers the two things only `pm` and `qa` do: making
an artifact exist, and taking hold of one. An engineer is *handed* its ticket,
already claimed, already specified, with failing tests already on the branch, so
none of this binds it and none of it is worth its context.

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

There is no central lock file, and `agile.py` does not do this for you — it has
never written a ticket, deliberately. The claim is a single `Edit` whose
`old_string` is the contiguous unclaimed block. Because `Edit` requires an exact
match, a racing second agent's edit **fails** — and that failure is the lock. A
script rewriting the same frontmatter would have to invent a lock to replace it.

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

## The spec is the contract

A task or bug carries `spec:` — either `specs/<ID>.md` or `null` with
`spec_waiver: NO-SPEC (<reason>)`. The file is **created by the script, never by
hand**, for the same reason a knowledge-base note is:

```bash
python3 .claude/scripts/agile.py spec new TASK-0231    # then set the spec: it prints
python3 .claude/scripts/agile.py next-req TASK-0231    # -> REQ-0004
```

A `PreToolUse` hook denies a spec file that is not named after an existing
ticket, and `lint` reports an orphan spec as an error — a spec that outlived its
ticket is a document nobody will ever reconcile.

Requirement ids are **per-ticket, never reused and never renumbered**, exactly
like artifact ids: a requirement that is dropped keeps its row with
`Status: dropped`, so a REQ id written into a test name or a commit message
stays meaningful. The full specification is `SCHEMA.md` §10.

The one part of a spec written from outside the subagent that owns the gate is
the `## Questions` table, and it is written by a command rather than by hand:

```bash
python3 .claude/scripts/agile.py spec answer TASK-0231 Q1="<what the user said>"
```

The orchestrator runs it the moment the user answers. Those words are the only
thing in the cycle the repository cannot reconstruct, and a relayed copy of them
lives exactly as long as one context window.

Who may write what:

| | May write |
|---|---|
| `qa`, in `speccing` | the whole file |
| the orchestrator, at any time | `## Questions` answers, via `spec answer` |
| `qa`, later | nothing — a brief that moves after the tests were written is not a brief |
| `pm`, at gate 6 | the `Becomes` cell of a `## Carryover` row, and nothing else |
| anyone else | nothing |

**Gates 5 and 6 run at the same time, and that is only safe because their file
sets are disjoint.** At gate 5 `qa` writes the knowledge base and this ticket's
`## Log`; at gate 6 `pm` writes *other* tickets, the parent, and those carryover
cells. Neither touches the other's files, and `pm` in particular does not edit
the ticket under review.
