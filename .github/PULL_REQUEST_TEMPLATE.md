## What and why

<!-- One coherent change. A refactor and a behaviour change in one diff is two PRs.
     Say what breaks for an existing installation, if anything. -->

Closes #

## How it was verified

```
$ tests/smoke.sh
<!-- paste the tail -->
```

<!-- Anything else you ran: forge init --auto into a scratch repo, forge upgrade
     twice for a zero diff, forge detect on a real project. -->

## Checklist

- [ ] Nothing under `template/` names a project, a stack, a branch, a scope or a command
- [ ] `tests/smoke.sh` passes, and new behaviour has a new assertion in it
- [ ] A validation rule changed in `agile.py` is also changed in `template/docs/agile/SCHEMA.md` §6 (and the reverse)
- [ ] A new frontmatter field landed in all four places: `SCHEMA.md`, the script's required-fields list, the skill that teaches it, the smoke test
- [ ] Anything new that is read at runtime is in `package.json`'s `files`
- [ ] `VERSION` in `bin/forge` still equals `version` in `package.json`
- [ ] Stdlib-only Python 3.9+; no third-party import anywhere in the hook path
- [ ] No forge signature on anything forge does not generate, and `"attribution": false` still removes every instance
- [ ] Breakage for existing installations is handled by `forge upgrade` or reported by `forge.py doctor`, and named in the commit body
