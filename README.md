# forge

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
  <img alt="forge — the cycle a ticket goes through, and the three records behind it" src="assets/banner-light.svg">
</picture>

A reusable agent harness for software projects: a test-first development cycle,
a Markdown tracker, a typed knowledge base, four role agents and the hooks that
keep all of it honest — installable into any repository in one command.

## Install

```bash
gh api repos/vstlmkh/forge/contents/install.sh -H "Accept: application/vnd.github.raw" | sh
```

or, if you would rather clone first:

```bash
git clone https://github.com/vstlmkh/forge.git ~/.forge && ~/.forge/install.sh
```

The repository is **private**, which rules out the usual
`curl … raw.githubusercontent.com/… | sh`: raw URLs do not see your git
credentials and answer 404. `gh api` authenticates over the API, and a plain
`git clone` over https works through whatever credential helper already holds
your token. Once the repository is public, the short form works too:

```bash
curl -fsSL https://raw.githubusercontent.com/vstlmkh/forge/master/install.sh | sh
```

One git checkout in `~/.forge`, one `forge` shim in `~/.local/bin`, no packages,
nothing compiled. Re-run the installer any time to update, or run
`forge self-update`. `FORGE_HOME`, `FORGE_BIN`, `FORGE_REF` and `FORGE_REPO`
override where it lands, which ref it tracks and where it clones from.

**On a machine with several GitHub accounts**, `gh repo clone` and
`git@github.com:…` both fail with *Repository not found*: they use the default
ssh key, which belongs to another account. The installer handles it — it tries
https, then `git@github.com`, then every `Host` alias in `~/.ssh/config` whose
`HostName` is `github.com`, and tells you which one worked. Nothing ever waits
on a credential prompt, so piping it into `sh` cannot hang.

## Use it in a project

```bash
cd /path/to/your/project
forge detect        # what forge thinks this repository is made of
forge init --auto   # install the harness from exactly that, asking nothing
```

`detect` reads `.gitmodules`, then looks for `package.json`, `pyproject.toml`,
`composer.json`, `go.mod`, `Cargo.toml` and `pubspec.yaml` — including one level
inside a submodule, where deployment repositories usually keep the application.
Out of that come the repositories, the scopes, a stack label and the real test,
lint, type and build commands the project already has. It guesses that those
commands work; `forge doctor` and you decide whether they do.

`forge init` without `--auto` asks instead — it still opens with what it
detected, so the usual answer is "yes, that's right".

Either way it writes `forge.json`, copies the harness into `.claude/`, scaffolds
`docs/agile/` and `docs/knowledge/`, renders one engineer agent per scope, and
adds a managed block to your `CLAUDE.md`. Nothing else in the project is
touched.

## What you get

| Piece | What it is |
|---|---|
| `docs/agile/` | backlog, task tracker and bug tracker as Markdown with YAML frontmatter; `INDEX.md` is generated |
| `docs/knowledge/` | eight-type knowledge base — business rules, incidents, decisions, contracts — with a generated coverage index |
| `.claude/agents/` | `pm`, `qa`, and one engineer per code scope |
| `.claude/skills/` | the operating rules: artifacts, grooming, git, Definition of Done, knowledge |
| `.claude/commands/` | `/agile:*`, `/kb:*`, `/forge:doctor` |
| `.claude/scripts/` | `agile.py`, `kb.py`, `forge.py` and four hooks — stdlib-only Python 3, no dependencies |
| `forge.json` | **the only project-specific file**: repositories, scopes, owning agents, and the Definition-of-Done matrix |

## The cycle it enforces

Four properties are load-bearing, and all four are checked by a script rather
than trusted:

- **Test-first.** `qa` writes a failing test per acceptance criterion and proves
  it red *before* an engineer starts. There is no `todo -> in_progress`.
- **The tests are not the implementer's.** At the review gate `qa` diffs the test
  files against its own red commit; a loosened matcher or a deleted assertion is
  a rejection.
- **Nobody closes their own work.** An engineer stops at `review`, `qa` moves it
  to `verify`, and only the top-level session sets `done`.
- **A gap is named, not hidden.** `SKIPPED`, `NO-TEST` and `NO-DOCS` are the
  three waivers; each one must name what it falls back on, and `lint` refuses a
  ticket that reaches review having recorded neither a note nor a reason.

## Everything project-specific lives in `forge.json`

```jsonc
{
  "repos":  { "backend": { "path": "backend", "branch": "master", "submodule": true } },
  "scopes": { "backend": { "repo": "backend", "agent": "backend-engineer",
                           "kb_scope": "backend", "stack": "Laravel 11",
                           "workdir": "backend/app" } },
  "checks": { "backend": [ { "id": "tests", "command": "composer test",
                             "cwd": "backend/app", "available": true } ] }
}
```

The scripts, skills, agents and commands read it; none of them hardcode a scope,
a branch or a command. That is what makes the same harness fit a one-repository
service and a super-repo with submodules, and what lets the Definition-of-Done
matrix tighten itself: when a bootstrap ticket makes `mypy` real, flipping
`"available": false` to `true` is part of that ticket's acceptance criteria.

```bash
python3 .claude/scripts/forge.py scopes        # who implements what, and where
python3 .claude/scripts/forge.py checks api    # the matrix qa is bound by
python3 .claude/scripts/forge.py doctor        # does the config match the repo?
```

## Commands in a project that has the harness

```
/agile:board            what is going on
/agile:groom <request>  turn a request into tickets
/agile:next             what to work on
/agile:work <ID>        QA writes failing tests → implement → QA reviews, stops at verify
/agile:close <ID>       merge, record the sha, close
/agile:bug <symptom>    file and triage a defect

/kb:consult <subject>   what do we already know?
/kb:new <finding>       file it, correctly typed and cross-linked
/kb:audit               gaps, misfilings, staleness, broken links
/forge:doctor           does the harness still match the repository?
```

## CLI

```
forge detect [TARGET]    print the shape forge infers, and change nothing
forge init [TARGET]      install — interactively, or --auto, or --preset NAME
forge agents [TARGET]    re-render the per-scope engineer agents from forge.json
forge upgrade [TARGET]   refresh scripts, skills, commands and specs in place
forge doctor [TARGET]    run the installed harness's self-check
forge self-update        pull the newest forge into ~/.forge
forge where              print where forge is installed
```

`upgrade` never touches `forge.json` or a rendered agent (pass `--agents` to
re-render those too), and rewrites only the `<!-- forge:begin -->` block in
`CLAUDE.md`. Running it twice leaves a zero diff.

## Repository layout

```
forge/
├── install.sh             clones into ~/.forge and links the shim; re-run to update
├── bin/forge              the CLI: detect, init, agents, upgrade, doctor
├── assets/banner.py       regenerates the two README banners
├── template/              the payload that gets copied into a project
│   ├── .claude/           agents, skills, commands, scripts, settings
│   ├── docs/              the tracker and knowledge-base specifications
│   ├── CLAUDE.harness.md.tmpl
│   └── forge.example.*.json
├── docs/                  how the harness works and how to extend it
├── tests/smoke.sh         installs into a throwaway repo and proves every gate fires
└── LICENSE                MIT
```

## Requirements

Python 3.9+ and git. No third-party packages, at install time or afterwards —
the hooks run on every turn, so the harness refuses to own a dependency tree.
Updating forge never touches a project: a project picks up a new version when
you run `forge upgrade` in it.

## Tests

```bash
tests/smoke.sh
```

Installs into a temporary repository, files a ticket and a note through the
scripts, and asserts that each gate fires: the docs gate, the knowledge-base
naming guard, the generated-index guard, the byte-stability of both indexes, and
the one-working-tree rule.

## Attribution

forge signs the files it generates — the two `INDEX.md` boards, the managed
`CLAUDE.md` block, the rendered engineer agents — with one line and a link:

```markdown
_Kept by [forge](https://github.com/vstlmkh/forge)._
```

It signs nothing else. Not a commit, not a pull request, not a ticket, not a
knowledge-base note, not a file anyone on the project wrote. The line is plain
visible text, because the only honest mark to leave in somebody else's
repository is one they can read and delete — and a hidden one in a client
codebase is a liability for whoever installed it.

Turn it off entirely with `forge init --no-attribution`, or later:

```jsonc
{ "attribution": false }     // in forge.json; regenerate and every instance is gone
```

```bash
python3 .claude/scripts/forge.py credit   # what this project signs with, if anything
```

## License

MIT — see [LICENSE](LICENSE).

That covers everything under `template/` too, so the harness a project installs
carries the same terms. Installed files get no licence header: they land in
someone else's repository, and a per-file banner there would be noise.
