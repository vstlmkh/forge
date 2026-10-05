#!/usr/bin/env python3
"""agile.py - consistency engine for the Markdown tracker.

Stdlib only. Reads the YAML frontmatter of every artifact under
<tracker>/{backlog,tasks,bugs}, validates it against <tracker>/SCHEMA.md, and
regenerates <tracker>/INDEX.md deterministically. Everything project-specific -
the scopes, the agents that own them, the repositories they live in - comes
from `forge.json` via `forgecfg.py`, so this file is the same in every project.

Commands
    index                       regenerate <tracker>/INDEX.md
    lint                        validate only, print PATH:FIELD: MESSAGE
    next-id <epic|story|task|bug>   print the next free id
    show <ID>                   print JSON {path, frontmatter}
    spec new <ID>               scaffold <tracker>/specs/<ID>.md
    spec show <ID>              print JSON {path, frontmatter, brief, questions, carryover}
    spec check <ID>             validate one spec
    next-req <ID>               print the next free REQ id for that ticket
    gates [N]                   print the gate contract(s)
    handoff <ID> --gate <N>     print the dispatch payload for that gate

Exit codes
    0  clean
    1  fatal (unreadable file, missing directory, bad arguments)
    2  integrity issues found (index still written)
    3  refused to overwrite an existing file
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.dont_write_bytecode = True   # never leave __pycache__ in the repo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import forge as forgecfg  # noqa: E402

# --------------------------------------------------------------------------
# schema constants - keep in sync with <tracker>/SCHEMA.md
# The project-specific vocabulary (scopes, agents, repos) lives in forge.json.
# --------------------------------------------------------------------------

KINDS = {
    "epic": ("backlog", "EPIC", 3),
    "story": ("backlog", "STORY", 3),
    "task": ("tasks", "TASK", 4),
    "bug": ("bugs", "BUG", 4),
}

BACKLOG_STATUSES = ["draft", "groomed", "in_progress", "done", "cancelled"]
TASK_STATUSES = [
    "todo", "speccing", "writing_tests", "in_progress", "review", "verify",
    "done", "blocked", "cancelled",
]
BUG_STATUSES = TASK_STATUSES + ["triage", "wontfix", "cannot_reproduce"]

BACKLOG_TRANSITIONS = {
    "draft": {"groomed", "cancelled"},
    "groomed": {"in_progress", "draft", "cancelled"},
    "in_progress": {"done", "groomed", "cancelled"},
    "done": {"in_progress"},
    "cancelled": {"draft"},
}

TASK_TRANSITIONS = {
    # qa specifies first and writes the failing tests second; there is no path
    # from todo straight into either test-writing or implementation. A project
    # that sets policy.spec_first false keeps the old todo -> writing_tests
    # edge - see SPEC_FIRST_LEGACY_EDGES.
    "todo": {"speccing", "blocked", "cancelled"},
    "speccing": {"writing_tests", "todo", "blocked", "cancelled"},
    # writing_tests -> speccing: the spec was wrong, not the test. It keeps the
    # claim and the spec file; going back to todo would throw both away.
    "writing_tests": {"in_progress", "speccing", "todo", "blocked", "cancelled"},
    "in_progress": {"review", "writing_tests", "blocked", "todo"},
    "review": {"verify", "in_progress"},
    "verify": {"done", "in_progress"},
    "blocked": {"todo", "cancelled"},
    "done": {"in_progress"},
    "cancelled": {"todo"},
}

# restored when policy.spec_first is false, so that upgrading a project with
# tickets already in flight does not make a legal board illegal
SPEC_FIRST_LEGACY_EDGES = {"todo": {"writing_tests"}}

BUG_TRANSITIONS = dict(TASK_TRANSITIONS)
BUG_TRANSITIONS["triage"] = {"todo", "wontfix", "cannot_reproduce", "blocked"}
BUG_TRANSITIONS["wontfix"] = {"triage"}
BUG_TRANSITIONS["cannot_reproduce"] = {"triage"}

PRIORITIES = ["P0", "P1", "P2", "P3"]
SEVERITIES = ["S1", "S2", "S3", "S4"]

# statuses that mean "someone is holding this right now"
CLAIMED_STATUSES = {"speccing", "writing_tests", "in_progress", "review", "verify"}
# Statuses that occupy a working tree. `speccing` is deliberately absent: it
# cuts no branch and writes nothing outside the tracker, so the next ticket can
# be specified while this one is being implemented. Do not "fix" this by adding
# it - the pipelining is the point, and invariant #12 is about git trees.
OCCUPYING_STATUSES = {"writing_tests", "in_progress", "review"}
# statuses qa owns: specifying it, writing the tests, and judging the result
QA_STATUSES = {"speccing", "writing_tests", "review", "verify"}
# Statuses that require a branch. `speccing` is absent: qa still cuts the branch
# when it writes the tests, one stage later.
BRANCHED_STATUSES = {"in_progress", "review", "verify"}
# Statuses in which no work may start while a blocked_by target is unfinished.
# `speccing` is absent on purpose - specifying against an open dependency is
# cheap and useful, where writing tests against one wastes the work twice. It
# is reported as a WARN instead (invariant 16).
DEPENDENT_STATUSES = {"writing_tests", "in_progress"}
# statuses by which the spec must exist and be agreed. `done` is excluded so
# that tickets closed before the spec gate existed never start erroring.
SPECCED_STATUSES = {"writing_tests", "in_progress", "review", "verify"}
# the two fields that arrived with the spec gate; see policy.spec_first
SPEC_FIELDS = {"spec", "spec_waiver"}
TERMINAL_STATUSES = {"done", "cancelled", "wontfix", "cannot_reproduce"}

COMMON_FIELDS = ["id", "type", "title", "status", "priority", "labels", "created", "updated"]
WORK_FIELDS = [
    "parent", "scope", "assignee", "claimed_at", "branch", "pr",
    "merge_sha", "blocked_by", "spec", "spec_waiver", "docs", "docs_waiver",
]

# statuses by which the knowledge base must have been consulted and actualised
DOCUMENTED_STATUSES = {"review", "verify", "done"}
DOCS_WAIVER_RE = re.compile(r"^NO-DOCS \(.+\)$")
NO_TICKET_RE = re.compile(r"^NO-TICKET \(.+\)$")
SPEC_WAIVER_RE = re.compile(r"^NO-SPEC \(.+\)$")
REQ_RE = re.compile(r"^REQ-\d{4}$")
# the spec's own lifecycle, in its frontmatter - not the ticket's
SPEC_STATUSES = ["drafting", "questions", "agreed", "superseded"]
# what a row of the spec's `## Brief` may claim about a requirement
REQ_STATUSES = ["agreed", "assumed", "question", "deferred", "dropped"]
SPEC_SECTIONS = ["Brief", "Questions", "Carryover", "Spec", "Plan"]
BUG_EXTRA_FIELDS = ["severity", "found_in", "reported_by", "regression_of", "spawned_tasks"]

BANNER = (
    "<!-- GENERATED by .claude/scripts/agile.py - DO NOT EDIT. "
    "Run: python3 .claude/scripts/agile.py index -->"
)

ID_RE = re.compile(r"^(EPIC|STORY|TASK|BUG)-\d{3,4}$")
ID_IN_TEXT_RE = re.compile(r"\b(?:EPIC|STORY|TASK|BUG)-\d{3,4}\b")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$")
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


# --------------------------------------------------------------------------
# frontmatter parsing - restricted grammar, no PyYAML
# --------------------------------------------------------------------------

class ParseError(Exception):
    pass


def _scalar(raw: str):
    raw = raw.strip()
    if raw == "" or raw in ("null", "~"):
        return None
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part) for part in inner.split(",")]
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    return raw


def parse_frontmatter(text: str) -> dict:
    """Parse the restricted frontmatter grammar.

    Supported: `key: scalar`, `key: [a, b]`, `key:` followed by `  - item`
    lines, and full-line `#` comments. Nested maps, multiline scalars and
    anchors are deliberately unsupported - SCHEMA.md forbids them.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ParseError("file does not start with a '---' frontmatter fence")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ParseError("unterminated frontmatter block (no closing '---')")

    data: dict = {}
    key = None
    for lineno, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            item = line.strip()
            if not item.startswith("- "):
                raise ParseError(f"line {lineno}: indented line is not a '- item'")
            if key is None or not isinstance(data.get(key), list):
                raise ParseError(f"line {lineno}: list item without a list key")
            data[key].append(_scalar(item[2:]))
            continue
        if ":" not in line:
            raise ParseError(f"line {lineno}: expected 'key: value'")
        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.strip()
        if raw.startswith("#"):
            raw = ""
        elif " #" in raw and not raw.startswith(("\"", "'")):
            raw = raw.split(" #", 1)[0].strip()
        data[key] = [] if raw == "" else _scalar(raw)
    return data


# --------------------------------------------------------------------------
# section and placeholder helpers
#
# Invariant #10's rule - "a section whose only content is an italic placeholder
# counts as empty" - applies to a spec's table cells as well as to a ticket's
# sections, so it lives here rather than inside Artifact.
# --------------------------------------------------------------------------

def is_placeholder(line: str) -> bool:
    """True when a line looks like content but is not: blank, a bare bullet, an
    italic prompt (`_to be filled_`), or TBD / TODO / N/A."""
    line = line.strip()
    if not line or line in ("-", "*"):
        return True
    if len(line) > 1 and line.startswith("_") and line.endswith("_"):
        return True
    if line.lower().strip(".:") in ("tbd", "todo", "n/a", "none yet"):
        return True
    return False


def section_of(body: str, heading: str) -> str | None:
    """The text under `## <heading>`, up to the next `## `, or None if absent."""
    pat = re.compile(r"^##\s+" + re.escape(heading) + r"\s*$", re.MULTILINE)
    m = pat.search(body)
    if not m:
        return None
    rest = body[m.end():]
    nxt = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def table_rows(chunk: str) -> list[list[str]]:
    """The data rows of the Markdown pipe table in `chunk`, as cell lists. The
    header row and the `|---|` separator are dropped; empty cells are kept so a
    column's position never shifts. A section carries one table; if it carries
    two, the rows of the last one are returned."""
    rows: list[list[str]] = []
    for line in chunk.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") and c for c in cells):   # the separator
            rows = []                                        # header precedes it
            continue
        rows.append(cells)
    return rows


# --------------------------------------------------------------------------
# artifact loading
# --------------------------------------------------------------------------

class Artifact:
    def __init__(self, path: str, rel: str, fm: dict, body: str):
        self.path = path
        self.rel = rel
        self.fm = fm
        self.body = body

    def __getattr__(self, name):
        return self.fm.get(name)

    @property
    def id(self) -> str:
        return self.fm.get("id") or ""

    @property
    def kind(self) -> str:
        return self.fm.get("type") or ""

    @property
    def status(self) -> str:
        return self.fm.get("status") or ""

    @property
    def prio(self) -> int:
        p = self.fm.get("priority")
        return PRIORITIES.index(p) if p in PRIORITIES else len(PRIORITIES)

    def listfield(self, name) -> list:
        v = self.fm.get(name)
        if v is None:
            return []
        return v if isinstance(v, list) else [v]

    def section(self, heading: str) -> str | None:
        """The body of `## <heading>`, or None when the heading is absent."""
        return section_of(self.body, heading)

    def has_section(self, heading: str) -> bool:
        chunk = self.section(heading)
        if chunk is None:
            return False
        return any(not is_placeholder(line) for line in chunk.splitlines())


def find_root(explicit: str | None = None) -> str:
    return forgecfg.find_root(explicit)


def tracker_dir(root: str) -> str:
    return forgecfg.load(root).tracker_dir()


def _trel(root: str) -> str:
    return forgecfg.load(root).tracker_rel


def load_all(root: str) -> tuple[list[Artifact], list[str]]:
    tracker = tracker_dir(root)
    trel = _trel(root)
    if not os.path.isdir(tracker):
        raise SystemExit(f"fatal: {tracker} does not exist")
    arts: list[Artifact] = []
    fatal: list[str] = []
    for sub in ("backlog", "tasks", "bugs"):
        d = os.path.join(tracker, sub)
        if not os.path.isdir(d):
            fatal.append(f"{trel}/{sub}: directory is missing")
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(".md") or name.startswith("."):
                continue
            path = os.path.join(d, name)
            rel = os.path.relpath(path, root)
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                fm = parse_frontmatter(text)
            except (OSError, ParseError) as exc:
                fatal.append(f"{rel}: {exc}")
                continue
            body = text.split("\n---", 1)[-1]
            arts.append(Artifact(path, rel, fm, body))
    return arts, fatal


def specs_dir(root: str) -> str:
    return os.path.join(tracker_dir(root), "specs")


def spec_rel(ident: str) -> str:
    """The one legal value of a ticket's `spec:` field. The field exists so a
    ticket can say it has no spec; it is not a degree of freedom."""
    return f"specs/{ident}.md"


def load_specs(root: str) -> tuple[list[Artifact], list[str]]:
    """Specs live beside the tickets but are not tickets: load_all must not see
    them, or every spec would be validated as an artifact with a missing kind."""
    d = specs_dir(root)
    specs: list[Artifact] = []
    fatal: list[str] = []
    if not os.path.isdir(d):
        return specs, fatal
    for name in sorted(os.listdir(d)):
        if not name.endswith(".md") or name.startswith("."):
            continue
        path = os.path.join(d, name)
        rel = os.path.relpath(path, root)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            fm = parse_frontmatter(text)
        except (OSError, ParseError) as exc:
            fatal.append(f"{rel}: {exc}")
            continue
        body = text.split("\n---", 1)[-1]
        specs.append(Artifact(path, rel, fm, body))
    return specs, fatal


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

class Issue:
    def __init__(self, rel: str, field: str, msg: str, level: str = "ERROR"):
        self.rel, self.field, self.msg, self.level = rel, field, msg, level

    def __str__(self):
        return f"{self.rel}:{self.field}: {self.level}: {self.msg}"

    def sort_key(self):
        return (0 if self.level == "ERROR" else 1, self.rel, self.field, self.msg)


def _git_sha_on_branch(root: str, repo_path: str, branch: str, sha: str) -> bool | None:
    """True/False if decidable, None if git cannot answer (no checkout, no sha)."""
    subdir = root if repo_path in (".", "") else os.path.join(root, repo_path)
    if not os.path.isdir(os.path.join(subdir, ".git")) and not os.path.isfile(
        os.path.join(subdir, ".git")
    ):
        return None
    try:
        res = subprocess.run(
            ["git", "-C", subdir, "merge-base", "--is-ancestor", sha, branch],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode == 0:
        return True
    if "Not a valid" in res.stderr or "unknown revision" in res.stderr or "malformed" in res.stderr:
        return None
    return False


def _kb_notes(root: str) -> dict[str, list[str]]:
    """Map every knowledge-base note to its lookup keys: basename, kb-relative and
    repo-relative path (all without `.md`). kb.py owns the knowledge base's own
    rules; this is only enough to resolve a ticket's `docs:` entry."""
    kb = forgecfg.load(root).kb_dir()
    keys: dict[str, list[str]] = {}
    if not os.path.isdir(kb):
        return keys
    for dirpath, dirnames, filenames in os.walk(kb):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if not name.endswith(".md") or name.startswith("."):
                continue
            path = os.path.join(dirpath, name)
            wrel = os.path.relpath(path, kb)
            if os.sep not in wrel:            # README.md / INDEX.md
                continue
            rel = os.path.relpath(path, root)
            for k in (name[:-3], wrel[:-3], rel[:-3]):
                keys.setdefault(k.replace(os.sep, "/"), []).append(rel)
    return keys


def validate(root: str, arts: list[Artifact], check_git: bool = True) -> list[Issue]:
    cfg = forgecfg.load(root)
    issues: list[Issue] = []

    def err(a, field, msg):
        issues.append(Issue(a.rel, field, msg))

    def warn(a, field, msg):
        issues.append(Issue(a.rel, field, msg, "WARN"))

    kb = _kb_notes(root)
    specs, spec_fatal = load_specs(root)
    spec_frontmatter = {str(s.fm.get("ticket") or ""): s.fm for s in specs}
    for msg in spec_fatal:
        rel, _, detail = msg.partition(": ")
        issues.append(Issue(rel, "spec", detail or msg))
    scopes = cfg.scope_names
    agents = cfg.agents
    scope_owner = cfg.scope_owner
    stale_after = timedelta(hours=cfg.stale_claim_hours)

    by_id: dict[str, Artifact] = {}
    for a in arts:
        if not a.id:
            err(a, "id", "missing")
            continue
        if not ID_RE.match(a.id):
            err(a, "id", f"'{a.id}' does not match <TYPE>-<digits>")
        if a.id in by_id:
            err(a, "id", f"duplicate id, also used by {by_id[a.id].rel}")
        else:
            by_id[a.id] = a

    for a in arts:
        kind = a.kind
        if kind not in KINDS:
            err(a, "type", f"'{kind}' is not one of {sorted(KINDS)}")
            continue
        folder, prefix, pad = KINDS[kind]

        # id / filename / folder coherence
        if a.id and not a.id.startswith(prefix + "-"):
            err(a, "id", f"type '{kind}' requires the '{prefix}-' prefix")
        if a.id and len(a.id.split("-")[-1]) != pad:
            err(a, "id", f"type '{kind}' requires a {pad}-digit number")
        if os.path.basename(os.path.dirname(a.path)) != folder:
            err(a, "type", f"'{kind}' artifacts belong in {cfg.tracker_rel}/{folder}/")
        if a.id and not os.path.basename(a.path).startswith(a.id + "-"):
            err(a, "id", f"filename must start with '{a.id}-'")

        is_backlog = kind in ("epic", "story")
        required = list(COMMON_FIELDS)
        if not is_backlog:
            required += WORK_FIELDS
        if kind == "bug":
            required += BUG_EXTRA_FIELDS
        if is_backlog:
            required += ["parent", "scope"]
        for f in required:
            if f not in a.fm:
                # The spec fields arrived after the tracker did. On a project
                # still draining a board that predates them, a missing field is
                # a prompt to add it, not a broken ticket - otherwise `forge
                # upgrade` would turn a healthy board red overnight.
                if f in SPEC_FIELDS and not cfg.spec_first:
                    warn(a, f, "field is missing: add 'spec: null' and "
                               "'spec_waiver: null' after 'blocked_by:' - SCHEMA.md §10")
                else:
                    err(a, f, "field is missing")

        if not a.fm.get("title"):
            err(a, "title", "must not be empty")

        statuses = (
            BACKLOG_STATUSES if is_backlog
            else BUG_STATUSES if kind == "bug"
            else TASK_STATUSES
        )
        if a.status not in statuses:
            err(a, "status", f"'{a.status}' is not one of {statuses}")

        if a.fm.get("priority") not in PRIORITIES:
            err(a, "priority", f"'{a.fm.get('priority')}' is not one of {PRIORITIES}")

        for f in ("created", "updated"):
            v = a.fm.get(f)
            if v is not None and not DATE_RE.match(str(v)):
                err(a, f, f"'{v}' is not YYYY-MM-DD")

        # parent
        parent = a.fm.get("parent")
        if kind == "epic":
            if parent is not None:
                err(a, "parent", "an epic must have parent: null")
        elif kind == "story":
            if parent is None:
                err(a, "parent", "a story must name its epic")
            elif parent not in by_id:
                err(a, "parent", f"'{parent}' does not resolve to an artifact")
            elif by_id[parent].kind != "epic":
                err(a, "parent", f"'{parent}' is a {by_id[parent].kind}, expected an epic")
        else:
            if parent is None:
                err(a, "parent", "a task/bug must name its parent story, epic or bug")
            elif parent not in by_id:
                err(a, "parent", f"'{parent}' does not resolve to an artifact")
            elif by_id[parent].kind not in ("epic", "story", "bug"):
                err(a, "parent", f"'{parent}' is a {by_id[parent].kind}, not a valid parent")

        # scope
        if is_backlog:
            bad = [s for s in a.listfield("scope") if s not in scopes]
            if bad:
                err(a, "scope", f"unknown scope(s) {bad}, allowed {scopes}")
        else:
            scope = a.fm.get("scope")
            if isinstance(scope, list):
                err(a, "scope", "must be exactly one scope - split into one task per scope")
            elif scope not in scopes:
                err(a, "scope", f"'{scope}' is not one of {scopes}")

        if kind == "bug" and a.fm.get("severity") not in SEVERITIES:
            err(a, "severity", f"'{a.fm.get('severity')}' is not one of {SEVERITIES}")

        if is_backlog:
            continue

        # ---- work-artifact invariants -------------------------------------
        assignee = a.fm.get("assignee")
        claimed = a.fm.get("claimed_at")
        scope = a.fm.get("scope")

        if assignee is not None and assignee not in agents:
            err(a, "assignee", f"'{assignee}' is not one of {agents}")

        if a.status in CLAIMED_STATUSES:
            if assignee is None:
                err(a, "assignee", f"status '{a.status}' requires an assignee")
            if claimed is None:
                err(a, "claimed_at", f"status '{a.status}' requires claimed_at")

        if claimed is not None and not TS_RE.match(str(claimed)):
            err(a, "claimed_at", f"'{claimed}' is not ISO-8601 UTC (YYYY-MM-DDThh:mm:ssZ)")

        if assignee == "qa" and a.status not in QA_STATUSES:
            err(a, "assignee",
                f"qa may only hold an artifact in status {sorted(QA_STATUSES)}")
        elif assignee not in (None, "qa", "pm") and scope in scope_owner:
            if assignee not in scope_owner[scope]:
                err(a, "assignee", f"'{assignee}' may not own a '{scope}' artifact "
                                   f"(forge.json: scopes.{scope}.agent)")

        # the test-first stage is qa's, and only qa's
        if a.status == "writing_tests" and assignee not in (None, "qa"):
            err(a, "assignee", "status 'writing_tests' belongs to qa")

        if a.status in BRANCHED_STATUSES and not a.fm.get("branch"):
            err(a, "branch",
                f"status '{a.status}' requires a branch - qa cuts it in writing_tests")

        if cfg.pr_required and a.status in ("review", "verify") and not a.fm.get("pr"):
            err(a, "pr", f"status '{a.status}' requires a pr url")

        repo = cfg.repo_of_scope(scope) if scope else None
        sha = a.fm.get("merge_sha")
        if a.status == "done" and repo is not None and not sha:
            err(a, "merge_sha", "a done artifact with a code scope must record its merge sha")
        if sha and not SHA_RE.match(str(sha)):
            err(a, "merge_sha", f"'{sha}' is not a git sha")
        if sha and check_git and repo is not None:
            ok = _git_sha_on_branch(root, repo.path, repo.branch, str(sha))
            if ok is False:
                err(a, "merge_sha", f"{sha} is not reachable from {repo.path}/{repo.branch}")
            elif ok is None:
                warn(a, "merge_sha", f"could not verify {sha} against {repo.path}/{repo.branch}")

        # ---- the spec contract --------------------------------------------
        # The brief is what the ticket was grilled down to. A ticket that
        # reaches writing_tests without an agreed spec skipped the gate, and
        # qa would then be guessing what to assert - which is the failure the
        # whole stage exists to prevent.
        spec = a.fm.get("spec")
        spec_waiver = a.fm.get("spec_waiver")
        if kind in ("task", "bug"):
            hard = cfg.spec_first
            report = err if hard else warn
            if spec_waiver is not None and not SPEC_WAIVER_RE.match(str(spec_waiver)):
                err(a, "spec_waiver", "must read 'NO-SPEC (<reason>)' or be null")
            if spec is not None and spec_waiver is not None:
                err(a, "spec_waiver", "a waiver contradicts a filled spec: - drop one")
            if spec is not None and str(spec) != spec_rel(a.id):
                err(a, "spec",
                    f"must be '{spec_rel(a.id)}' or null - a ticket has one spec, "
                    "named after it")
            elif spec is not None and not os.path.isfile(
                    os.path.join(tracker_dir(root), str(spec))):
                err(a, "spec", f"'{spec}' does not exist")
            if a.status == "speccing" and spec is None and spec_waiver is None:
                report(a, "spec",
                       "status 'speccing' means the spec is being written: run "
                       f"`agile.py spec new {a.id}`")
            if a.status in SPECCED_STATUSES and spec is None and spec_waiver is None:
                report(a, "spec",
                       f"status '{a.status}' requires an agreed spec at "
                       f"{spec_rel(a.id)}, or spec_waiver: NO-SPEC (<reason>) - "
                       f"run `agile.py spec new {a.id}`")
            if a.status in SPECCED_STATUSES and spec is not None:
                sfm = spec_frontmatter.get(a.id)
                if sfm is not None and sfm.get("status") != "agreed":
                    report(a, "spec",
                           f"{spec} is '{sfm.get('status')}', not 'agreed': the brief "
                           "is not settled, so there is nothing to test against")

        # ---- the knowledge-base contract ----------------------------------
        # A ticket carries the notes it read at grooming and actualised at
        # close. An empty `docs:` past review is a gap, not an oversight - the
        # honest way out is a waiver, exactly as with NO-TEST.
        docs = [str(d) for d in a.listfield("docs")]
        waiver = a.fm.get("docs_waiver")
        for entry in docs:
            hits = kb.get(entry.strip().removesuffix(".md").replace(os.sep, "/"), [])
            if not hits:
                err(a, "docs", f"'{entry}' does not resolve to a note under {cfg.kb_rel}")
            elif len(hits) > 1:
                err(a, "docs", f"'{entry}' is ambiguous: {sorted(hits)}")
        if waiver is not None and not DOCS_WAIVER_RE.match(str(waiver)):
            err(a, "docs_waiver", "must read 'NO-DOCS (<reason>)' or be null")
        if docs and waiver is not None:
            err(a, "docs_waiver", "a waiver contradicts a filled docs: - drop one")
        if cfg.require_docs and a.status in DOCUMENTED_STATUSES and not docs and waiver is None:
            err(a, "docs",
                f"status '{a.status}' requires the knowledge-base notes this ticket read and "
                "actualised, or docs_waiver: NO-DOCS (<reason>)")

        # blocked_by
        for dep in a.listfield("blocked_by"):
            if dep not in by_id:
                err(a, "blocked_by", f"'{dep}' does not resolve to an artifact")
            elif a.status in DEPENDENT_STATUSES and by_id[dep].status not in TERMINAL_STATUSES:
                err(a, "blocked_by",
                    f"cannot be {a.status} while {dep} is {by_id[dep].status}")
            elif a.status == "speccing" and by_id[dep].status not in TERMINAL_STATUSES:
                # specifying against an open dependency is cheap and often
                # right; writing tests against one is what wastes the work
                warn(a, "blocked_by",
                     f"specifying while {dep} is {by_id[dep].status} - the contract "
                     "it settles may move under this brief")

        # bug-specific
        if kind == "bug":
            spawned = a.listfield("spawned_tasks")
            for t in spawned:
                if t not in by_id:
                    err(a, "spawned_tasks", f"'{t}' does not resolve to an artifact")
                elif by_id[t].fm.get("parent") != a.id:
                    err(a, "spawned_tasks", f"{t} must set parent: {a.id}")
            if spawned and a.status == "done":
                open_ = [t for t in spawned if t in by_id and by_id[t].status != "done"]
                if open_:
                    err(a, "status", f"cannot be done while {open_} are open")
            reg = a.fm.get("regression_of")
            if reg is not None and reg not in by_id:
                err(a, "regression_of", f"'{reg}' does not resolve to an artifact")
            if a.status in ("review", "verify") and not a.has_section("Root cause"):
                err(a, "status", "a bug must have a filled '## Root cause' before review")
            if a.status in ("wontfix", "cannot_reproduce") and not a.has_section("Log"):
                err(a, "status", f"'{a.status}' requires a justification in '## Log'")

        # stale claim
        if a.status in CLAIMED_STATUSES and claimed and TS_RE.match(str(claimed)):
            try:
                ts = datetime.strptime(str(claimed).replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                ts = None
            if ts and datetime.now(timezone.utc) - ts > stale_after:
                warn(a, "claimed_at",
                     f"claim by {assignee} is older than {cfg.stale_claim_hours}h - pm should review")

    # blocked_by cycles
    graph = {
        a.id: [d for d in a.listfield("blocked_by") if d in by_id]
        for a in arts if a.id and a.kind in ("task", "bug")
    }
    state: dict[str, int] = {}

    def walk(node, trail):
        if state.get(node) == 2:
            return
        if state.get(node) == 1:
            cyc = " -> ".join(trail[trail.index(node):] + [node])
            issues.append(Issue(by_id[node].rel, "blocked_by", f"dependency cycle {cyc}"))
            return
        state[node] = 1
        for nxt in graph.get(node, []):
            walk(nxt, trail + [node])
        state[node] = 2

    for node in graph:
        walk(node, [])

    # one occupying artifact per working tree
    units: dict[str, list[Artifact]] = {}
    for a in arts:
        if a.kind not in ("task", "bug") or a.status not in OCCUPYING_STATUSES:
            continue
        unit = cfg.unit_of_scope(str(a.fm.get("scope")))
        if unit:
            units.setdefault(unit, []).append(a)
    for unit, holders in units.items():
        if len(holders) > 1:
            repo = cfg.repos[unit]
            where = "the repository" if repo.is_root else repo.path
            names = ", ".join(sorted(h.id for h in holders))
            for h in holders:
                err(h, "status",
                    f"{where} has one working tree; {names} occupy it at once")

    issues.extend(validate_specs(root, specs, by_id, cfg))

    if not cfg.spec_first:
        would_fail = [
            a.id for a in arts
            if a.kind in ("task", "bug") and a.status in SPECCED_STATUSES
            and a.fm.get("spec") is None
        ]
        if would_fail:
            issues.append(Issue(
                "forge.json", "policy.spec_first",
                f"off: {len(would_fail)} ticket(s) are past speccing without a spec "
                f"({', '.join(sorted(would_fail))}). Turn it on once they close.",
                "WARN"))

    issues.sort(key=lambda i: i.sort_key())
    return issues


# --------------------------------------------------------------------------
# the spec artifact
# --------------------------------------------------------------------------

def validate_specs(root: str, specs: list[Artifact], by_id: dict,
                   cfg) -> list[Issue]:
    """Rules S1-S10 of SCHEMA.md §10, reported against the spec's own path."""
    issues: list[Issue] = []

    def err(s, field, msg):
        issues.append(Issue(s.rel, field, msg))

    def warn(s, field, msg):
        issues.append(Issue(s.rel, field, msg, "WARN"))

    for s in specs:
        name = os.path.basename(s.path)[:-3]
        ticket = str(s.fm.get("ticket") or "")

        # S1 - identity and the back-link
        if s.fm.get("type") != "spec":
            err(s, "type", "must be 'spec'")
        if s.fm.get("id") != ticket:
            err(s, "id", f"must equal ticket ('{ticket}')")
        if ticket != name:
            err(s, "ticket", f"'{ticket}' does not match the filename '{name}.md'")
        holder = by_id.get(name)
        if holder is None:
            err(s, "ticket",
                f"no artifact with id '{name}' - an orphan spec outlives a ticket "
                "that was renamed or deleted")
        elif holder.fm.get("spec") != spec_rel(name):
            err(s, "ticket",
                f"{name} does not point back at this file: set 'spec: {spec_rel(name)}'")
        sstatus = s.fm.get("status")
        if sstatus not in SPEC_STATUSES:
            err(s, "status", f"must be one of {'|'.join(SPEC_STATUSES)}")

        # S2/S3 - the sections, and a brief that is not a skeleton
        for heading in SPEC_SECTIONS:
            if s.section(heading) is None:
                err(s, "body", f"'## {heading}' is missing")
        # S4/S5 - the requirement table
        brief = table_rows(s.section("Brief") or "")
        # S3 - a brief is empty when it holds no real requirement row. The
        # table header is not content, which is why has_section cannot answer
        # this one.
        if s.section("Brief") is not None and not any(
                r and REQ_RE.match(r[0]) for r in brief):
            err(s, "Brief", "no requirements - a spec with an unfilled brief is a skeleton")
        seen: set[str] = set()
        reqs: dict[str, str] = {}
        for row in brief:
            if not row or is_placeholder(row[0]):
                continue
            rid = row[0]
            if not REQ_RE.match(rid):
                err(s, "Brief", f"'{rid}' does not match REQ-<4 digits>")
                continue
            if rid in seen:
                err(s, "Brief", f"duplicate {rid}")
            seen.add(rid)
            rstatus = row[2] if len(row) > 2 else ""
            if rstatus not in REQ_STATUSES:
                err(s, "Brief",
                    f"{rid}: status '{rstatus}' is not one of {'|'.join(REQ_STATUSES)}")
            reqs[rid] = rstatus
            if len(row) > 1 and is_placeholder(row[1]):
                err(s, "Brief", f"{rid}: the requirement itself is empty")

        # S6 - `agreed` means nothing is still open
        open_qs = [
            row for row in table_rows(s.section("Questions") or "")
            if row and not is_placeholder(row[0])
            and (len(row) < 4 or is_placeholder(row[3]))
        ]
        if sstatus == "agreed":
            if open_qs:
                err(s, "status",
                    f"{len(open_qs)} question(s) in '## Questions' have no answer - "
                    "a spec is agreed when the user has answered, not when qa has guessed")
            still_asking = sorted(r for r, st in reqs.items() if st == "question")
            if still_asking:
                err(s, "Brief",
                    f"{', '.join(still_asking)} are still 'question' in an agreed spec")

        # S7 - deferred and carryover are the same list, seen from two sides
        carry = table_rows(s.section("Carryover") or "")
        carried: dict[str, str] = {}
        for row in carry:
            if not row or is_placeholder(row[0]):
                continue
            if not REQ_RE.match(row[0]):
                err(s, "Carryover", f"'{row[0]}' does not match REQ-<4 digits>")
                continue
            carried[row[0]] = row[-1] if len(row) > 1 else ""
        for rid, st in sorted(reqs.items()):
            if st == "deferred" and rid not in carried:
                err(s, "Carryover", f"{rid} is deferred but is not carried over")
        for rid in sorted(carried):
            if rid not in reqs:
                err(s, "Carryover", f"{rid} is carried over but is not in '## Brief'")
            elif reqs[rid] != "deferred":
                err(s, "Carryover", f"{rid} is carried over but its brief status is '{reqs[rid]}'")

        # S8 - a carryover row names the ticket it became, or argues why not
        for rid, target in sorted(carried.items()):
            if not target or is_placeholder(target):
                if holder is not None and holder.status in ("verify", "done"):
                    err(s, "Carryover",
                        f"{rid} has no ticket: gate 6 files one per row, or writes "
                        "NO-TICKET (<reason>)")
                continue
            if NO_TICKET_RE.match(target):
                continue
            ids = ID_IN_TEXT_RE.findall(target)
            if not ids:
                err(s, "Carryover",
                    f"{rid}: '{target}' is neither a ticket id nor NO-TICKET (<reason>)")
            for tid in ids:
                if tid not in by_id:
                    err(s, "Carryover", f"{rid}: '{tid}' does not resolve to an artifact")

        # Traceability: a brief that nothing downstream mentions is decoration.
        # Each live requirement is tagged into the ticket's criteria at gate 1,
        # so gates 2 and 4 can work per REQ rather than per paragraph.
        if holder is not None and holder.status in SPECCED_STATUSES and cfg.spec_first:
            criteria = holder.section("Acceptance criteria") or ""
            untraced = sorted(
                r for r, st in reqs.items()
                if st in ("agreed", "assumed") and r not in criteria
            )
            if untraced:
                verb = "appears" if len(untraced) == 1 else "appear"
                err(s, "Brief",
                    f"{', '.join(untraced)} {verb} in no acceptance criterion of "
                    f"{name} - tag the criteria '(REQ-NNNN)' so the tests and the "
                    "evidence can be traced back")

        # S9 - an assumption that outlived the gate is a finding, not a fact
        if holder is not None and holder.status in SPECCED_STATUSES:
            assumed = sorted(r for r, st in reqs.items() if st == "assumed")
            if assumed:
                warn(s, "Brief",
                     f"{', '.join(assumed)} were assumed, never confirmed - "
                     "gate 4 judges them as well as the diff")

        # S10 - an agreed spec plans the gates it has not reached yet
        if sstatus == "agreed":
            plan = s.section("Plan") or ""
            missing = [g for g in ("G2", "G3", "G4", "G5", "G6") if g not in plan]
            if missing:
                err(s, "Plan", f"does not name {', '.join(missing)}")

    return issues


# --------------------------------------------------------------------------
# the gates
#
# One contract, filled six times. `agile-dod` points at `agile.py gates`
# instead of restating this table, so the prose cannot drift from the script,
# and `handoff` renders a dispatch payload from the same rows.
#
# Substitutions available in every string: {id} {scope} {repo} {branch} {agent}
# {others} {tracker}. Nothing here names a project, a stack or a command that
# is not part of the harness itself.
# --------------------------------------------------------------------------

GATES = {
    1: {
        "name": "brief, carryover and spec",
        "owner": "qa",
        "status": "speccing",
        "entry": "status todo, nobody holding it",
        "artifact": "{tracker}/specs/{id}.md",
        "exit": "the spec is 'agreed', every live REQ is tagged into the "
                "acceptance criteria, and `agile.py lint` is clean",
        "failure": "speccing -> todo: the request cannot be specified as written, "
                   "and pm must reshape it",
        "waiver": "spec_waiver: NO-SPEC (<reason>) for a ticket too small to grill",
        "prohibitions": [
            "guess at a requirement. What the knowledge base and the code cannot "
            "answer becomes a question for the user, never an assumption.",
            "ask the user yourself - you have no way to. Write the questions into "
            "'## Questions', set the spec to 'questions', and stop.",
            "re-scope or re-prioritise. Tagging a criterion with its REQ id is the "
            "only edit you may make to '## Acceptance criteria'.",
            "cut a branch or touch any file outside {tracker}/.",
            "move past writing_tests.",
        ],
        "steps": [
            "Claim it: status speccing, assignee qa, claimed_at - with the "
            "compare-and-swap edit from `agile-artifacts`. If the edit fails you "
            "lost the race: stop and report.",
            "`python3 .claude/scripts/agile.py spec new {id}`, then set the "
            "printed `spec:` value on the ticket.",
            "Close what the repository can answer first: "
            "`python3 .claude/scripts/kb.py for-ticket {id}`, `kb.py find`, then "
            "the code. Every requirement records where it came from.",
            "Write '## Brief', allocating ids with "
            "`python3 .claude/scripts/agile.py next-req {id}`.",
            "Everything still open goes into '## Questions' with the REQ it "
            "blocks. Set the spec's status to 'questions' and stop - the "
            "top-level session puts them to the user in one batch.",
            "With the answers: finish '## Brief', move anything deferred into "
            "'## Carryover', write '## Spec' and '## Plan', set the spec "
            "'agreed'.",
            "Tag each acceptance criterion with its '(REQ-NNNN)'.",
            "speccing -> writing_tests; `agile.py lint` clean; commit.",
        ],
    },
    2: {
        "name": "writing the tests",
        "owner": "qa",
        "status": "writing_tests",
        "entry": "status speccing with an agreed spec",
        "artifact": "a failing test per agreed REQ, committed alone on {branch}",
        "exit": "real red output in '## Log', naming the REQ each test covers",
        "failure": "writing_tests -> speccing: the brief is wrong, not the test",
        "waiver": "NO-TEST (<reason>) - the review gate falls back to: <check>",
        "prohibitions": [
            "write production code, in any repository, for any reason.",
            "claim a test is red that you did not watch fail.",
            "invent an assertion the brief does not call for.",
            "start a second ticket in a working tree that is already occupied.",
        ],
        "steps": [
            "Claim speccing -> writing_tests, assignee qa.",
            "Read '## Brief' and '## Spec'. They are the specification; the "
            "ticket's '## Log' is history and you do not need it.",
            "Confirm the working tree is clean, then cut the ticket's branch per "
            "`agile-git`. The engineer continues on it.",
            "Write a test per agreed REQ, matching the existing suite's idiom.",
            "Run them and read the failure. It must fail on the assertion, not on "
            "a missing import.",
            "Commit the tests alone with a `Refs: {id}` trailer; push.",
            "Set branch, status in_progress, assignee {agent}; append the real red "
            "output to '## Log', one line per REQ.",
            "`agile.py lint` clean.",
        ],
    },
    3: {
        "name": "red to green",
        "owner": "engineer",
        "status": "in_progress",
        "entry": "status in_progress on {branch}, carrying qa's red test commit",
        "artifact": "the implementation on qa's branch, plus a PR",
        "exit": "every test qa wrote passes, every available check for {scope} "
                "really ran, PR open, status review",
        "failure": "in_progress -> writing_tests: a test is genuinely wrong, "
                   "argued in '## Log' - never edited",
        "waiver": "SKIPPED (<reason> - see TASK-000X) for a check that does not "
                  "exist here yet",
        "prohibitions": [
            "cut a new branch. qa's red commit is on {branch} and your work "
            "continues it.",
            "edit, skip, loosen or delete a test qa wrote. qa diffs them, and an "
            "empty diff is what it expects.",
            "implement a requirement that is not in '## Brief'. If the work needs "
            "one, say so in '## Log' and hand back - a requirement that enters "
            "here was never grilled.",
            "touch another scope's code: {others}.",
            "report a check as passing when it did not run, or move past review.",
        ],
        "steps": [
            "Check out {branch}. Do not cut one.",
            "Run the tests and watch them fail. That failure is the brief in "
            "executable form.",
            "Read the knowledge-base notes named in the reference above before you write code.",
            "Implement until they pass, matching the surrounding idiom.",
            "Run every available check for {scope}, plus the whole suite.",
            "Commit with a `Refs: {id}` trailer, push, open the PR.",
            "File what the work revealed: "
            "`python3 .claude/scripts/kb.py new <type> <scope> \"<description>\" "
            "--ticket {id}`, or argue a NO-DOCS waiver.",
            "Set pr, status review, assignee qa; append an evidence line per REQ "
            "to '## Log'.",
            "`agile.py lint` and `kb.py lint` both clean.",
        ],
    },
    4: {
        "name": "validation",
        "owner": "qa",
        "status": "review",
        "entry": "status review with a PR and green checks claimed",
        "artifact": "an evidence line per REQ in '## Log'",
        "exit": "every agreed REQ proved by something you ran yourself, and the "
                "test files unchanged since your red commit",
        "failure": "review -> in_progress with the exact command and its output",
        "waiver": "SKIPPED (<reason> - see TASK-000X)",
        "prohibitions": [
            "write or edit production code, including a one-line fix that would "
            "make your own test pass. Reject instead.",
            "edit a test while the ticket is in review. If it is wrong, move the "
            "ticket back and prove it red again.",
            "accept a criterion that is merely plausible from reading the diff.",
            "pass a requirement that is still 'assumed' in the brief without "
            "saying so - it was never put to the user.",
            "merge, bump a submodule pointer, or set done.",
        ],
        "steps": [
            "Read the diff: `gh pr diff <url>`, or `git -C {repo} diff "
            "<base>...{branch}`.",
            "Run the tests you wrote. Your own run, not the engineer's output.",
            "Diff the test files against your red commit: "
            "`git -C {repo} diff <red-sha>..HEAD -- <test paths>`. Empty is what "
            "you expect; anything else is a rejection.",
            "Prove each agreed REQ: run the command, or point at the file and "
            "line. One evidence line per REQ.",
            "Run every available check for {scope} plus the whole suite; record "
            "unavailable ones as SKIPPED with the blocking ticket.",
            "Judge the 'assumed' rows in the brief as well as the diff.",
            "For a bug: '## Root cause' filled, and the original reproduction no "
            "longer reproduces.",
        ],
    },
    5: {
        "name": "documentation",
        "owner": "qa",
        "status": "review",
        "entry": "gate 4 passed",
        "artifact": "a verdict on the notes the engineer filed",
        "exit": "every note resolves, is correctly typed, carries real evidence "
                "and is cross-linked; `kb.py lint` clean",
        "failure": "review -> in_progress naming what is missing",
        "waiver": "docs_waiver: NO-DOCS (<reason>), and it must survive scrutiny",
        "prohibitions": [
            "write the notes the engineer owed and then approve them. Filing is "
            "the engineer's job; judging is yours, and doing both destroys the "
            "separation your verdict rests on.",
            "accept a NO-DOCS waiver on a ticket that changed behaviour, fixed a "
            "defect or chose between approaches.",
            "accept a business rule filed as an overview - lint cannot see a "
            "misfiling, which is why you have to.",
            "move the ticket to verify before gate 6 has reported.",
        ],
        "steps": [
            "`python3 .claude/scripts/kb.py for-ticket {id}` and `kb.py lint`.",
            "Judge each note: right type, real evidence, '## Related' linked both "
            "ways, ticket listed in `tickets:` with `updated:` bumped.",
            "Judge any NO-DOCS waiver as a claim, not a formality.",
            "Write the verdict into '## Log' - red output and green output "
            "together.",
            "Once gate 6 has reported: review -> verify, assignee qa. `verify` "
            "means it awaits the user's acceptance; you do not close it.",
        ],
    },
    6: {
        "name": "board update",
        "owner": "pm",
        "status": "review",
        "entry": "gate 4 passed; runs in parallel with gate 5",
        "artifact": "a ticket per '## Carryover' row, and the parent rolled up",
        "exit": "every carryover row names a ticket id or an argued NO-TICKET",
        "failure": "report what could not be filed and why; this gate never "
                   "blocks verify on its own",
        "waiver": "NO-TICKET (<reason>) for a row that will never become work",
        "prohibitions": [
            "transition {id}. You create tickets and roll the parent up; qa moves "
            "this one to verify. 'pm may not move a task past todo' still holds.",
            "edit {id} itself - qa is writing its '## Log' at gate 5 at this very "
            "moment, and two writers on one file lose each other's work.",
            "file a carryover row as a ticket without grooming it properly: it "
            "needs docs:, a scope, and criteria an agent can satisfy.",
            "invent a verification command that `forge.py checks <scope>` does "
            "not list.",
        ],
        "steps": [
            "Read '## Carryover' in the spec. Nothing else about this ticket "
            "concerns you.",
            "For each row: `python3 .claude/scripts/agile.py next-id task`, write "
            "the ticket, consult the knowledge base for its docs:.",
            "Write the new id into the row's 'Becomes' cell - that is the only "
            "edit you make to the spec.",
            "A row that should never become work gets NO-TICKET (<reason>) there "
            "instead, argued.",
            "Roll the parent up if this was its last open child.",
            "`agile.py lint` clean. Report the ids you filed.",
        ],
    },
}


def gate_context(root: str, a: Artifact, cfg) -> dict:
    """The substitutions a gate's strings may use. Everything concrete comes
    from forge.json at runtime, which is why none of it is written into the
    gate table."""
    scope = str(a.fm.get("scope") or "")
    repo = cfg.repo_of_scope(scope)
    owners = sorted(cfg.scope_owner.get(scope, set()))
    # the other code scopes' working directories - in a monorepo those are
    # sibling paths inside one repository, in a super-repo they are separate
    # checkouts, and in both cases they are what this agent must not touch
    others = []
    for name, s in cfg.scopes.items():
        if name == scope or not s.code:
            continue
        other_repo = cfg.repo_of_scope(name)
        where = s.workdir or (other_repo.path if other_repo else name)
        if where not in others:
            others.append(where)
    return {
        "id": a.id,
        "scope": scope or "<unscoped>",
        "repo": repo.path if repo else ".",
        "branch": str(a.fm.get("branch") or "<the ticket's branch>"),
        "agent": owners[0] if owners else "the scope's engineer",
        "others": ", ".join(others) or "none - this project has one code scope",
        "tracker": cfg.tracker_rel,
    }


def gate_owner(gate: dict, ctx: dict) -> str:
    return ctx["agent"] if gate["owner"] == "engineer" else gate["owner"]


SPEC_SKELETON = """\
---
id: {ident}
type: spec
ticket: {ident}
status: drafting
created: {today}
updated: {today}
---

# {ident} — {title}

## Brief

_The requirements this ticket is agreed to satisfy. One row per requirement,
allocated with `agile.py next-req {ident}`. IDs are never reused and never
renumbered: a dropped requirement keeps its row with status `dropped`._

| ID | Requirement | Status | Source |
|---|---|---|---|
| _REQ-0001_ | _what must be true when this is done_ | _question_ | _user / kb:<note> / code:<path:line>_ |

## Questions

_What the knowledge base and the code could not answer. The orchestrator puts
these to the user in one batch; you do not guess. An unanswered question becomes
a carryover row, never an assumption._

| Q | Blocks | Question | Answer |
|---|---|---|---|
| Q1 | REQ-0001 | _the question_ | _filled in when the user answers_ |

## Carryover

_Requirements deliberately deferred. Gate 6 files a ticket per row and writes
its id into `Becomes`; a row that will never become a ticket says
`NO-TICKET (<reason>)`._

| ID | Deferred because | Becomes |
|---|---|---|

## Spec

_Behaviour, boundaries and contracts, written against the REQ ids above. Say
what is explicitly out of scope - that is what stops the ticket growing._

## Plan

_The remaining gates, instantiated for this ticket._

| Gate | Owner | Artifact | Exit |
|---|---|---|---|
| G2 | qa | a failing test per agreed REQ | real red output in `## Log` |
| G3 | the scope's engineer | the implementation, on qa's branch | every G2 test green |
| G4 | qa | an evidence line per REQ | every agreed REQ proved |
| G5 | qa | the notes the work established | `kb.py lint` clean |
| G6 | pm | a ticket per carryover row | every row carries an id |
"""


# --------------------------------------------------------------------------
# INDEX.md rendering
# --------------------------------------------------------------------------

def _rel_from_index(a: Artifact, root: str) -> str:
    return os.path.relpath(a.path, tracker_dir(root)).replace(os.sep, "/")


def _row(a: Artifact, root: str) -> str:
    who = a.fm.get("assignee") or "-"
    pr = a.fm.get("pr")
    prcell = f"[PR]({pr})" if pr else "-"
    scope = a.fm.get("scope") or "-"
    if isinstance(scope, list):
        scope = ", ".join(scope) or "-"
    sev = f" {a.fm.get('severity')}" if a.kind == "bug" else ""
    return (
        f"| [{a.id}]({_rel_from_index(a, root)}) | {a.fm.get('title')} | "
        f"{a.fm.get('priority')}{sev} | {scope} | {a.status} | {who} | {prcell} |"
    )


HEAD = "| ID | Title | Prio | Scope | Status | Assignee | PR |\n|---|---|---|---|---|---|---|"


def render_index(root: str, arts: list[Artifact], issues: list[Issue]) -> str:
    cfg = forgecfg.load(root)
    work = [a for a in arts if a.kind in ("task", "bug")]
    backlog = [a for a in arts if a.kind in ("epic", "story")]
    by_id = {a.id: a for a in arts if a.id}

    def key(a):
        return (a.prio, a.id)

    def blocked(a):
        if a.status == "blocked":
            return True
        return any(
            d in by_id and by_id[d].status not in TERMINAL_STATUSES
            for d in a.listfield("blocked_by")
        )

    now = sorted([a for a in work if a.status in CLAIMED_STATUSES], key=key)
    ready = sorted([a for a in work if a.status == "todo" and not blocked(a)], key=key)
    blk = sorted([a for a in work if a.status != "blocked" and blocked(a)]
                 + [a for a in work if a.status == "blocked"], key=key)
    triage = sorted([a for a in work if a.status == "triage"], key=key)
    done = sorted(
        [a for a in work if a.status == "done"],
        key=lambda a: (str(a.fm.get("updated") or ""), a.id),
        reverse=True,
    )[:15]

    out: list[str] = [BANNER, "", f"# Board - {cfg.project_name}", ""]
    counts = {
        "now": len(now), "ready": len(ready), "blocked": len(blk),
        "triage": len(triage), "done": len([a for a in work if a.status == "done"]),
    }
    out.append(
        f"Now {counts['now']} - Ready {counts['ready']} - Blocked {counts['blocked']} - "
        f"Triage {counts['triage']} - Done {counts['done']}"
    )
    out.append("")

    def section(title, items, empty):
        out.append(f"## {title}")
        out.append("")
        if not items:
            out.append(f"_{empty}_")
        else:
            out.append(HEAD)
            out.extend(_row(a, root) for a in items)
        out.append("")

    section("Now", now, "nothing in flight")
    section("Ready", ready, "nothing ready - groom something")
    section("Blocked", blk, "nothing blocked")
    section("Triage", triage, "no untriaged bugs")

    out.append("## Backlog tree")
    out.append("")
    epics = sorted([a for a in backlog if a.kind == "epic"], key=key)
    if not epics:
        out.append("_no epics yet_")
        out.append("")
    for e in epics:
        stories = sorted([a for a in backlog if a.fm.get("parent") == e.id], key=key)
        kids_of_epic = sorted([a for a in work if a.fm.get("parent") == e.id], key=key)
        tot = sum(1 for a in work if a.fm.get("parent") == e.id or
                  (a.fm.get("parent") in {s.id for s in stories}))
        dn = sum(1 for a in work if (a.fm.get("parent") == e.id or
                 a.fm.get("parent") in {s.id for s in stories}) and a.status == "done")
        out.append(
            f"- **[{e.id}]({_rel_from_index(e, root)})** {e.fm.get('title')} "
            f"- `{e.status}` {e.fm.get('priority')} ({dn}/{tot} done)"
        )
        for s in stories:
            kids = sorted([a for a in work if a.fm.get("parent") == s.id], key=key)
            sdn = sum(1 for a in kids if a.status == "done")
            out.append(
                f"  - [{s.id}]({_rel_from_index(s, root)}) {s.fm.get('title')} "
                f"- `{s.status}` ({sdn}/{len(kids)} done)"
            )
            for t in kids:
                out.append(
                    f"    - [{t.id}]({_rel_from_index(t, root)}) {t.fm.get('title')} "
                    f"- `{t.status}` {t.fm.get('scope')}"
                )
        for t in kids_of_epic:
            out.append(
                f"  - [{t.id}]({_rel_from_index(t, root)}) {t.fm.get('title')} "
                f"- `{t.status}` {t.fm.get('scope')}"
            )
    orphan_stories = sorted(
        [a for a in backlog if a.kind == "story" and a.fm.get("parent") not in
         {e.id for e in epics}], key=key)
    for s in orphan_stories:
        out.append(f"- **[{s.id}]({_rel_from_index(s, root)})** {s.fm.get('title')} "
                   f"- `{s.status}` (orphan story)")
    out.append("")

    out.append("## Recently done")
    out.append("")
    if not done:
        out.append("_nothing closed yet_")
    else:
        out.append("| ID | Title | Scope | Closed | Merge |")
        out.append("|---|---|---|---|---|")
        for a in done:
            sha = a.fm.get("merge_sha")
            out.append(
                f"| [{a.id}]({_rel_from_index(a, root)}) | {a.fm.get('title')} | "
                f"{a.fm.get('scope')} | {a.fm.get('updated')} | `{str(sha)[:8] if sha else '-'}` |"
            )
    out.append("")

    if issues:
        out.append("## Integrity")
        out.append("")
        out.append(f"`agile.py lint` reports {len(issues)} issue(s):")
        out.append("")
        for i in issues:
            out.append(f"- `{i.rel}` **{i.field}** - {i.level}: {i.msg}")
        out.append("")

    credit = cfg.credit()
    if credit:
        out += ["---", "", credit, ""]

    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_index(root: str, arts: list[Artifact]) -> int:
    issues = validate(root, arts)
    path = os.path.join(tracker_dir(root), "INDEX.md")
    content = render_index(root, arts, issues)
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
    if old != content:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
    work = [a for a in arts if a.kind in ("task", "bug")]
    errs = sum(1 for i in issues if i.level == "ERROR")
    print(
        f"index: {len(arts)} artifacts ({len(work)} work items), "
        f"{errs} error(s), {len(issues) - errs} warning(s)"
        f"{'' if old == content else ' - INDEX.md updated'}"
    )
    return 2 if issues else 0


def cmd_lint(root: str, arts: list[Artifact]) -> int:
    issues = validate(root, arts)
    for i in issues:
        print(i)
    if not issues:
        print(f"lint: clean ({len(arts)} artifacts)")
    return 2 if issues else 0


def cmd_next_id(root: str, arts: list[Artifact], kind: str) -> int:
    if kind not in KINDS:
        print(f"fatal: unknown kind '{kind}', expected one of {sorted(KINDS)}", file=sys.stderr)
        return 1
    _folder, prefix, pad = KINDS[kind]
    high = 0
    for a in arts:
        if a.id.startswith(prefix + "-"):
            try:
                high = max(high, int(a.id.split("-")[-1]))
            except ValueError:
                pass
    print(f"{prefix}-{high + 1:0{pad}d}")
    return 0


def _spec_of(root: str, ident: str) -> Artifact | None:
    for s in load_specs(root)[0]:
        if os.path.basename(s.path)[:-3] == ident:
            return s
    return None


def cmd_spec(root: str, arts: list[Artifact], args: list[str]) -> int:
    """spec new|show|check <ID> - the spec file is created by this command and
    never by hand, for the same reason a knowledge-base note is: the path, the
    frontmatter and the required sections all come out right, and a validator
    that shouts at an agent mid-task is worse than no validator."""
    if not args:
        print("fatal: spec needs new|show|check and an id", file=sys.stderr)
        return 1
    sub, rest = args[0], args[1:]
    if sub not in ("new", "show", "check") or not rest:
        print("fatal: usage: spec new|show|check <ID>", file=sys.stderr)
        return 1
    ident = rest[0]
    holder = next((a for a in arts if a.id == ident), None)

    if sub == "new":
        if holder is None:
            print(f"fatal: no artifact with id '{ident}'", file=sys.stderr)
            return 1
        if holder.kind not in ("task", "bug"):
            print(f"fatal: {ident} is a {holder.kind}; only a task or a bug is specified",
                  file=sys.stderr)
            return 1
        d = specs_dir(root)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{ident}.md")
        if os.path.exists(path):
            print(f"fatal: {os.path.relpath(path, root)} already exists", file=sys.stderr)
            return 3
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(SPEC_SKELETON.format(
                ident=ident, today=today, title=holder.fm.get("title") or ident))
        print(os.path.relpath(path, root))
        # agile.py has never written a ticket and must not start: the claim is
        # an Edit-based compare-and-swap, and a script rewriting frontmatter
        # behind the agent's back breaks it. Print the edit instead.
        print(f"now set this on {holder.rel}:    spec: {spec_rel(ident)}", file=sys.stderr)
        return 0

    s = _spec_of(root, ident)
    if s is None:
        print(f"fatal: no spec at {spec_rel(ident)}", file=sys.stderr)
        return 1

    if sub == "show":
        print(json.dumps({
            "path": s.rel,
            "frontmatter": s.fm,
            "brief": [
                {"id": r[0], "requirement": r[1] if len(r) > 1 else "",
                 "status": r[2] if len(r) > 2 else "", "source": r[3] if len(r) > 3 else ""}
                for r in table_rows(s.section("Brief") or "")
                if r and REQ_RE.match(r[0])
            ],
            "questions": [
                {"q": r[0], "blocks": r[1] if len(r) > 1 else "",
                 "question": r[2] if len(r) > 2 else "",
                 "answer": "" if len(r) < 4 or is_placeholder(r[3]) else r[3]}
                for r in table_rows(s.section("Questions") or "")
                if r and not is_placeholder(r[0])
            ],
            "carryover": [
                {"id": r[0], "because": r[1] if len(r) > 1 else "",
                 "becomes": r[-1] if len(r) > 1 else ""}
                for r in table_rows(s.section("Carryover") or "")
                if r and REQ_RE.match(r[0])
            ],
        }, indent=2, sort_keys=True))
        return 0

    by_id = {a.id: a for a in arts if a.id}
    issues = validate_specs(root, [s], by_id, forgecfg.load(root))
    for i in issues:
        print(i)
    return 2 if any(i.level == "ERROR" for i in issues) else 0


def cmd_next_req(root: str, ident: str) -> int:
    """REQ ids are per-ticket and allocated from the brief, the way artifact ids
    are allocated from the filesystem. They are never reused and never
    renumbered, so a REQ in a test name or a commit message stays meaningful."""
    s = _spec_of(root, ident)
    if s is None:
        print(f"fatal: no spec at {spec_rel(ident)} - run `agile.py spec new {ident}`",
              file=sys.stderr)
        return 1
    high = 0
    for row in table_rows(s.section("Brief") or ""):
        if row and REQ_RE.match(row[0]):
            high = max(high, int(row[0].split("-")[1]))
    print(f"REQ-{high + 1:04d}")
    return 0


def cmd_gates(args: list[str]) -> int:
    wanted = GATES
    if args:
        try:
            n = int(args[0])
        except ValueError:
            print(f"fatal: '{args[0]}' is not a gate number", file=sys.stderr)
            return 1
        if n not in GATES:
            print(f"fatal: there are {len(GATES)} gates, not {n}", file=sys.stderr)
            return 1
        wanted = {n: GATES[n]}
    # No ticket is in hand here, so the substitutions show their shape rather
    # than a value. `handoff` is where they are filled from forge.json.
    generic = {"id": "<ID>", "scope": "<scope>", "repo": "<repo>",
               "branch": "<branch>", "agent": "<the scope's engineer>",
               "others": "<the other scopes>", "tracker": "<tracker>"}
    for n, g in sorted(wanted.items()):
        g = {k: (v.format(**generic) if isinstance(v, str) else v)
             for k, v in g.items()}
        print(f"Gate {n} of {len(GATES)} — {g['name']}")
        print(f"  Owner     {g['owner']}")
        print(f"  Status    {g['status']}")
        print(f"  Entry     {g['entry']}")
        print(f"  Artifact  {g['artifact']}")
        print(f"  Exit      {g['exit']}")
        print(f"  Failure   {g['failure']}")
        print(f"  Waiver    {g['waiver']}")
        print()
    return 0


def _wrap(text: str, width: int = 76, indent: str = "") -> list[str]:
    out, line = [], indent
    for word in text.split():
        if line.strip() and len(line) + 1 + len(word) > width:
            out.append(line)
            line = indent + word
        else:
            line = f"{line} {word}" if line.strip() else indent + word
    if line.strip():
        out.append(line)
    return out


def _bullet(text: str) -> list[str]:
    lines = _wrap(text, indent="  ")
    lines[0] = "- " + lines[0].lstrip()
    return lines


def _log_tail(a: Artifact, keep: int) -> tuple[str, int, int]:
    """The last `keep` bullet entries of '## Log'. A truncation is always
    announced: a budget that hides what it dropped reads as completeness."""
    chunk = a.section("Log") or ""
    entries, cur = [], []
    for line in chunk.splitlines():
        if line.startswith(("- ", "* ")):
            if cur:
                entries.append("\n".join(cur))
            cur = [line]
        elif cur:
            cur.append(line)
    if cur:
        entries.append("\n".join(cur))
    total = len(entries)
    if keep <= 0 or not entries:
        return "", 0, total
    tail = entries[-keep:]
    return "\n".join(tail), len(tail), total


def render_handoff(root: str, a: Artifact, n: int, cfg,
                   max_log: int = 3) -> list[str]:
    """The dispatch payload for one gate.

    The layout is fixed and is the point: CONTRACT and PROHIBITIONS first,
    inert REFERENCE in the middle, the same contract compressed again last.
    An instruction buried in the middle of a long prompt is an instruction that
    will not be followed, so nothing binding is ever placed there - and the
    reference half carries paths and commands rather than pasted file bodies,
    which is also what keeps the payload small.
    """
    g = GATES[n]
    ctx = gate_context(root, a, cfg)

    def sub(text: str) -> str:
        return text.format(**ctx)
    owner = gate_owner(g, ctx)
    spec = _spec_of(root, a.id)
    out: list[str] = []
    bar = "=" * 70

    # ---- 1. the contract -------------------------------------------------
    out.append(f"=== GATE {n} of {len(GATES)} — {g['name']} — {a.id} {'=' * 10}")
    out.append(f"YOU ARE: {owner}.")
    out += _wrap(f"ENTRY:    {sub(g['entry'])}")
    out += _wrap(f"YOU OWE:  {sub(g['artifact'])}")
    out += _wrap(f"EXIT:     {sub(g['exit'])}")
    out += _wrap(f"FAILURE:  {sub(g['failure'])}")
    out += _wrap(f"WAIVER:   {sub(g['waiver'])}")

    # ---- 2. the prohibitions ---------------------------------------------
    out.append("")
    out.append("MUST NOT:")
    for p in g["prohibitions"]:
        out += _bullet(sub(p))

    # ---- 3. the reference ------------------------------------------------
    out.append("")
    out.append("--- reference (read these yourself; they are not pasted here) ---")
    out.append(f"ticket    {a.rel}")
    if spec is not None:
        out.append(f"spec      {spec.rel}")
    elif a.fm.get("spec_waiver"):
        out.append(f"spec      none — {a.fm.get('spec_waiver')}")
    out.append(f"scope     {ctx['scope']}   repo {ctx['repo']}")
    # Gate 6 works on other artifacts entirely: a branch, a PR and a check
    # matrix would be noise, and noise in the middle is what pushes the
    # binding half of the payload apart.
    if n != 6:
        if a.fm.get("branch"):
            out.append(f"branch    {a.fm.get('branch')}")
        if a.fm.get("pr"):
            out.append(f"pr        {a.fm.get('pr')}")
        if n != 5:
            out.append(f"checks    python3 .claude/scripts/forge.py checks {ctx['scope']}")
        out.append(f"docs      python3 .claude/scripts/kb.py for-ticket {a.id}")

    if n in (2, 3, 4) and a.fm.get("branch"):
        repo = ctx["repo"]
        out.append(f"tests     git -C {repo} diff --name-only "
                   f"<base>...{a.fm.get('branch')}   # qa's test files")

    if spec is not None:
        if n in (2, 3, 4):
            rows = [r for r in table_rows(spec.section("Brief") or "")
                    if r and REQ_RE.match(r[0]) and (len(r) < 3 or r[2] != "dropped")]
            if rows:
                out.append("")
                out.append("spec ## Brief")
                for r in rows:
                    status = r[2] if len(r) > 2 else "?"
                    out.append(f"  {r[0]}  [{status}]  {r[1] if len(r) > 1 else ''}")
        if n in (2, 3, 5):
            body = (spec.section("Spec") or "").strip()
            if body:
                out.append("")
                out.append("spec ## Spec")
                out += [f"  {l}" for l in body.splitlines()]
        if n == 3:
            plan = [r for r in table_rows(spec.section("Plan") or "")
                    if r and r[0] == f"G{n}"]
            if plan:
                out.append("")
                out.append(f"spec ## Plan — your row: {' | '.join(plan[0])}")
        if n == 6:
            out.append("")
            out.append("spec ## Carryover")
            rows = [r for r in table_rows(spec.section("Carryover") or "")
                    if r and REQ_RE.match(r[0])]
            for r in rows:
                out.append(f"  {r[0]}  because: {r[1] if len(r) > 1 else ''}  "
                           f"becomes: {r[-1] if len(r) > 1 else ''}")
            if not rows:
                out.append("  (nothing deferred — report that and file nothing)")
            out.append(f"parent    {a.fm.get('parent')}")

    if n != 6:
        tail, kept, total = _log_tail(a, 0 if n == 1 else max_log)
        if kept:
            out.append("")
            out.append(f"## Log (last {kept} of {total})")
            out += [f"  {l}" for l in tail.splitlines()]
        elif total and n != 1:
            out.append(f"log       {total} entries, none carried (--max-log 0)")

    # ---- 4. the steps ----------------------------------------------------
    out.append("")
    out.append("--- steps ---")
    for i, step in enumerate(g["steps"], 1):
        lines = _wrap(sub(step), indent="    ")
        lines[0] = f"{i:2d}. " + lines[0].lstrip()
        out += lines

    # ---- 5. the anchor ---------------------------------------------------
    out.append("")
    out.append(f"=== ANCHOR — re-read before you answer {'=' * 31}")
    out += _wrap(f"GATE {n}: {g['name']}. Exit: {sub(g['exit'])}.")
    for p in g["prohibitions"]:
        out += _bullet(f"do not {sub(p)}")
    out += _wrap(f"Failure route: {sub(g['failure'])}.")
    out.append("Finish with: agile.py lint and kb.py lint, both exit 0.")
    out.append(bar)
    return out


def cmd_handoff(root: str, arts: list[Artifact], args: list[str]) -> int:
    rest = list(args)
    n, max_log = None, 3
    for flag, default in (("--gate", None), ("--max-log", 3)):
        if flag in rest:
            i = rest.index(flag)
            try:
                value = int(rest[i + 1])
            except (IndexError, ValueError):
                print(f"fatal: {flag} needs a number", file=sys.stderr)
                return 1
            del rest[i:i + 2]
            if flag == "--gate":
                n = value
            else:
                max_log = value
    if not rest:
        print("fatal: handoff needs a ticket id", file=sys.stderr)
        return 1
    if n is None:
        print(f"fatal: handoff needs --gate <1-{len(GATES)}>", file=sys.stderr)
        return 1
    if n not in GATES:
        print(f"fatal: there are {len(GATES)} gates, not {n}", file=sys.stderr)
        return 1
    ident = rest[0]
    a = next((x for x in arts if x.id == ident), None)
    if a is None:
        print(f"fatal: no artifact with id '{ident}'", file=sys.stderr)
        return 1

    cfg = forgecfg.load(root)
    target = GATES[n]["status"]
    legal = (a.status == target
             or target in TASK_TRANSITIONS.get(a.status, set())
             or (not cfg.spec_first
                 and target in SPEC_FIRST_LEGACY_EDGES.get(a.status, set())))
    lines = render_handoff(root, a, n, cfg, max_log)
    if not legal:
        print(f"BLOCKED: {ident} is '{a.status}' and cannot reach '{target}', "
              f"which gate {n} runs in. Legal next: "
              f"{', '.join(sorted(TASK_TRANSITIONS.get(a.status, set()))) or 'none'}.")
        print()
    print("\n".join(lines))
    return 2 if not legal else 0


def cmd_show(root: str, arts: list[Artifact], ident: str) -> int:
    for a in arts:
        if a.id == ident:
            print(json.dumps({"path": a.rel, "frontmatter": a.fm}, indent=2, sort_keys=True))
            return 0
    print(f"fatal: no artifact with id '{ident}'", file=sys.stderr)
    return 1


USAGE = __doc__


def main(argv: list[str]) -> int:
    args = list(argv[1:])
    root_arg = None
    if "--root" in args:
        i = args.index("--root")
        try:
            root_arg = args[i + 1]
        except IndexError:
            print("fatal: --root needs a path", file=sys.stderr)
            return 1
        del args[i:i + 2]
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0 if args else 1

    root = find_root(root_arg)
    arts, fatal = load_all(root)
    if fatal:
        for f in fatal:
            print(f"fatal: {f}", file=sys.stderr)
        return 1

    cmd = args[0]
    if cmd == "spec":
        return cmd_spec(root, arts, args[1:])
    if cmd == "gates":
        return cmd_gates(args[1:])
    if cmd == "handoff":
        return cmd_handoff(root, arts, args[1:])
    if cmd == "next-req":
        if len(args) < 2:
            print("fatal: next-req needs a ticket id", file=sys.stderr)
            return 1
        return cmd_next_req(root, args[1])
    if cmd == "index":
        return cmd_index(root, arts)
    if cmd == "lint":
        return cmd_lint(root, arts)
    if cmd == "next-id":
        if len(args) < 2:
            print("fatal: next-id needs a kind (epic|story|task|bug)", file=sys.stderr)
            return 1
        return cmd_next_id(root, arts, args[1])
    if cmd == "show":
        if len(args) < 2:
            print("fatal: show needs an ID", file=sys.stderr)
            return 1
        return cmd_show(root, arts, args[1])
    print(f"fatal: unknown command '{cmd}'", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
