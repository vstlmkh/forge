---
description: Check that the harness configuration matches the repository it is installed in
---

Validate the harness itself, not the work it tracks.

```bash
python3 .claude/scripts/forge.py doctor
python3 .claude/scripts/forge.py scopes
python3 .claude/scripts/forge.py repos
python3 .claude/scripts/forge.py checks
python3 .claude/scripts/agile.py lint
python3 .claude/scripts/kb.py lint
```

`doctor` exits 2 when `forge.json` disagrees with the files on disk — a scope
whose agent file is missing, a scope pointing at an undeclared repository, a
scope with no Definition-of-Done rows, a tracker or knowledge-base directory
that does not exist.

Then judge what the exit code cannot:

- **Are the declared checks real?** Run one command from each scope's matrix and
  see whether it exists. A row marked `available` that errors out is worse than
  one marked unavailable — it turns the review gate into theatre. Fix the
  `available` flag in `forge.json` and say which rows you changed.
- **Do the repositories and branches match reality?** `git -C <path> rev-parse
  --abbrev-ref HEAD`, and `git submodule status` where applicable.
- **Does every scope have somewhere for its knowledge to go?** A scope whose
  `kb_scope` has no notes at all is a knowledge base about to be started late.

Report what you changed in `forge.json`, what you could not verify, and what the
user has to decide.
