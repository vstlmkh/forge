---
description: File a bug with a reproduction and have the PM triage it
argument-hint: [what is broken — symptom, where, and how to see it]
---

File a bug: **$ARGUMENTS**

## 1. Gather before you file

A bug without a reproduction is a rumour. Before creating the file, establish as
much of this as you can from the conversation, the code and the logs:

- exact steps to reproduce, or a precise pointer at the offending code;
- expected versus actual behaviour;
- evidence — a response body, a stack trace, a log line, a file and line number;
- which scope owns it (`python3 .claude/scripts/forge.py scopes`);
- when it started, and whether a known ticket introduced it;
- **whether this has happened before**:
  `python3 .claude/scripts/kb.py find <symptom keyword> [...]` and a look
  through `docs/knowledge/*/troubleshooting/`. A recurrence is worth far more
  than a new report: the existing note already carries the root cause, the fix
  and the detection command. Say plainly whether this is new or a repeat, and
  list the note in the bug's `docs:`.

Ask the user — in their own language — for anything critical you cannot
determine yourself. Do not invent a reproduction.

## 2. Create it

```bash
python3 .claude/scripts/agile.py next-id bug
```

Write `docs/agile/bugs/<ID>-<kebab-slug>.md` with the full bug frontmatter from
`docs/agile/SCHEMA.md`: `status: triage`, `reported_by`, `found_in`, and
`severity` left for triage if you genuinely cannot judge it. Fill
`## Steps to reproduce`, `## Expected`, `## Actual` and `## Evidence`. **Leave
`## Root cause` empty** — the engineer owns it, and `lint` will block the bug
from reaching `review` without it.

## 3. Triage

Dispatch the `pm` subagent to triage: reproduce or attempt to, set `scope`,
`severity` and `priority`, and move `triage -> todo`. A defect spanning several
scopes stays `blocked` with one spawned task per scope listed in
`spawned_tasks`.

```bash
python3 .claude/scripts/agile.py lint
git add docs && git commit -m "chore(agile): opens <BUG-ID>"
```

## 4. Report

Give the user the bug ID, the severity and priority with a one-line
justification, and whether it jumps the queue. An `S1` should be worked
immediately via `/agile:work <ID>` — say so rather than leaving it on the board.
