---
name: agile-lessons
description: How the agents record and obey what this project has taught them about working here — reading the rules at the start of a gate, filing one when a ticket bounces, confirming an existing rule instead of duplicating it, and judging a NO-LESSON waiver at gate 5. Load before closing a ticket that was rejected at any gate, and whenever `lessons:` or `lessons_waiver:` has to be set. The convention itself is docs/lessons/README.md.
---

# Lessons

The tracker is what we are doing. The knowledge base is what we know about the
product. Lessons are **how work goes wrong here** — the rules this project paid
for, usually by a ticket bouncing off a gate. This skill is the procedure;
`docs/lessons/README.md` is the specification.

## Reading them costs one line each. That is deliberate.

```bash
python3 .claude/scripts/lessons.py for <your agent name>
```

Every rule is one imperative line of at most 120 characters, and the hand-off is
capped at `policy.lesson_budget` of them, ranked by how often each has proved
itself. You read lines, not files. Open one only when the line is not enough:

```bash
python3 .claude/scripts/lessons.py show LESSON-0003
```

The cap exists because the alternative does not work. Forty rules in front of an
agent is forty rules none of which get read, and every one of them is context
spent before the ticket is. If the hand-off says it withheld something, that is
the ranking doing its job, not an error to route around.

## A lesson is owed when a ticket bounces

Not when it closes. A ticket that ran straight through taught nothing about the
process, and `lessons_waiver: NO-LESSON (ran clean)` is the honest answer. What
is not honest is waiving a ticket that went backwards:

| Edge | Who learned it |
|---|---|
| `speccing -> todo` | the request could not be specified as written |
| `writing_tests -> speccing` | the brief was wrong, and the test writer found out |
| `in_progress -> writing_tests` | the test was wrong, and the implementer found out |
| `review -> in_progress` | the work was wrong in a way review could name |

Whoever **takes** that edge files the lesson, at the moment they take it. They
are the only one who still knows why; by gate 5 it has decayed into one line of
`## Log`. A hook will say so at the edit itself.

## Confirm before you file

```bash
python3 .claude/scripts/lessons.py list --scope <scope>
```

If a rule already says it, confirm that one:

```bash
python3 .claude/scripts/lessons.py confirm LESSON-0003 --ticket <TICKET-ID>
```

This is not bookkeeping. `confirmations` is the ranking key, so confirming is
what keeps a rule that keeps mattering inside the budget — and a near-duplicate
filed instead splits the evidence between two rules and sinks both.

Only when nothing fits:

```bash
python3 .claude/scripts/lessons.py new "<two to five words>" \
    --scope <scope|all> --roles <role,role|all> --gate <N> --ticket <TICKET-ID> \
    --rule "<one imperative line>"
```

Then put the id in the ticket's `lessons:`. The file is not finished until
`## Why`, `## How to apply` and `## Evidence` are real; `lessons.py lint`
rejects a skeleton, and `agile.py lint` rejects an id that does not resolve.

## Writing the rule

The `rule:` line is the entire artefact for most readers. Write it as an
instruction, in the imperative, naming the action:

- **Good** — `Run every available check before asking for review, not after review asks.`
- **Bad** — `Checks matter.` (not an action)
- **Bad** — `The engineer should probably consider running the checks earlier.` (hedged, and longer than the failure it prevents)

`## Why` names the failure. A rule whose reason is invisible gets optimised away
by the next agent — which is how the project unlearned it the first time.

## What is not a lesson

A fact about the product is a knowledge-base note: `kb.py new`. The test is who
the rule binds. "The load balancer drops an instance that answers anything but
200" is true of the system — a note. "Run the migration check before opening the
PR" is true of working here — a lesson. Filing the first one here hides it from
everyone who searches the knowledge base, and the knowledge base is where the
next ticket will look.

## It decays, and that is the point

`lessons.py lint` warns when a rule has not been confirmed in
`policy.lesson_stale_days`. Answer the warning rather than silencing it:

```bash
python3 .claude/scripts/lessons.py retire LESSON-0003 --reason "the check now runs in CI"
```

Retiring is not deleting — the id stays resolvable for the tickets that cite it.
A rule nobody has needed in half a year is charging every agent context on every
turn for a failure that no longer happens.

## At gate 5

`qa` judges the lesson exactly as it judges the notes: it does not write the one
the implementer owed and then approve it, and it does not accept a NO-LESSON
waiver from a ticket that bounced. The contract is printed, not remembered:

```bash
python3 .claude/scripts/agile.py gates 5
```
