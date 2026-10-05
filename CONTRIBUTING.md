# Contributing to forge

forge is a harness that gets copied into other people's repositories, where it
runs on every turn and refuses to install a dependency tree. That single fact
sets every rule below. Read the two short ones — [the one rule](#the-one-rule)
and [what has to change together](#what-has-to-change-together) — before you
write code; the rest you can look up when you need it.

- [Filing an issue](#filing-an-issue)
- [Working on the code](#working-on-the-code)
- [The one rule](#the-one-rule)
- [What has to change together](#what-has-to-change-together)
- [Adding a stack](#adding-a-stack)
- [Tests](#tests)
- [Commits](#commits)
- [Pull requests](#pull-requests)
- [Releases](#releases)

## Filing an issue

Open issues at <https://github.com/vstlmkh/forge/issues>. There are four forms,
and picking the right one decides how fast the issue gets answered:

| Form | Use it when |
|---|---|
| **Bug** | a command does the wrong thing: `detect` misreads a project, `init` writes something broken, `upgrade` produces a diff on a second run, a hook denies a write it should allow |
| **Stack support** | `forge detect` does not recognise a language, a package manager or a layout it ought to |
| **Feature / change** | the harness should do something it does not, or a rule should be different |
| **Docs** | the README, `docs/` or anything under `template/docs/` is wrong, missing or contradicts the scripts |

### What a good bug report contains

A reproduction beats a description. Paste the output, not your reading of it:

```bash
forge where         # which channel: a ~/.forge checkout, or an npm install
forge version
python3 --version
forge detect .      # the shape forge infers from the project in question
```

Then: what you ran, what happened, what you expected. If the bug is inside an
installed project rather than in the CLI, add:

```bash
python3 .claude/scripts/forge.py doctor
python3 .claude/scripts/agile.py lint
python3 .claude/scripts/kb.py lint
```

Two things are worth stating explicitly because they are the usual cause:

- **which channel** you installed through — `install.sh` into `~/.forge`, or
  `npm`/`npx @vstlmkh/forge`. The two ship the same files but resolve paths
  differently, and `forge self-update` has a separate branch for each;
- **the project's `forge.json`**, redacted. Nearly every "the harness is wrong"
  report turns out to be a disagreement between the config and the repository,
  which is exactly what `doctor` exists to name.

**Do not paste client code, private paths or credentials.** forge is installed
into other people's repositories; a bug report is not worth leaking one. Reduce
the problem to a throwaway `git init` directory wherever you can — the reporter
who includes a five-line reproduction gets a fix, the one who includes a
screenshot of a private monorepo gets questions.

### Before you open a feature request

Say which of these the change is, because they have different bars:

- **a project's business** — a scope, a stack label, a check command, a policy
  toggle. That is `forge.json` in your project, not a change here. See
  [docs/customizing.md](docs/customizing.md); if `forge.json` genuinely cannot
  express it, *that* is the feature request, and say so in those words;
- **the payload** — a skill, a hook, a tracker field, a knowledge-base type.
  Name the failure it prevents. Every rule under `template/` is a rule some
  agent has to obey in somebody else's repository forever, so a rule with no
  named failure is a rule the next agent optimises away;
- **the CLI** — detection, rendering, upgrade. Keep it stdlib-only; see
  [Compatibility](#compatibility).

### Security

Do not open a public issue for a vulnerability — a hook that can be made to
execute attacker-controlled input, a guard that can be bypassed into a write
outside the project. Mail <vladislav.stelmakh02@gmail.com> instead.

## Working on the code

```bash
git clone https://github.com/vstlmkh/forge.git
cd forge
bin/forge version          # no build step; it is one stdlib-only Python file
tests/smoke.sh             # ~a minute, installs into a temporary repository
```

**This repository is the factory, not a project that uses the factory.** There
is no `forge.json` at the root, no board and no knowledge base, and
`.claude/scripts/` belongs to `template/`. Never run `agile.py` or `kb.py`
against this checkout, and never `forge init` it into itself — see
[CLAUDE.md](CLAUDE.md), which is the agent-facing version of this document.

To try a change end to end, install it into a scratch repository:

```bash
mkdir /tmp/scratch && cd /tmp/scratch && git init
/path/to/forge/bin/forge init --auto
```

`bin/forge` is reached through a symlink on `PATH`, so it resolves its own
location with `realpath`, not `abspath`: `template/` has to be found next to the
real file, not next to the shim. Preserve that if you touch path resolution.

### Compatibility

Stdlib-only Python 3.9+ for `bin/forge` and for everything under
`template/.claude/scripts/`. The hooks run on every turn in every installed
project, so a third-party import here is a dependency tree in someone else's
repository. Node appears only as the npm shim, and does nothing but exec the
Python.

When a change would break an existing installation — a renamed field, a moved
path — say so in the commit body, and either make `forge upgrade` handle it or
make `forge.py doctor` report it. A project upgrades by running the CLI, not by
reading a changelog.

## The one rule

> Nothing in `template/` may name a project, a stack, a branch, a scope or a
> command.

Everything project-specific is read at runtime from `forge.json`: scripts call
`forge.load(root)`, skills and commands tell the agent to run
`python3 .claude/scripts/forge.py scopes` / `checks <scope>` rather than
restating a matrix, and `template/.claude/agents/_engineer.md.tmpl` is the only
file with `{{PLACEHOLDERS}}`.

If you find yourself writing `backend` or `npm` into a file under `template/`,
it belongs in `forge.json` or in the engineer template instead. The two
`forge.example.*.json` files are the only place concrete stacks may appear.

This is what makes `forge upgrade` safe: the payload is byte-identical in every
installation, so refreshing it cannot overwrite a project's decisions.

### Writing style for the payload

Files under `template/` are read by an agent mid-task, with no memory of the
discussion that produced them, and they are what the agent will obey:

- state the rule, then why it exists — a rule whose reason is invisible gets
  optimised away;
- prefer a command the agent can run over a fact it has to trust;
- name the failure the rule prevents. "Do not edit `INDEX.md`" is weaker than
  the sentence explaining that a hook will deny it and the board regenerates
  anyway.

## What has to change together

Three changes touch more than one file by nature. A PR that does half of one is
incomplete, and the smoke test catches most but not all of it:

| Change | Every place it has to land |
|---|---|
| a validation rule | `validate()` in `template/.claude/scripts/agile.py` **and** the invariant list in `template/docs/agile/SCHEMA.md` §6 |
| a frontmatter field | `SCHEMA.md`, the required-fields list in the script, the skill that teaches the field, and `tests/smoke.sh` |
| anything a new feature reads at runtime | the `files` list in `package.json` — otherwise it works from a checkout and is missing from the npm package |
| a version bump | `VERSION` in `bin/forge` **and** `version` in `package.json`; the smoke test asserts they are equal |

The script wins when prose and code disagree, which is precisely why the prose
must not drift from it.

## Adding a stack

Detection is the most common contribution, and it is two edits:

1. a `_<lang>_checks(dir)` function in `bin/forge` returning a stack label and
   the real test / lint / type / build commands the manifest implies;
2. one entry in `MANIFESTS` mapping the manifest filename to it.

Then extend the detection assertions in `tests/smoke.sh`, and add the manifest
to the list in the README.

Detection **proposes; it never asserts**. A check it infers is written
`"available": true` because the project *has* that script, not because forge ran
it — the text `detect` prints says so, and `forge doctor` is where it gets
tested. Do not make detection execute project commands.

## Tests

```bash
tests/smoke.sh
```

It installs into a temporary repository, files a ticket and a note through the
scripts, and asserts that each gate fires: the docs gate, the knowledge-base
naming guard, the generated-index guard, the byte-stability of both indexes, the
one-working-tree rule, and that the CLI and the package agree on a version.

**A change to `agile.py`, `kb.py`, a hook or anything else under `template/`
without a passing smoke run is not finished.** New behaviour means a new
assertion in the same file; a gate nobody tests is a gate that silently stops
firing.

## Commits

Conventional-commit prefix, lowercase subject, present tense, describing what
the commit does to the repository:

```
feat: ships forge as an npm package, @vstlmkh/forge
fix: makes the installer survive a private repo and several GitHub accounts
docs: adds badges to the README
chore: releases 1.0.1
```

`feat`, `fix`, `docs`, `refactor`, `test`, `chore`. One concern per commit. Put
the reason, and any breakage for existing installations, in the body — the
subject says what changed, the body says why it had to.

Do not add a forge signature to a commit, a PR body, a ticket or a note.
[forge signs only what forge generates](README.md#attribution): the two
`INDEX.md` boards, the managed `CLAUDE.md` block, the rendered agents. Anything
a human or an agent writes belongs to the project, not to the tool — and
`"attribution": false` has to keep working everywhere, including in anything new
you teach forge to generate.

## Pull requests

1. branch off `master` — `feat/…`, `fix/…`, `docs/…`;
2. make one coherent change; a refactor and a behaviour change in one diff is
   two PRs;
3. run `tests/smoke.sh` and paste the tail of it into the PR;
4. fill in the template: what changed, why, how you verified it, and whether an
   existing installation has to do anything to pick it up.

What gets a PR sent back, in rough order of frequency:

- a project name, stack, branch or command written into `template/`;
- a payload change with no smoke assertion;
- a validation rule changed in the script but not in `SCHEMA.md`, or vice versa;
- a third-party import anywhere in the hook path;
- a new runtime file missing from `package.json`'s `files`;
- a signature on something forge did not generate.

Small, obviously-correct PRs — a stack, a typo, a clearer sentence under
`template/` — do not need an issue first. Anything that changes a rule the
harness enforces should start as an issue, because the discussion is about
whether the rule is right, and that is cheaper before the diff exists.

## Releases

Maintainers only:

```bash
# bump VERSION in bin/forge and version in package.json to the same value
tests/smoke.sh
git commit -am "chore: releases X.Y.Z"
git tag vX.Y.Z && git push --follow-tags
npm publish            # prepublishOnly runs the smoke test again
```

Both channels ship the same files: the `~/.forge` git checkout follows the
pushed ref, the npm package follows the published version. `forge self-update`
branches on which one it is running from; keep both branches correct.

## Licence

MIT, and that covers `template/` too — the harness a project installs carries
the same terms. By contributing you agree your work ships under it. Installed
files get no licence header: they land in someone else's repository, where a
per-file banner would be noise.
