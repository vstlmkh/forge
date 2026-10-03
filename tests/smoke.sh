#!/usr/bin/env bash
# End-to-end check of the harness: install it into a throwaway repo, file a
# ticket and a note through the scripts, and prove that every gate fires.
#
#   tests/smoke.sh [workdir]
#
# Exits non-zero on the first failed expectation.
set -u

FORGE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${1:-$(mktemp -d)}"
PASS=0
FAIL=0

ok()   { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL %s\n' "$1"; }
want() { # want <expected-rc> <label> -- <command...>
  local exp="$1" label="$2"; shift 3
  local out; out="$("$@" 2>&1)"; local rc=$?
  if [ "$rc" = "$exp" ]; then ok "$label (rc=$rc)"; else
    bad "$label (rc=$rc, expected $exp)"; printf '%s\n' "$out" | sed 's/^/       /'; fi
}

rm -rf "$WORK"; mkdir -p "$WORK"; cd "$WORK" || exit 1
git init -q .
git config user.email forge@example.com
git config user.name forge

echo "== install"
"$FORGE/bin/forge" init "$WORK" --preset monorepo --name "Smoke" >/dev/null || exit 1
"$FORGE/bin/forge" agents "$WORK" >/dev/null || exit 1
want 0 "forge doctor is clean" -- python3 .claude/scripts/forge.py doctor
[ -f CLAUDE.md ] && ok "CLAUDE.md written" || bad "CLAUDE.md missing"
[ -f .claude/agents/api-engineer.md ] && ok "engineer agent rendered" || bad "engineer agent missing"
grep -q "{{" .claude/agents/api-engineer.md && bad "unrendered placeholder left in agent" \
  || ok "no placeholders left in the rendered agent"

echo "== empty tracker"
want 0 "agile index on an empty tracker" -- python3 .claude/scripts/agile.py index
want 0 "kb index on an empty base" -- python3 .claude/scripts/kb.py index

echo "== artifacts"
TODAY=$(date +%F)
cat > docs/agile/backlog/EPIC-001-bootstrap.md <<EOT
---
id: EPIC-001
type: epic
title: Bootstrap the project
status: groomed
parent: null
priority: P2
scope: [api]
labels: []
created: $TODAY
updated: $TODAY
---

## Why

Something has to hold the first tasks.
EOT
cat > docs/agile/tasks/TASK-0001-first-task.md <<EOT
---
id: TASK-0001
type: task
title: Return a health endpoint
status: todo
parent: EPIC-001
scope: api
priority: P2
assignee: null
claimed_at: null
branch: null
pr: null
merge_sha: null
blocked_by: []
docs: []
docs_waiver: null
labels: []
created: $TODAY
updated: $TODAY
---

## Goal

Prove the pipeline end to end.

## Acceptance criteria

- [ ] GET /health returns 200 with {"status":"ok"}.

## Log
EOT
want 0 "a well-formed epic and task lint clean" -- python3 .claude/scripts/agile.py lint
want 0 "next-id advances" -- python3 .claude/scripts/agile.py next-id task
[ "$(python3 .claude/scripts/agile.py next-id task)" = "TASK-0002" ] \
  && ok "next-id is TASK-0002" || bad "next-id did not advance"

echo "== the docs gate"
python3 - <<'PY'
import re
p = "docs/agile/tasks/TASK-0001-first-task.md"
s = open(p).read().replace("status: todo", "status: review")
s = s.replace("branch: null", "branch: feat/health").replace("pr: null", "pr: https://example.com/pr/1")
s = s.replace("assignee: null", "assignee: qa").replace(
    "claimed_at: null", "claimed_at: 2026-10-03T10:00:00Z")
open(p, "w").write(s)
PY
OUT="$(python3 .claude/scripts/agile.py lint 2>&1)"; RC=$?
[ "$RC" = 2 ] && printf '%s' "$OUT" | grep -q "docs" \
  && ok "review with an empty docs: is rejected" \
  || { bad "the docs gate did not fire"; printf '%s\n' "$OUT" | sed 's/^/       /'; }

echo "== a knowledge-base note"
NOTE="$(python3 .claude/scripts/kb.py new business-rule api "health endpoint shape" \
        --ticket TASK-0001 --title "The health endpoint answers 200 with a status field" 2>/dev/null)"
[ -n "$NOTE" ] && ok "kb.py new created $NOTE" || bad "kb.py new produced nothing"
python3 - <<'PY'
import glob
p = glob.glob("docs/knowledge/api/business-rule/*.md")[0]
s = open(p).read()
s = s.replace("_State the rule as an imperative the code must obey. One rule per note._",
              "GET /health answers 200 and a JSON body carrying a `status` field.")
s = s.replace("_The product or legal reason. Without this the rule reads as an accident and gets refactored away._",
              "The load balancer removes an instance that answers anything else.")
s = s.replace("_The file and the layer that enforces it, and the test that guards it - or the fact that nothing does._",
              "services/api/routes/health.py, guarded by services/api/tests/test_health.py.")
open(p, "w").write(s)

t = "docs/agile/tasks/TASK-0001-first-task.md"
s = open(t).read().replace("docs: []",
    "docs:\n  - " + p.split("docs/knowledge/", 1)[1])
open(t, "w").write(s)
PY
want 0 "the ticket and the note now lint clean" -- python3 .claude/scripts/agile.py lint
want 0 "the knowledge base lints clean" -- python3 .claude/scripts/kb.py lint
want 0 "for-ticket resolves the note" -- python3 .claude/scripts/kb.py for-ticket TASK-0001
want 0 "find hits the note" -- python3 .claude/scripts/kb.py find health
want 2 "find reports a gap as exit 2" -- python3 .claude/scripts/kb.py find nonexistentsubject

echo "== generated indexes are byte-stable"
python3 .claude/scripts/agile.py index >/dev/null
cp docs/agile/INDEX.md /tmp/forge-index-a
python3 .claude/scripts/agile.py index >/dev/null
cmp -s /tmp/forge-index-a docs/agile/INDEX.md && ok "agile index is byte-stable" \
  || bad "agile index is not byte-stable"

echo "== hooks"
hook() { printf '%s' "$2" | python3 ".claude/scripts/$1" >/dev/null 2>&1; echo $?; }
[ "$(hook guard-index.py '{"tool_input":{"file_path":"docs/agile/INDEX.md"}}')" = 2 ] \
  && ok "guard-index denies editing the board" || bad "guard-index let the board through"
[ "$(hook guard-index.py '{"tool_input":{"file_path":"docs/agile/tasks/TASK-0001-first-task.md"}}')" = 0 ] \
  && ok "guard-index allows a ticket" || bad "guard-index blocked a ticket"
[ "$(hook guard-kb.py '{"tool_input":{"file_path":"docs/knowledge/api/business-rule/notes.md"}}')" = 2 ] \
  && ok "guard-kb denies a misnamed note" || bad "guard-kb allowed a misnamed note"
[ "$(hook guard-kb.py '{"tool_input":{"file_path":"docs/knowledge/nope/business-rule/{business-rule} x y - 2026-10-03.md"}}')" = 2 ] \
  && ok "guard-kb denies an unknown scope" || bad "guard-kb allowed an unknown scope"
[ "$(hook guard-kb.py '{"tool_input":{"file_path":"docs/agile/tasks/TASK-0009-new.md","content":"---\nid: TASK-0009\n---\n"}}')" = 2 ] \
  && ok "guard-kb denies a new ticket with no docs:" || bad "guard-kb allowed a ticket with no docs:"

echo "== detection and --auto"
FIX="$WORK/../forge-smoke-fixture-$$"
rm -rf "$FIX"; mkdir -p "$FIX/apps/web" "$FIX/services/api"
git -C "$FIX" init -q
cat > "$FIX/apps/web/package.json" <<'EOT'
{"name":"web","scripts":{"test":"jest","tsc":"tsc --noEmit","build":"next build"},
 "dependencies":{"next":"16.0.0"},"devDependencies":{"typescript":"5.6.0"}}
EOT
cat > "$FIX/services/api/pyproject.toml" <<'EOT'
[project]
name = "api"
dependencies = ["fastapi"]
[dependency-groups]
dev = ["pytest", "ruff"]
EOT
OUT="$("$FORGE/bin/forge" detect "$FIX" 2>&1)"
printf '%s' "$OUT" | grep -q "scope web" && printf '%s' "$OUT" | grep -q "scope api"   && ok "detect finds both parts of a mixed monorepo"   || { bad "detect missed a scope"; printf '%s\n' "$OUT" | sed 's/^/       /'; }
printf '%s' "$OUT" | grep -q "npm test" && printf '%s' "$OUT" | grep -q "pytest -q"   && ok "detect reads the real test commands" || bad "detect invented or missed a command"

"$FORGE/bin/forge" init "$FIX" --auto --name Fixture >/dev/null 2>&1
( cd "$FIX" && want 0 "a repo initialised with --auto passes doctor" -- \
    python3 .claude/scripts/forge.py doctor )
[ -f "$FIX/.claude/agents/web-engineer.md" ] && [ -f "$FIX/.claude/agents/api-engineer.md" ] \
  && ok "--auto renders an agent per detected scope" || bad "--auto skipped an agent"

echo "== submodule layout"
SUB="$WORK/../forge-smoke-sub-$$"
rm -rf "$SUB"; mkdir -p "$SUB/backend/app" "$SUB/frontend"
git -C "$SUB" init -q
printf '[submodule "backend"]\n\tpath = backend\n\turl = git@example.com:a/b.git\n' > "$SUB/.gitmodules"
echo '{"name":"b","scripts":{"test":"phpunit"}}' > "$SUB/backend/app/composer.json"
OUT="$("$FORGE/bin/forge" detect "$SUB" 2>&1)"
printf '%s' "$OUT" | grep -q "super-repo with submodules" \
  && ok "detect recognises a super-repo" || bad "detect missed the submodules"
printf '%s' "$OUT" | grep -q "backend/app" \
  && ok "detect finds an application nested inside a submodule" \
  || bad "detect did not look inside the submodule"

echo "== installer"
INST="$WORK/../forge-smoke-install-$$"
rm -rf "$INST"
FORGE_REPO="$FORGE" FORGE_HOME="$INST/.forge" FORGE_BIN="$INST/bin" \
  sh "$FORGE/install.sh" >/dev/null 2>&1
[ -L "$INST/bin/forge" ] && ok "installer links a shim onto the bin dir" \
  || bad "installer did not create the shim"
[ "$("$INST/bin/forge" version 2>/dev/null)" = "$("$FORGE/bin/forge" version)" ] \
  && ok "the shim runs, and finds template/ through the symlink" \
  || bad "the shim could not run"
FORGE_REPO="$FORGE" FORGE_HOME="$INST/.forge" FORGE_BIN="$INST/bin" \
  sh "$FORGE/install.sh" >/dev/null 2>&1 \
  && ok "re-running the installer updates in place" || bad "the installer is not re-runnable"
rm -rf "$FIX" "$SUB" "$INST"

echo
echo "passed $PASS, failed $FAIL   (workdir: $WORK)"
[ "$FAIL" = 0 ]
