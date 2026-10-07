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
skip() { printf '  SKIP %s\n' "$1"; }   # never a pass - the harness's own rule
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
spec: null
spec_waiver: null
docs: []
docs_waiver: null
labels: []
created: $TODAY
updated: $TODAY
---

## Goal

Prove the pipeline end to end.

## Acceptance criteria

- [ ] (REQ-0001) GET /health returns 200 with {"status":"ok"}.

## Log
EOT
want 0 "a well-formed epic and task lint clean" -- python3 .claude/scripts/agile.py lint
want 0 "next-id advances" -- python3 .claude/scripts/agile.py next-id task
[ "$(python3 .claude/scripts/agile.py next-id task)" = "TASK-0002" ] \
  && ok "next-id is TASK-0002" || bad "next-id did not advance"

echo "== the spec gate"
[ -d docs/agile/specs ] && ok "init creates the specs directory" || bad "no docs/agile/specs/"

# a ticket may not reach writing_tests unspecified
python3 - <<'PY2'
t = "docs/agile/tasks/TASK-0001-first-task.md"
s = open(t).read().replace("status: todo", "status: writing_tests")
s = s.replace("assignee: null", "assignee: qa")
open(t, "w").write(s)
PY2
OUT="$(python3 .claude/scripts/agile.py lint 2>&1)"; RC=$?
[ "$RC" = 2 ] && printf '%s' "$OUT" | grep -q "spec" \
  && ok "writing_tests without a spec is rejected" \
  || { bad "the spec gate did not fire"; printf '%s\n' "$OUT" | sed 's/^/       /'; }

want 1 "spec new refuses an unknown ticket" -- python3 .claude/scripts/agile.py spec new TASK-9999
want 0 "spec new scaffolds the spec" -- python3 .claude/scripts/agile.py spec new TASK-0001
[ -f docs/agile/specs/TASK-0001.md ] && ok "the spec file exists" || bad "spec new wrote nothing"
want 3 "spec new refuses to clobber" -- python3 .claude/scripts/agile.py spec new TASK-0001
want 2 "a skeleton spec is not agreed" -- python3 .claude/scripts/agile.py spec check TASK-0001
[ "$(python3 .claude/scripts/agile.py next-req TASK-0001)" = "REQ-0001" ] \
  && ok "next-req starts at REQ-0001" || bad "next-req did not start at REQ-0001"

# fill the brief the way qa would at gate 1, and point the ticket at it
python3 - <<'PY2'
p = "docs/agile/specs/TASK-0001.md"
s = open(p).read()
s = s.replace("status: drafting", "status: agreed")
s = s.replace(
    "| _REQ-0001_ | _what must be true when this is done_ | _question_ "
    "| _user / kb:<note> / code:<path:line>_ |",
    "| REQ-0001 | GET /health answers 200 with a status field. | agreed | user |\n"
    "| REQ-0002 | It answers within 50ms. | deferred | user |")
s = s.replace("| Q1 | REQ-0001 | _the question_ | _filled in when the user answers_ |",
              "| Q1 | REQ-0001 | Which status code? | 200. |")
s = s.replace("| ID | Deferred because | Becomes |\n|---|---|---|\n",
              "| ID | Deferred because | Becomes |\n|---|---|---|\n"
              "| REQ-0002 | no load harness yet | NO-TICKET (measured elsewhere) |\n")
s = s.replace("_Behaviour, boundaries and contracts, written against the REQ ids above. Say\n"
              "what is explicitly out of scope - that is what stops the ticket growing._",
              "GET /health answers 200 and a JSON body carrying a status field. "
              "Latency is out of scope.")
open(p, "w").write(s)

t = "docs/agile/tasks/TASK-0001-first-task.md"
s = open(t).read().replace("spec: null", "spec: specs/TASK-0001.md")
open(t, "w").write(s)
PY2
want 0 "a filled, agreed spec checks clean" -- python3 .claude/scripts/agile.py spec check TASK-0001
[ "$(python3 .claude/scripts/agile.py next-req TASK-0001)" = "REQ-0003" ] \
  && ok "next-req advances past the brief" || bad "next-req did not advance"

# a brief nothing traces back to is decoration
sed -i.bak 's/- \[ \] (REQ-0001) GET/- [ ] GET/' docs/agile/tasks/TASK-0001-first-task.md
OUT="$(python3 .claude/scripts/agile.py lint 2>&1)"; RC=$?
[ "$RC" = 2 ] && printf '%s' "$OUT" | grep -q "REQ-0001" \
  && ok "an untagged acceptance criterion is rejected" \
  || { bad "the traceability rule did not fire"; printf '%s\n' "$OUT" | sed 's/^/       /'; }
mv docs/agile/tasks/TASK-0001-first-task.md.bak docs/agile/tasks/TASK-0001-first-task.md

# an orphan spec outlives a ticket that was renamed or deleted
cp docs/agile/specs/TASK-0001.md docs/agile/specs/TASK-0404.md
OUT="$(python3 .claude/scripts/agile.py lint 2>&1)"; RC=$?
[ "$RC" = 2 ] && printf '%s' "$OUT" | grep -q "TASK-0404" \
  && ok "an orphan spec is rejected" || bad "the orphan spec was accepted"
rm -f docs/agile/specs/TASK-0404.md

# back to todo so the docs gate below starts where it used to
python3 - <<'PY2'
t = "docs/agile/tasks/TASK-0001-first-task.md"
s = open(t).read().replace("status: writing_tests", "status: todo")
s = s.replace("assignee: qa", "assignee: null")
open(t, "w").write(s)
PY2
want 0 "the specified ticket lints clean again" -- python3 .claude/scripts/agile.py lint

echo "== the gates and the handoff payload"
want 1 "gates refuses a gate that does not exist" -- python3 .claude/scripts/agile.py gates 9
[ "$(python3 .claude/scripts/agile.py gates | grep -c '^Gate')" = 6 ] \
  && ok "there are six gates" || bad "the gate table is not six rows"
want 1 "handoff needs a gate" -- python3 .claude/scripts/agile.py handoff TASK-0001
want 0 "handoff renders gate 1" -- python3 .claude/scripts/agile.py handoff TASK-0001 --gate 1
want 2 "handoff refuses a gate the ticket cannot reach" -- \
  python3 .claude/scripts/agile.py handoff TASK-0001 --gate 4
OUT="$(python3 .claude/scripts/agile.py handoff TASK-0001 --gate 1)"
printf '%s' "$OUT" | head -2 | grep -q "GATE 1" \
  && ok "the contract opens the payload" || bad "handoff buried the contract"
printf '%s' "$OUT" | head -20 | grep -q "MUST NOT" \
  && ok "the prohibitions are in the first screen" || bad "the prohibitions are not up front"
printf '%s' "$OUT" | tail -20 | grep -q "ANCHOR" \
  && ok "the contract is repeated in the last screen" || bad "handoff lost the anchor"
# nothing inert may follow the anchor - that is the whole layout rule
printf '%s' "$OUT" | sed -n '/=== ANCHOR/,$p' | grep -qE '^--- (reference|steps)' \
  && bad "reference material follows the anchor" \
  || ok "the anchor is the last thing in the payload"
printf '%s' "$OUT" | grep -q "api" \
  && ok "handoff reads the scope from forge.json" || bad "handoff did not resolve the scope"
printf '%s' "$OUT" | grep -q "Prove the pipeline end to end" \
  && bad "handoff pasted the ticket body instead of its path" \
  || ok "handoff carries paths, not pasted file bodies"

echo "== the docs gate"
# a claim made now, not a literal date - a hardcoded one ages past
# stale_claim_hours and turns this fixture into a time bomb
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)" python3 - <<'PY'
import os
p = "docs/agile/tasks/TASK-0001-first-task.md"
s = open(p).read().replace("status: todo", "status: review")
s = s.replace("branch: null", "branch: feat/health").replace("pr: null", "pr: https://example.com/pr/1")
s = s.replace("assignee: null", "assignee: qa").replace(
    "claimed_at: null", "claimed_at: " + os.environ["NOW"])
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

echo "== lessons"
[ -f docs/lessons/README.md ] && ok "init installs the lessons convention" \
  || bad "docs/lessons/README.md missing"
want 0 "lessons.py roles prints the vocabulary" -- python3 .claude/scripts/lessons.py roles
python3 .claude/scripts/lessons.py for api-engineer | grep -q "none recorded yet" \
  && ok "an empty layer costs one line" || bad "the empty hand-off is not silent"

L1="$(python3 .claude/scripts/lessons.py new "migration check before pr" \
      --scope api --roles engineer --gate 3 --ticket TASK-0001 \
      --rule "Run every available check before asking for review, not after review asks." 2>/dev/null)"
[ -n "$L1" ] && ok "lessons.py new created $L1" || bad "lessons.py new produced nothing"
[ -f "docs/lessons/api/LESSON-0001 migration check before pr.md" ] \
  && ok "the id leads the filename" || bad "the lesson is not where the convention says"
want 2 "a skeleton body is rejected" -- python3 .claude/scripts/lessons.py lint

python3 - <<'PY2'
import glob
p = glob.glob("docs/lessons/api/*.md")[0]
s = open(p).read()
for frag, real in [
    ("_The failure this prevents", "The PR sat for a day while review ran the check the author had not."),
    ("_What to do differently", "`forge.py checks <scope>`, every available row, before the PR is opened."),
    ("_The ticket and the gate", "- TASK-0001, gate 3: review bounced it for an unrun check."),
]:
    line = next(l for l in s.splitlines() if l.startswith(frag))
    s = s.replace(line, real)
open(p, "w").write(s)
PY2
want 0 "a filled lesson lints clean" -- python3 .claude/scripts/lessons.py lint
python3 .claude/scripts/lessons.py for api-engineer | grep -q "LESSON-0001" \
  && ok "the engineer is handed its scope's rule" || bad "the hand-off missed the rule"
python3 .claude/scripts/lessons.py for pm | grep -q "none recorded yet" \
  && ok "a rule addressed to engineers does not reach pm" || bad "roles are not filtered"
python3 .claude/scripts/lessons.py for qa --scope api | grep -q "none recorded yet" \
  && ok "roles filter independently of scope" || bad "qa was handed an engineer rule"

L2="$(python3 .claude/scripts/lessons.py new "waiver wording" --scope all --roles all \
      --rule "Record a skipped check as SKIPPED with its reason and ticket, never as a pass." \
      --ticket TASK-0001 2>/dev/null)"
python3 - <<'PY2'
import glob
p = [x for x in glob.glob("docs/lessons/all/*.md")][0]
s = open(p).read()
for frag, real in [
    ("_The failure this prevents", "A silently omitted row reads as a pass and the gate stops meaning anything."),
    ("_What to do differently", "Write `SKIPPED (<reason> - see TASK-000X)` in the verdict."),
    ("_The ticket and the gate", "- TASK-0001, gate 5: a row was omitted rather than recorded."),
]:
    line = next(l for l in s.splitlines() if l.startswith(frag))
    s = s.replace(line, real)
open(p, "w").write(s)
PY2
want 0 "two lessons lint clean" -- python3 .claude/scripts/lessons.py lint
[ "$(python3 .claude/scripts/lessons.py for api-engineer | grep -c '^  LESSON-')" = 2 ] \
  && ok "scope 'all' reaches every engineer" || bad "the 'all' scope did not reach the engineer"
OUT="$(python3 .claude/scripts/lessons.py for api-engineer --budget 1)"
printf '%s' "$OUT" | grep -q "withheld" \
  && ok "the budget caps the hand-off and says what it withheld" \
  || bad "the budget truncated in silence"
[ "$(printf '%s' "$OUT" | grep -c '^  LESSON-')" = 1 ] \
  && ok "the budget is a hard cap" || bad "the budget did not cap"

want 0 "confirm bumps the counter" -- python3 .claude/scripts/lessons.py confirm LESSON-0002
grep -q "confirmations: 1" docs/lessons/all/*.md \
  && ok "the confirmation is written back" || bad "confirm did not persist"
[ "$(python3 .claude/scripts/lessons.py for api-engineer --budget 1 | grep '^  LESSON-')" \
  = "$(printf '  LESSON-0002  Record a skipped check as SKIPPED with its reason and ticket, never as a pass.')" ] \
  && ok "a confirmed rule outranks an unconfirmed one" || bad "confirmations do not rank"

want 1 "a rule may not supersede itself" -- \
  python3 .claude/scripts/lessons.py supersede LESSON-0001 --by LESSON-0001
want 0 "supersede records the replacement" -- \
  python3 .claude/scripts/lessons.py supersede LESSON-0001 --by LESSON-0002
python3 .claude/scripts/lessons.py for api-engineer | grep -q "LESSON-0001" \
  && bad "a superseded rule is still handed out" || ok "a superseded rule leaves the hand-off"
want 0 "the layer lints clean after supersession" -- python3 .claude/scripts/lessons.py lint

# the two limits that keep this layer affordable
python3 - <<'PY2'
import glob
p = glob.glob("docs/lessons/all/*.md")[0]
s = open(p).read()
old = next(l for l in s.splitlines() if l.startswith("rule: "))
open(p, "w").write(s.replace(old, "rule: " + "x" * 130))
PY2
OUT="$(python3 .claude/scripts/lessons.py lint 2>&1)"
printf '%s' "$OUT" | grep -q "rule" \
  && ok "a rule that does not fit on a line is rejected" || bad "the rule limit does not fire"
python3 - <<'PY2'
import glob
p = glob.glob("docs/lessons/all/*.md")[0]
s = open(p).read()
old = next(l for l in s.splitlines() if l.startswith("rule: "))
open(p, "w").write(s.replace(old,
    "rule: Record a skipped check as SKIPPED with its reason and ticket, never as a pass."))
PY2

want 0 "lessons index writes" -- python3 .claude/scripts/lessons.py index
cp docs/lessons/INDEX.md /tmp/forge-lessons-a
python3 .claude/scripts/lessons.py index >/dev/null
cmp -s /tmp/forge-lessons-a docs/lessons/INDEX.md && ok "lessons index is byte-stable" \
  || bad "lessons index is not byte-stable"

echo "== the carryover gate"
# at verify, every deferred requirement must have become a ticket or an argument
python3 - <<'PY2'
t = "docs/agile/tasks/TASK-0001-first-task.md"
text = open(t).read().replace("status: review", "status: verify")
open(t, "w").write(text)
p = "docs/agile/specs/TASK-0001.md"
text = open(p).read().replace("NO-TICKET (measured elsewhere)", "")
open(p, "w").write(text)
PY2
OUT="$(python3 .claude/scripts/agile.py lint 2>&1)"; RC=$?
[ "$RC" = 2 ] && printf '%s' "$OUT" | grep -q "REQ-0002" \
  && ok "a carryover row with no ticket blocks verify" \
  || { bad "the carryover gate did not fire"; printf '%s\n' "$OUT" | sed 's/^/       /'; }
python3 - <<'PY2'
p = "docs/agile/specs/TASK-0001.md"
text = open(p).read().replace(
    "| REQ-0002 | no load harness yet |  |",
    "| REQ-0002 | no load harness yet | NO-TICKET (measured elsewhere) |")
open(p, "w").write(text)
t = "docs/agile/tasks/TASK-0001-first-task.md"
text = open(t).read().replace("status: verify", "status: review")
open(t, "w").write(text)
PY2
want 0 "an argued NO-TICKET clears it" -- python3 .claude/scripts/agile.py lint

echo "== the role agents are rendered"
for a in pm qa qa-spec; do
  [ -f ".claude/agents/$a.md" ] && ok "$a is rendered" || bad "$a is missing"
  grep -q "{{" ".claude/agents/$a.md" && bad "unrendered placeholder in $a" \
    || ok "no placeholders left in $a"
done
grep -q "^model: opus" .claude/agents/qa-spec.md \
  && ok "qa-spec takes its model from policy.models" \
  || bad "qa-spec did not get its model"
python3 - <<'PY2'
import json
c = json.load(open("forge.json"))
c.setdefault("policy", {}).setdefault("models", {})["qa"] = "haiku"
json.dump(c, open("forge.json", "w"), indent=2)
PY2
"$FORGE/bin/forge" agents "$WORK" --force >/dev/null 2>&1
grep -q "^model: haiku" .claude/agents/qa.md \
  && ok "policy.models overrides a role's model" || bad "policy.models was ignored"
python3 - <<'PY2'
import json
c = json.load(open("forge.json"))
c["policy"]["models"].pop("qa")
json.dump(c, open("forge.json", "w"), indent=2)
PY2
"$FORGE/bin/forge" agents "$WORK" --force >/dev/null 2>&1

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
[ "$(hook guard-index.py '{"tool_input":{"file_path":"docs/lessons/INDEX.md"}}')" = 2 ] \
  && ok "guard-index denies editing the lessons index" || bad "guard-index let the lessons index through"
[ "$(hook guard-index.py '{"tool_input":{"file_path":"docs/agile/tasks/TASK-0001-first-task.md"}}')" = 0 ] \
  && ok "guard-index allows a ticket" || bad "guard-index blocked a ticket"
[ "$(hook guard-kb.py '{"tool_input":{"file_path":"docs/knowledge/api/business-rule/notes.md"}}')" = 2 ] \
  && ok "guard-kb denies a misnamed note" || bad "guard-kb allowed a misnamed note"
[ "$(hook guard-kb.py '{"tool_input":{"file_path":"docs/knowledge/nope/business-rule/{business-rule} x y - 2026-10-03.md"}}')" = 2 ] \
  && ok "guard-kb denies an unknown scope" || bad "guard-kb allowed an unknown scope"
[ "$(hook guard-kb.py '{"tool_input":{"file_path":"docs/agile/tasks/TASK-0009-new.md","content":"---\nid: TASK-0009\nspec: null\n---\n"}}')" = 2 ] \
  && ok "guard-kb denies a new ticket with no docs:" || bad "guard-kb allowed a ticket with no docs:"
[ "$(hook guard-kb.py '{"tool_input":{"file_path":"docs/agile/tasks/TASK-0009-new.md","content":"---\nid: TASK-0009\ndocs: []\n---\n"}}')" = 2 ] \
  && ok "guard-kb denies a new ticket with no spec:" || bad "guard-kb allowed a ticket with no spec:"
[ "$(hook guard-kb.py '{"tool_input":{"file_path":"docs/agile/specs/notes.md"}}')" = 2 ] \
  && ok "guard-kb denies a misnamed spec" || bad "guard-kb allowed a misnamed spec"
[ "$(hook guard-kb.py '{"tool_input":{"file_path":"docs/agile/specs/TASK-0404.md"}}')" = 2 ] \
  && ok "guard-kb denies a spec for a ticket that does not exist" \
  || bad "guard-kb allowed an orphan spec"
[ "$(hook guard-kb.py '{"tool_input":{"file_path":"docs/agile/specs/TASK-0001.md"}}')" = 0 ] \
  && ok "guard-kb allows a real spec" || bad "guard-kb blocked a real spec"

echo "== upgrading a board that predates the spec gate"
OLD="$WORK/../forge-smoke-legacy-$$"
rm -rf "$OLD"; mkdir -p "$OLD"; (cd "$OLD" && git init -q .)
"$FORGE/bin/forge" init "$OLD" --preset monorepo --name Legacy >/dev/null 2>&1
  cd "$OLD" || exit 1
  cp "$WORK/docs/agile/backlog/EPIC-001-bootstrap.md" docs/agile/backlog/
  # a ticket written before `spec:` existed, caught mid-flight by the upgrade
  cat > docs/agile/tasks/TASK-0001-legacy.md <<EOT
---
id: TASK-0001
type: task
title: Written before the spec gate existed
status: in_progress
parent: EPIC-001
scope: api
priority: P2
assignee: api-engineer
claimed_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
branch: feat/legacy
pr: null
merge_sha: null
blocked_by: []
docs: []
docs_waiver: NO-DOCS (a fixture)
labels: []
created: $TODAY
updated: $TODAY
---

## Goal

Exist.

## Acceptance criteria

- [ ] it works

## Log

- $TODAY opened before the gate
EOT
  python3 - <<'PY2'
import json
c = json.load(open("forge.json"))
c["policy"].pop("spec_first", None)      # as an older forge.json would be
json.dump(c, open("forge.json", "w"), indent=2)
PY2
  "$FORGE/bin/forge" upgrade . >/dev/null 2>&1
  SF="$(python3 -c 'import json;print(json.load(open("forge.json"))["policy"]["spec_first"])')"
  [ "$SF" = "False" ] && ok "upgrade leaves the gate off while tickets are in flight" \
    || bad "upgrade turned the spec gate on under a live board (spec_first=$SF)"
  OUT="$(python3 .claude/scripts/agile.py lint 2>&1)"; RC=$?
  [ "$RC" != 1 ] && ! printf '%s' "$OUT" | grep -q "ERROR" \
    && ok "a pre-gate board still lints without errors" \
    || { bad "upgrading broke a healthy board"; printf '%s\n' "$OUT" | sed 's/^/       /'; }
  printf '%s' "$OUT" | grep -q "spec_first" \
    && ok "lint says what turning the gate on would cost" \
    || bad "lint is silent about the disabled gate"
  python3 .claude/scripts/forge.py doctor 2>&1 | grep -q "spec_first" \
    && ok "doctor keeps asking for the gate to be turned on" \
    || bad "doctor does not mention the disabled gate"
  [ -d docs/agile/specs ] && ok "upgrade creates specs/ in an existing project" \
    || bad "upgrade did not create specs/"
cd "$WORK" || exit 1
rm -rf "$OLD"

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

echo "== attribution"
grep -q "github.com/vstlmkh/forge" docs/agile/INDEX.md \
  && ok "the generated board carries the forge line" || bad "the board is unsigned"
grep -q "github.com/vstlmkh/forge" docs/knowledge/INDEX.md \
  && ok "the generated knowledge index carries it too" || bad "the knowledge index is unsigned"
grep -q "github.com/vstlmkh/forge" CLAUDE.md \
  && ok "the managed CLAUDE.md block carries it" || bad "the CLAUDE.md block is unsigned"
grep -q "github.com/vstlmkh/forge" .claude/agents/api-engineer.md \
  && ok "a rendered agent says what generated it" || bad "the rendered agent is unsigned"
for f in docs/agile/tasks/TASK-0001-first-task.md docs/agile/SCHEMA.md; do
  grep -q "github.com/vstlmkh/forge" "$f" && bad "forge signed $f, which it does not generate"
done
ok "nothing forge did not generate was signed"

OFF="$WORK/../forge-smoke-noattr-$$"
rm -rf "$OFF"; mkdir -p "$OFF/apps/web"
git -C "$OFF" init -q
echo '{"name":"w","scripts":{"test":"jest"}}' > "$OFF/apps/web/package.json"
"$FORGE/bin/forge" init "$OFF" --auto --name NoAttr --no-attribution >/dev/null 2>&1
( cd "$OFF" && python3 .claude/scripts/agile.py index >/dev/null 2>&1
  python3 .claude/scripts/kb.py index >/dev/null 2>&1 )
if grep -rq "github.com/vstlmkh/forge" "$OFF/docs" "$OFF/CLAUDE.md" "$OFF/.claude/agents" 2>/dev/null
then bad "--no-attribution left a mark behind"
else ok "--no-attribution removes every instance"; fi
rm -rf "$OFF"

echo "== installer"
INST="$WORK/../forge-smoke-install-$$"
rm -rf "$INST"
FORGE_REPO="$FORGE" FORGE_HOME="$INST/.forge" FORGE_BIN="$INST/bin" \
  sh "$FORGE/install.sh" >/dev/null 2>&1
[ -L "$INST/bin/forge" ] && ok "installer links a shim onto the bin dir" \
  || bad "installer did not create the shim"
# the installer clones a ref, so its version legitimately differs from an
# edited working tree - assert that the shim runs, not that it matches
case "$("$INST/bin/forge" version 2>/dev/null)" in
  [0-9]*.[0-9]*.[0-9]*) ok "the shim runs, and finds template/ through the symlink" ;;
  *) bad "the shim could not run" ;;
esac
FORGE_REPO="$FORGE" FORGE_HOME="$INST/.forge" FORGE_BIN="$INST/bin" \
  sh "$FORGE/install.sh" >/dev/null 2>&1 \
  && ok "re-running the installer updates in place" || bad "the installer is not re-runnable"
rm -rf "$FIX" "$SUB" "$INST"

echo "== npm packaging"
PKG_VERSION="$(node -p "require('$FORGE/package.json').version" 2>/dev/null || true)"
if [ -n "$PKG_VERSION" ]; then
  [ "$PKG_VERSION" = "$("$FORGE/bin/forge" version)" ] \
    && ok "package.json and the CLI agree on the version" \
    || bad "package.json says $PKG_VERSION, the CLI says $("$FORGE/bin/forge" version)"
else
  skip "version sync (node is not installed)"
fi

if [ -n "${npm_lifecycle_event:-}" ]; then
  # we are already inside `npm publish`/`npm test`; packing again from here
  # re-enters npm in the same directory and fails on its own lock
  skip "npm packaging (already running inside npm $npm_lifecycle_event)"
elif command -v npm >/dev/null 2>&1 && command -v node >/dev/null 2>&1; then
  NPM="$WORK/../forge-smoke-npm-$$"
  rm -rf "$NPM"; mkdir -p "$NPM/proj/apps/web"
  TGZ="$(cd "$FORGE" && npm pack --silent --pack-destination "$NPM" 2>/dev/null | tail -1)"
  if [ -n "$TGZ" ] && npm install --silent --prefix "$NPM/install" "$NPM/$TGZ" >/dev/null 2>&1; then
    SHIM="$NPM/install/node_modules/.bin/forge"
    [ -x "$SHIM" ] && ok "npm installs a forge shim" || bad "npm did not install the shim"
    [ "$("$SHIM" version 2>/dev/null)" = "$PKG_VERSION" ] \
      && ok "the npm shim runs the Python CLI" || bad "the npm shim did not run"
    git -C "$NPM/proj" init -q
    echo '{"name":"w","scripts":{"test":"jest"}}' > "$NPM/proj/apps/web/package.json"
    ( cd "$NPM/proj" && "$SHIM" init . --auto --name NpmTest >/dev/null 2>&1 \
      && python3 .claude/scripts/forge.py doctor >/dev/null 2>&1 ) \
      && ok "a project installed from the npm package passes doctor" \
      || bad "the packaged harness did not install cleanly"
    "$SHIM" self-update 2>&1 | grep -q "npm" \
      && ok "self-update tells an npm install to use npm" \
      || bad "self-update tried to git-pull an npm install"
  else
    bad "npm pack/install failed"
  fi
  rm -rf "$NPM"
else
  skip "npm packaging (node or npm is not installed)"
fi

echo
echo "passed $PASS, failed $FAIL   (workdir: $WORK)"
[ "$FAIL" = 0 ]
