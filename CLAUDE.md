# forge — working on the harness itself

This repository **is the factory**, not a project that uses the factory. Nothing
here is wired up: there is no `forge.json` at the root, no board, no knowledge
base, and `.claude/scripts/` belongs to `template/`, not to this session. Do not
run `agile.py` or `kb.py` against this repo, and do not install the harness into
it.

```
install.sh                clones into ~/.forge and links the shim; re-run to update
bin/forge                 the CLI: detection, install, render, upgrade
template/                 the payload copied into a project — the actual product
assets/logo.py            the mark: six gates, four cleared
                          -> logo-{light,dark}.svg, favicon.svg
assets/banner.py          regenerates the two README banners; imports the mark
docs/                     how the harness works, and how to extend it
tests/smoke.sh            installs into a throwaway repo and proves every gate fires
```

`bin/forge` is reached through a symlink on `PATH`, so it resolves its own
location with `realpath`, not `abspath` — `template/` has to be found next to
the real file, not next to the shim.

Detection (`forge detect`, and the opening of `forge init`) proposes; it never
asserts. A check it infers is written `"available": true` because the project
*has* that script, not because forge ran it — the text it prints says so, and
`forge doctor` is where that gets tested. Adding a stack means one function in
`bin/forge` and one entry in `MANIFESTS`.

## The one rule that keeps the harness reusable

> Nothing in `template/` may name a project, a stack, a branch, a scope or a
> command.

Everything project-specific is read at runtime from `forge.json`:

- scripts call `forge.load(root)` and take their vocabulary from it;
- skills and commands tell the agent to run `python3 .claude/scripts/forge.py
  scopes` / `checks <scope>` rather than restating a matrix;
- `template/.claude/agents/_engineer.md.tmpl` is rendered per scope by
  `bin/forge`, and it is the only file with `{{PLACEHOLDERS}}`.

If you find yourself writing "backend" or "npm" into a file under `template/`,
it belongs in `forge.json` or in the engineer template instead. The two
`forge.example.*.json` files are where concrete stacks are allowed to appear.

## After any change under `template/`

```bash
tests/smoke.sh
```

It installs into a temporary repository and asserts the gates still fire. A
change to `agile.py`, `kb.py` or a hook without a passing smoke run is not
finished.

Changing a validation rule means changing it in **both** places: `validate()` in
`template/.claude/scripts/agile.py` and the invariant list in
`template/docs/agile/SCHEMA.md` §6. The script wins when they disagree, which is
precisely why the prose must not drift from it.

Adding a frontmatter field means four edits: `SCHEMA.md`, the required-fields
list in the script, the skill that teaches the field, and the smoke test.

## Writing style for the payload

The files under `template/` are read by an agent mid-task, with no memory of
this session, and they are what the agent will obey. Write them accordingly:

- state the rule, then why it exists — a rule whose reason is invisible gets
  optimised away by the next agent;
- prefer a command the agent can run over a fact it has to trust;
- name the failure the rule prevents. "Do not edit `INDEX.md`" is weaker than
  the sentence explaining that a hook will deny it and the board regenerates
  anyway.

## Attribution

forge signs what forge generates — both `INDEX.md` boards, the managed
`CLAUDE.md` block, the rendered agents — and nothing else. Adding a signature
anywhere a human or an agent writes (a commit trailer, a PR body, a ticket, a
note) is out of bounds: those belong to the project, not to the tool. Keep it
visible text with a link rather than a hidden mark, and keep
`"attribution": false` working everywhere, including in anything new you teach
forge to generate. `cfg.credit()` in the payload and `credit()` in `bin/forge`
are the only two places that produce the line.

## Two distribution channels, one CLI

`install.sh` (a git checkout in `~/.forge`) and the npm package
(`@vstlmkh/forge`, where `bin/forge.js` shells out to `bin/forge`) ship the same
files. Two things must therefore stay true: `VERSION` in `bin/forge` equals
`version` in `package.json` — the smoke test checks it — and anything a new
feature needs at runtime belongs in the `files` list of `package.json`, or it
will work from a checkout and be missing from the package. `forge self-update`
branches on which channel it is running from; keep both branches correct.

## Compatibility

Stdlib-only Python 3.9+. The hooks run on every turn in every installed project,
so a third-party import here is a dependency tree in someone else's repository.
`bin/forge` has the same constraint.

When a change to the payload would break an existing installation — a renamed
field, a moved path — say so in the commit body and make `forge upgrade` handle
it, or make `forge.py doctor` report it. A project upgrades by running the CLI,
not by reading a changelog.

## The assets

`assets/logo.py` and `assets/banner.py` are generators; the SVGs beside them
are outputs and are regenerated, never hand-edited. The mark's geometry lives
in `logo.py` alone and `banner.py` imports it, so the two cannot drift.

| File | Written for |
|---|---|
| `banner-{light,dark}.svg` | the README header, switched by `<picture>` |
| `logo-{light,dark}.svg` | the mark on its own, wherever one ground is known |
| `favicon.svg` | a browser tab: one file, theme-switched by a `<style>` inside it |

Two files rather than one everywhere except the favicon, because GitHub only
picks between images with `<picture><source media="(prefers-color-scheme:
dark)">` and its sanitiser is free to drop a `<style>` from an SVG served as an
`<img>`. A favicon has no `<picture>` to switch with and is resolved by the
browser rather than by GitHub, so there the media query is the only option and
it works.

Nothing in this repository consumes `favicon.svg` yet — there is no site. It
exists so that whatever fronts the project next does not need the mark redrawn.
