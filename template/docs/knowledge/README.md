# The project knowledge base

Durable knowledge about this project, in plain Markdown, committed here.
`docs/agile/` records **what we are doing**; `docs/knowledge/` records **what we
know**. A ticket is closed and forgotten; a note outlives it.

This file is the authoritative specification of the convention.
`.claude/scripts/kb.py lint` enforces its mechanical half, exactly as
`agile.py lint` does for the tracker. If the two disagree, the script wins and
this file is the bug.

> **Source code remains the ultimate source of truth.** When a note and the code
> disagree, the code is right, the note is stale, and fixing the note is part of
> whatever task discovered the discrepancy.

## Layout

```
docs/knowledge/<scope>/<type>/{<type>} <description> - <yyyy-mm-dd>.md
```

**The curly braces around the type are literal characters in the filename**, not
placeholders, and so is the ` - ` before the date. Only `<scope>`, `<type>`,
`<description>` and `<yyyy-mm-dd>` are placeholders — everything else is typed
exactly as shown.

- `<scope>` — one of this project's knowledge-base scopes. A folder, no braces.
  `python3 .claude/scripts/kb.py types` prints them; they come from `forge.json`
  and usually mirror the tracker's scopes plus a `shared` one.
- `<type>` — one of the eight types below. It is both the folder name (plain)
  and the braced first token of the filename; the redundancy is deliberate, so
  a note is filed correctly whether you found it by path or by basename, and a
  basename quoted out of context still states its own kind.
- `<description>` — lowercase words separated by spaces, two to five of them,
  naming the subject rather than the event: `subscription proration`, not
  `fixed the proration bug`. A hyphen is allowed inside a word, so
  `docker-compose` survives. Nothing else: no braces, no punctuation, no
  capitals.
- `<yyyy-mm-dd>` — unbraced, after a ` - ` separator, and it is the date the
  note was **created**, never touched again. Age is information; `updated:` in
  the frontmatter carries the freshness.
- The whole basename is at most 80 characters and is **globally unique** across
  the tree, which is what lets `[[wikilinks]]` address a note by basename alone.

```
docs/knowledge/backend/business-rule/{business-rule} subscription proration - 2026-10-03.md
docs/knowledge/frontend/troubleshooting/{troubleshooting} hydration mismatch on plans - 2026-10-03.md
docs/knowledge/shared/api-contract/{api-contract} subscriptions endpoint - 2026-10-03.md
```

> **Quote every path.** Spaces and braces mean a bare
> `cat docs/knowledge/shared/overview/{overview} repo layout - 2026-10-03.md`
> is not one argument. Quote it, or let the tools hand you the path:
> `kb.py find`, `kb.py for-ticket` and `kb.py new` all print paths you can copy.

Never create a note by hand — the path, the frontmatter and the section
skeleton all come out right if you use:

```bash
python3 .claude/scripts/kb.py new <type> <scope> "<description>" [--ticket TASK-0001]
```

### `<scope>`

A knowledge-base scope answers "where is this true?". The project declares them
in `forge.json`; each tracker scope maps to one, and scopes that are not tied to
a single repository (infra, docs, the harness itself) map to the shared one.
A ticket scoped to one repository may still legitimately touch a `shared` note —
the endpoint it implements is half of a contract.

### `<type>`

| Type | Answers | Filed when |
|---|---|---|
| `business-rule` | what the product **must** do | a rule exists that code has to obey and violating it is a defect, whether or not a test guards it |
| `troubleshooting` | this broke before, here is why | a bug is fixed, an incident is understood, or a failure recurs |
| `overview` | how this module is put together | a subsystem's structure, entry points and responsibilities are worth a map |
| `integration` | how an external system actually behaves | a third-party API, a queue, a host — including its lies |
| `api-contract` | what one side promises the other | an interface's shape is agreed across a boundary — usually `shared/` only |
| `decision` | why it is this way and not the obvious way | an architectural choice with alternatives that a future agent would otherwise re-litigate |
| `runbook` | how to actually run the thing | a procedure worth repeating — local setup, deploy, rollback, a migration |
| `data-model` | what the entities are and what holds them together | a schema, its invariants and the relations behind them |

Two rules keep the taxonomy from collapsing:

1. **`overview` is not the default.** A rule goes in `business-rule`, an
   incident in `troubleshooting`, an external system in `integration`, a
   procedure in `runbook`. Dumping everything into `overview` is the single most
   common way a knowledge base like this dies. `kb.py lint` cannot catch it;
   reviewers can.
2. **One finding, one note.** A task that reveals a business rule *and* an
   external-API quirk *and* a fix produces three notes, cross-linked — not one
   note with three headings. They will be needed by different tasks at different
   times.

## Frontmatter

The grammar is the tracker's restricted grammar, parsed by the same code:
`key: scalar`, `key: [a, b]`, or `key:` followed by indented `- item` lines.
No nested maps, no `|` blocks, no anchors.

```yaml
---
type: business-rule        # one of the eight above; must match the folder
scope: backend             # a knowledge-base scope; must match the folder
title: Proration is computed on billing-period days, not calendar days
status: current            # current | superseded
created: 2026-10-03        # must equal the date in the filename
updated: 2026-10-03
tickets: [TASK-0231]       # the tickets that produced or last confirmed this
superseded_by: null        # a note basename, required when status is superseded
labels: [billing]
---
```

`title` is a sentence, not a filename echo. It is what an agent reads in
`INDEX.md` when deciding whether to open the note, so it should state the
finding: *"Proration is computed on billing-period days"* earns its line;
*"Proration"* does not.

## Body

Every note ends with `## Related`. Otherwise the sections follow the type:

| Type | Required sections |
|---|---|
| `business-rule` | `## Rule`, `## Why`, `## Where enforced`, `## Related` |
| `troubleshooting` | `## Symptom`, `## Root cause`, `## Fix`, `## How to detect it again`, `## Related` |
| `overview` | `## What it does`, `## Structure`, `## Entry points`, `## Related` |
| `integration` | `## What it is`, `## How we call it`, `## Behaviour to know`, `## Related` |
| `api-contract` | `## Endpoint`, `## Request`, `## Response`, `## Consumers`, `## Related` |
| `decision` | `## Decision`, `## Context`, `## Alternatives considered`, `## Consequences`, `## Related` |
| `runbook` | `## When to run this`, `## Steps`, `## If it goes wrong`, `## Related` |
| `data-model` | `## Entities`, `## Invariants`, `## Relations`, `## Related` |

A section whose only content is `_to be filled_`, `TBD`, `TODO`, `N/A` or a bare
bullet counts as **empty** and `lint` says so — the same rule the tracker
applies to `## Root cause`.

Write for an agent that has the code open and no memory. Explain *why*. Name
files and paths instead of pasting source: code moves, paths mostly do not, and
a pasted snippet rots invisibly.

## Cross-linking

Notes form a graph. `INDEX.md` is a generated table of contents, not the graph —
the edges live in the notes.

```markdown
## Related

- [[{api-contract} subscriptions endpoint - 2026-10-03]] — the field this rule feeds
- [[{integration} stripe webhooks - 2026-10-03]] — where the period days come from
```

- A wikilink addresses a note by **basename without `.md`**. Basenames are
  unique, so no path is needed and a note can be moved between scopes without
  breaking inbound links.
- Every link carries a trailing `— why it is related`. A bare list of links is
  a dead end; the reason is what lets an agent decide not to open it.
- Links are **directional but reciprocal**: when you link A → B, add the
  matching line to B's `## Related`. `kb.py lint` reports one-sided edges as
  warnings.
- A note with no connections keeps the heading with a single `- _none yet_`
  line, so the absence is visible rather than accidental.
- A note that goes wrong is **superseded**, not deleted: set
  `status: superseded`, point `superseded_by` at the replacement, and keep the
  file. Knowing what we used to believe is why `troubleshooting` exists.

## The tie to the tracker

The link runs both ways, and both directions are linted.

- A note's `tickets:` lists the tickets that produced or last confirmed it.
- A ticket's `docs:` lists the notes read at grooming and actualised at close.
  A ticket at `review` or beyond with an empty `docs:` and no
  `docs_waiver: NO-DOCS (<reason>)` is a `lint` error, not an oversight.

See `docs/agile/SCHEMA.md` §3.2 for the ticket fields and
`.claude/skills/project-knowledge/SKILL.md` for the consult/create/update
procedure the agents follow.

## Commands

```bash
python3 .claude/scripts/kb.py find stripe proration   # what do we already know?
python3 .claude/scripts/kb.py for-ticket TASK-0231    # notes bound to a ticket
python3 .claude/scripts/kb.py new business-rule backend "subscription proration"
python3 .claude/scripts/kb.py related "{business-rule} subscription proration - 2026-10-03"
python3 .claude/scripts/kb.py types                   # scopes, types and their sections
python3 .claude/scripts/kb.py lint                    # exit 2 means it is inconsistent
python3 .claude/scripts/kb.py index                   # regenerate INDEX.md
```

`INDEX.md` is generated. Never edit it — a `PreToolUse` hook denies the write,
and a `Stop` hook regenerates it once per turn.
