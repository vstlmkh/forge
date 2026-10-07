# Lessons

What this project has taught its agents about **how work goes wrong here**.

`docs/agile/` records what we are doing. `docs/knowledge/` records what we know
about the product. This records the rule a ticket paid for — usually by bouncing
off a gate — so that the next agent does not pay for it again.

This file is the authoritative specification of the convention.
`.claude/scripts/lessons.py lint` enforces its mechanical half, exactly as
`agile.py lint` does for the tracker. If the two disagree, the script wins and
this file is the bug.

> **A lesson is not a knowledge-base note.** A note says *the product works like
> this*; a lesson says *you will get this wrong unless you do that*. If what you
> learned is true about the system rather than about working on it, it is a note
> — `kb.py new` — and filing it here hides it from everyone who searches the
> knowledge base.

## The one-line rule is the whole design

Every lesson carries a `rule:` in its frontmatter: one imperative line, at most
120 characters. That line — not the file — is what an agent is handed at the
start of a gate:

```bash
python3 .claude/scripts/lessons.py for <agent>
```

It prints the rules that address that agent, ranked, and **never more than
`policy.lesson_budget` of them** (12 by default). It names how many it withheld
rather than truncating in silence. An agent reads the body only when the line
turns out to matter:

```bash
python3 .claude/scripts/lessons.py show LESSON-0003
```

That split is the reason this layer exists at all. Everything an agent reads at
gate time is context it does not spend on the ticket, so a lesson that cannot be
stated in one line is not yet understood well enough to be a lesson. `lint`
enforces the limit, and warns when a body runs past 40 lines.

## Layout

```
docs/lessons/<scope>/LESSON-NNNN <description>.md
```

- `<scope>` — a tracker scope from `forge.json`, or the reserved `all` for a
  rule that binds every scope. `lessons.py roles` prints the list.
- `LESSON-NNNN` — allocated by `lessons.py new`, never by hand. A lesson is
  addressed by id everywhere: in a ticket's `lessons:`, in a `[[LESSON-0003]]`
  link, in what `for` prints back. That is why the id leads the filename and
  there is no braced type and no date in it — the knowledge base needs those,
  this does not.
- `<description>` — two to five lowercase words naming the subject.

Never create one by hand:

```bash
python3 .claude/scripts/lessons.py new "<two to five words>" \
    --scope <scope|all> --roles <role,role|all> [--gate N] [--ticket <ID>] \
    --rule "<one imperative line>"
```

## Frontmatter

| Field | Meaning |
|---|---|
| `id` | `LESSON-NNNN`, allocated by the script |
| `scope` | a tracker scope, or `all` |
| `roles` | which identities must obey it: any of `pm`, `qa`, `engineer`, or `all` |
| `rule` | **one imperative line**, ≤ 120 chars — the only part most agents read |
| `status` | `active`, `retired`, `superseded` |
| `gate` | the gate this was learned at, `1`–`6`, or `null` |
| `tickets` | what produced or confirmed it |
| `confirmations` | how often it has proved itself again; it is the ranking key |
| `last_confirmed` | bumped by `lessons.py confirm`; it is what decays |
| `created`, `updated` | dates; `created` is never touched again |
| `superseded_by` | set only when `status: superseded` |

Body: `## Why`, `## How to apply`, `## Evidence`, `## Related`. `## Why` names
the failure the rule prevents — a rule whose reason is invisible gets optimised
away by the next agent, which is exactly how the project unlearned it the first
time.

## It decays on purpose

A rule nobody has needed in `policy.lesson_stale_days` (180 by default) is
spending context on every turn for nothing. `lessons.py lint` warns about it and
asks for one of two decisions:

```bash
python3 .claude/scripts/lessons.py confirm LESSON-0003 --ticket TASK-0051
python3 .claude/scripts/lessons.py retire  LESSON-0003 --reason "the check now runs in CI"
```

Confirming is not bookkeeping: `confirmations` is the ranking key, so confirming
is how a rule that keeps mattering stays inside the budget and a rule that
stopped mattering falls out of it.

Two active lessons that read the same are reported by `lint`. Resolve them with
`supersede`, never by deleting one — the id is referenced from tickets.

## Related

- [`../agile/SCHEMA.md`](../agile/SCHEMA.md) — the `lessons:` field on a ticket
  and the gate that requires it.
- [`../knowledge/README.md`](../knowledge/README.md) — where a fact about the
  product goes instead.
