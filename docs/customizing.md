# Customizing a project's harness

Everything below is an edit to `forge.json` in the project, not to the harness.
After any of them, run:

```bash
python3 .claude/scripts/forge.py doctor
```

## Add a scope

```jsonc
"scopes": {
  "mobile": {
    "repo": "mobile",              // a key of `repos`, or null for a non-code scope
    "agent": "mobile-engineer",
    "kb_scope": "mobile",
    "stack": "Flutter 3, Dart",
    "workdir": "apps/mobile",
    "notes": "Golden tests regenerate with --update-goldens; never commit a stale golden."
  }
},
"checks": { "mobile": [ { "id": "tests", "title": "Tests",
                          "command": "flutter test", "cwd": "apps/mobile",
                          "available": true } ] },
"kb": { "scopes": ["api", "web", "mobile", "shared"] }
```

Then render the agent:

```bash
forge agents .            # writes .claude/agents/mobile-engineer.md
```

`doctor` will tell you if you forgot the agent file, the checks or the
knowledge-base scope.

## Make a check available

A check that does not exist yet still belongs in the matrix:

```jsonc
{ "id": "types", "title": "Types", "command": "mypy .", "cwd": "services/api",
  "available": false, "blocked_by": "TASK-0003", "note": "mypy is not configured yet" }
```

`qa` reports it as `SKIPPED (… — see TASK-0003)` rather than silently omitting
it. When TASK-0003 lands, flipping `"available"` to `true` is one of that
ticket's own acceptance criteria — the gate tightens itself as the tooling
arrives.

## Switch off a policy

```jsonc
"policy": {
  "test_first": true,          // the cycle's writing_tests stage
  "require_docs": true,        // the docs:/NO-DOCS gate at review
  "stale_claim_hours": 24      // when lint warns about an abandoned claim
},
"git": { "pull_requests": false }   // for a project that merges locally
```

`require_docs: false` turns the knowledge-base gate into a convention instead of
a check. Think twice: it is the gate that stops a codebase relearning the same
rule every quarter.

## Two repositories, or twenty

`repos` is a map of working trees. A monorepo declares one with `"path": "."`;
a super-repo declares itself plus one entry per submodule. Scopes that share a
repository share its working tree, and `lint` will not let two of them be in
flight at once — that is a property of git checkouts, not a policy you can
configure away.

## Move the tracker or the knowledge base

```jsonc
"paths": { "tracker": "docs/tracker", "kb": "docs/brain" }
```

Everything follows: the scripts, the hooks, the guards and the generated
indexes. Prose in the specs still says `docs/agile` in places — the scripts are
the authority.

## Disown a competing knowledge directory

If an org-wide plugin or another tool wants to write notes under a different
convention into the same repository, name its directory:

```jsonc
"kb": { "forbidden_dirs": ["docs/wiki"] }
```

A `PreToolUse` hook then denies every write there and explains which convention
this project actually uses. Two conventions over one kind of content is how a
knowledge base dies.

## Turn the attribution off

```jsonc
"attribution": false
```

forge puts one line with a link into the files it generates — both `INDEX.md`
boards, the managed `CLAUDE.md` block, the rendered agents. Setting this to
`false` and regenerating removes every instance; `forge.py credit` tells you
what the project currently signs with. Nothing forge did not write is ever
touched, so no ticket, note or commit carries it either way.

## Change what the agents are called

`agent` on a scope names the subagent file. Rename it, re-run `forge agents .`,
delete the old file, and update any ticket whose `assignee` still carries the
old name — `lint` will list them.
