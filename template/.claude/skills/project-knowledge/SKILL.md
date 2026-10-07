---
name: project-knowledge
description: How the agents use the project knowledge base — consulting it before work starts, filing what a task revealed, actualising notes at close, and keeping the graph linked. Load before grooming a ticket, before changing business logic, integrations, domain workflows or architecture, and before closing anything. The convention itself is docs/knowledge/README.md.
---

# The project knowledge base

> **A rule about how to work here is not a note.** "The load balancer drops an
> instance that answers anything but 200" is true of the system and belongs
> here. "Run every available check before asking for review" is true of working
> on it and belongs in the lessons layer — `agile-lessons`, and
> `docs/lessons/README.md`. Filing the second kind here hides it from everyone
> who searches the knowledge base.

The tracker is what we are doing. The knowledge base is what we know. This skill
is the procedure; `docs/knowledge/README.md` is the specification — the eight
types, the filename grammar, the frontmatter and the required sections. Read it
once, then work from here.

Four capabilities, in the order the cycle uses them: **consult**, **file**,
**actualise**, **audit**.

> **The code is the ultimate source of truth.** A note that disagrees with the
> code is stale. Trust the code, say so out loud, and fix the note as part of
> whatever task found the discrepancy — never leave both versions standing.

## The obligation, in one line per role

| Role | When | What |
|---|---|---|
| `pm` | grooming, before writing a ticket | **consult**; cite the notes in `## Implementation notes` and list them in `docs:` |
| `qa` | `writing_tests` | read the ticket's `docs:`; a note that contradicts an acceptance criterion is a question for `pm`, not a test |
| engineer | `in_progress` | read the ticket's `docs:` first; **file** what the work revealed before asking for review |
| `qa` | `review` | check the notes exist, are correctly typed, and say what the work actually established |
| orchestrator | `/agile:close` | **actualise**: bump `updated:`, add the ticket to `tickets:`, fix what the work disproved |

## Capability: consult

Mandatory before implementing a feature, fixing a bug, or changing business
logic, integrations, domain workflows or architecture. Optional for formatting,
dependency bumps, typos and test-only changes.

```bash
python3 .claude/scripts/kb.py find <keyword> [<keyword> ...]   # AND across keywords
python3 .claude/scripts/kb.py for-ticket TASK-0231             # what this ticket is bound to
python3 .claude/scripts/kb.py related "<basename>"             # walk the graph one hop
grep -ri "<term>" docs/knowledge/                              # when you want the raw hits
```

1. Name the domains the work touches — billing, auth, deploy, a given service.
2. `find` each. `find` exits 2 when nothing matches: **that is a gap, not an
   answer.** Say so, and expect to file a note at the end.
3. Read the hits, then follow their `## Related` one hop. The graph exists so
   that finding one relevant note finds the rest; use it instead of running six
   more searches.
4. Carry what you learned into the ticket: the note basenames in `docs:`, and
   the substance in `## Implementation notes` — an engineer reads the ticket,
   not your search history.

## Capability: file

After work reveals durable knowledge. Never write the file by hand — the
skeleton, the path and the frontmatter come out right from:

```bash
python3 .claude/scripts/kb.py new <type> <scope> "<description>" \
  --ticket TASK-0231 --title "The finding as a sentence"
```

`<scope>` may be a knowledge-base scope or the ticket's own scope — the script
maps one to the other. `kb.py types` prints the vocabulary this project uses.

1. **Decompose the task into findings.** One task commonly yields two or three:
   a rule, an external-system quirk, and a fix. List them before you write
   anything.
2. **Classify each one.** `business-rule` for a rule the code must obey,
   `troubleshooting` for an incident and its cause, `integration` for how an
   external system really behaves, `api-contract` for a promise across a
   boundary, `decision` for a choice with rejected alternatives, `runbook` for a
   procedure, `data-model` for entities and invariants, `overview` for a
   structural map. **`overview` is not the default** — a note that could be
   anything is an `overview` note that will be read by nobody.
3. **One finding, one note.** Three findings in one note are three notes nobody
   can find.
4. **Prefer updating an existing note** to creating a near-duplicate. `find`
   first; the script refuses an exact filename collision but cannot spot a
   paraphrase.
5. Fill every required section. The skeleton ships with italic hints, and
   `kb.py lint` treats a leftover hint as an empty section — the note is red
   until it says something, by the same logic as a test that has never failed.
6. **Cross-link both ways.** Add the link and its reason to your note's
   `## Related`, and the matching line to the note you linked. `lint` warns on a
   one-sided edge, and warns again if a note ends up connected to nothing.
7. List the note in the ticket's `docs:` and run `kb.py lint`.

### When there is genuinely nothing to file

Some work leaves no durable knowledge: a formatting sweep, a dependency bump, a
typo. Say so, on the ticket, in the same shape as a `NO-TEST` waiver:

```yaml
docs: []
docs_waiver: NO-DOCS (mechanical rename across 40 call sites; no rule, no
  behaviour and no decision was established)
```

The waiver must say **why the work was knowledge-free**, not that you were busy.
"No time to document" is not a waiver; it is the gap the waiver is meant to make
visible. A ticket that changed behaviour, fixed a defect, or chose between
approaches has something to file — reach for the waiver only when the honest
answer to "what would a future agent need to know?" is nothing.

## Capability: actualise

Closing a ticket is where the knowledge base either stays true or starts
rotting. For every note in the ticket's `docs:`:

1. Re-read it against what the work actually established. Correct anything the
   work disproved — that is the point of the step, not a bonus.
2. Add the ticket to `tickets:` **if this work produced or confirmed the note.**
   A note you only read stays untouched; `tickets:` records authorship and
   confirmation, not readership.
3. Bump `updated:` to today. Never touch `created:` or the date in the filename
   — age is information.
4. Keep `## Related` current: the work may have created an edge that did not
   exist before.
5. A note the work has made wrong is **superseded, not deleted**:
   `status: superseded`, `superseded_by: <new basename>`, and the file stays.
   Rename with `git mv` and fix every inbound `[[wikilink]]`
   (`grep -rl <old-basename> docs/knowledge/`) — the file itself is the graph.

```bash
python3 .claude/scripts/kb.py lint && python3 .claude/scripts/agile.py lint
```

## Capability: audit

On demand (`/kb:audit`), not per ticket. A pass over the whole base rather than
one task's findings.

1. Read `docs/knowledge/INDEX.md` — the coverage table is the map, and the `_0_`
   cells are the backlog.
2. Survey the code for what is missing: integrations with no `integration` note,
   scheduled jobs and events with no `overview`, incident-prone areas with no
   `troubleshooting`, business logic with no `business-rule`.
3. Look for **misfilings**, which `lint` cannot see: a rule buried in an
   overview, a decision recorded as a runbook step, a `troubleshooting` note
   with no root cause.
4. Check the notes against the code. Stale notes are worse than missing ones —
   a missing note sends an agent to read the code; a wrong one sends it
   confidently in the wrong direction.
5. Present the plan — refilings, new notes, link repairs — and get sign-off
   before bulk changes. An audit can touch every file in the tree.
6. Then execute: `git mv` for renames, `kb.py new` for gaps, repair
   `## Related` in both directions, and re-run both linters.

## Writing style

Concise, factual, implementation-aware. Explain **why**, not only what.

- Write for an agent that has the code open and no memory of this session.
- Name paths, not source. Paths mostly survive; a pasted snippet rots invisibly
  and nothing tells you it has.
- Prefer rules, decisions, invariants and surprises over code summaries. If a
  competent agent could derive it in thirty seconds by reading the file, it does
  not need a note.
- Quote real evidence — the failing command, the actual output, the exit code.
  The knowledge base inherits the tracker's honesty rule: an unverified claim is
  marked as one, never smoothed into fact.
