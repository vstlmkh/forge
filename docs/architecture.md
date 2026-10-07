# How the harness is put together

Four records, each with a validator, a generated index and a guard that stops an
agent corrupting it by hand.

| Record | Path in a project | Validator | Answers |
|---|---|---|---|
| the tracker | `docs/agile/` | `agile.py lint` | what are we doing |
| the knowledge base | `docs/knowledge/` | `kb.py lint` | what do we know about the product |
| the lessons | `docs/lessons/` | `lessons.py lint` | how work goes wrong here |
| the shape | `forge.json` | `forge.py doctor` | what is this project made of |

## Why a record of the project's shape

The first version of this harness hardcoded two scopes, two submodules, two
engineer agents and one Definition-of-Done matrix into the scripts, the skills
and the agents. It worked, and it was unmovable: adapting it to a second project
meant editing eleven files and hoping you found all of them.

`forge.json` exists so that there is exactly one. The scripts read their
vocabulary from it at runtime; the skills tell the agent to *run* a command that
prints the matrix instead of restating the matrix; the engineer agents are
rendered from one template. The payload under `template/` is therefore identical
in every installation, which is what makes `forge upgrade` safe.

## Data flow

```
forge.json ──► forge.py ──► agile.py   ──► docs/agile/INDEX.md
     │             │    ├──► kb.py      ──► docs/knowledge/INDEX.md
     │             │    └──► lessons.py ──► docs/lessons/INDEX.md
     │             └──► guard-*.py, kb-context.py, kb-nudge.py,
     │                  lesson-nudge.py                          (hooks)
     └──► bin/forge ──► .claude/agents/{pm,qa,qa-spec,<scope>-engineer}.md,
                         the CLAUDE.md block
```

`agile.py` owns the frontmatter parser — a deliberately restricted YAML subset:
flat keys, flat lists, nothing nested. `kb.py` and `lessons.py` import it, so
every record speaks the same dialect and a note cannot drift into syntax the
tracker could not parse. All three are stdlib-only because they run inside
hooks, on every turn. The dependency goes one way: `agile.py` resolves a
ticket's `lessons:` by reading the files rather than importing `lessons.py`,
which imports `agile.py`.

## Why the spec is a separate file

A ticket's acceptance criteria say what to do. They are written by `pm` at
grooming, before anyone has tried to write a test against them, which is exactly
when the detail a test needs is still unknown. The spec at
`docs/agile/specs/<ID>.md` is where that detail is settled: `qa` answers what the
repository can answer, puts the rest to the user as one batch of questions
through the top-level session, and records the result as numbered requirements.

It is a separate file rather than more sections in the ticket for one reason
that is about cost. The ticket's `## Log` grows with every gate and every
rejection; by the time the engineer reads it, most of it is history. Splitting
the brief out means the engineer is handed `## Brief` and `## Spec` and nothing
else, and the same is true of every later gate — `agile.py handoff` carries a
different slice to each one. The ticket stays the record of what happened; the
spec stays the record of what was agreed.

The second reason is that it makes the gate checkable. The spec's own
`status: agreed` is what `lint` reads to decide whether a ticket may reach
`writing_tests` at all, and the requirement ids are what let a test, an evidence
line and a deferred ticket all point at the same thing.

## Why the dispatch prompt is built by a script

`agile.py handoff <ID> --gate <N>` renders a fixed five-part payload: the gate's
contract, the prohibitions that bind at that gate, the reference material, the
steps, and then the contract and prohibitions again, compressed.

The repetition is not redundancy. Attention falls off in the middle of a long
prompt, so anything binding is placed in the first screen and the last, and the
middle carries only inert reference — and that reference is paths and commands
rather than pasted file bodies, which is also what keeps a payload around 700
tokens instead of several thousand. A model tier per role lives in
`forge.json` under `policy.models`, because a model is bound to an agent file
rather than to a dispatch.

## The hooks, and what each one is for

| Hook | Event | Effect |
|---|---|---|
| `guard-index.py` | `PreToolUse` | denies a hand-edit of any generated `INDEX.md` |
| `guard-kb.py` | `PreToolUse` | denies a misfiled or misnamed note, a new ticket with no `docs:` or no `spec:`, a spec not named after an existing ticket, and writes under a disowned knowledge directory |
| `kb-nudge.py` | `PostToolUse` | catches a ticket moved to `review`/`done` with an empty `docs:`, while the agent still has the context to file the note |
| `kb-context.py` | `UserPromptSubmit` | injects the knowledge base's coverage when a cycle command starts, so consulting it is cheap at the one moment it matters |
| `lesson-nudge.py` | `PostToolUse` | catches a ticket moving *backwards* and asks for the lesson while the agent still knows why it bounced |
| `agile.py index`, `kb.py index`, `lessons.py index` | `Stop` | regenerate all three boards once per turn |

Guards fail open: any internal error allows the write. A guard that breaks a
session is worse than one that misses a file, and `lint` is the backstop.

## The claim protocol

There is no lock file. A claim is one `Edit` whose `old_string` is the whole
unclaimed frontmatter block; because `Edit` demands an exact match, the second
agent's edit fails, and that failure *is* the lock. `lint` then enforces the
consequence that locking cannot: at most one ticket per working tree may be in
`writing_tests`, `in_progress` or `review`, where a working tree is a repository
in `forge.json` and several scopes may share one.

## Why the knowledge base is typed

Eight types, each with required sections, and a filename that states its own
type in literal braces. The redundancy is what makes a note findable by path, by
basename and by `kb.py find` alike — and what makes a misfiling visible to a
reviewer. `lint` cannot catch a business rule filed as an `overview`; a human or
`qa` can, and the type system is what gives them something to point at.

Notes are a graph, not a tree: `INDEX.md` is a generated table of contents and
the edges live in each note's `## Related`, reciprocal in both directions, with
a reason on every link.

## Why a lesson is one line

The knowledge base is read on demand: an agent searches it, opens two notes and
pays for what it opened. The lessons layer is read *unconditionally*, at the top
of every gate, by every agent — so its cost is paid on every turn whether or not
it is relevant, and that changes what the format can be.

Hence one imperative line per rule, at most 120 characters, with the body behind
a second command that most readers never run. Hence a hard cap
(`policy.lesson_budget`, 12) on how many reach one agent, ranked by how often
each has proved itself, with the withheld ones named rather than dropped
silently. And hence decay: `lessons.py lint` warns when a rule has not been
confirmed in `policy.lesson_stale_days`, because an obsolete rule is not
harmless here — it is a line of context charged to every agent on every turn for
a failure that no longer happens.

The signal that fills the layer is a ticket moving backwards. A bounce is the
only event the harness produces that distinguishes "the code was wrong" from
"the process was wrong", and `lesson-nudge.py` fires on that edit rather than at
gate 5 because the agent taking the failure edge is the only one who still knows
why.
