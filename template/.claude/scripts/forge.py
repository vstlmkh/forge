#!/usr/bin/env python3
"""forge.py - the single source of truth about *this* project's shape.

Everything that differs between projects - how many repositories there are,
which scopes exist, who implements each one, what a check for that scope is
called, where the knowledge base lives - is declared in `forge.json` at the
repository root. The tracker (`agile.py`), the knowledge base (`kb.py`), the
hooks and the agents all read it from here, so there is exactly one place to
edit when a project's shape changes.

Stdlib only. Any consumer may assume the defaults below, so a `forge.json` that
declares only `project.name` and one scope is already valid.
"""

from __future__ import annotations

import json
import os
import sys

CONFIG_NAME = "forge.json"

# Attribution. forge signs the files it generates itself - the two INDEX.md
# boards, the managed CLAUDE.md block, the rendered agents - and nothing else:
# never a commit, never a pull request, never a file the project's own people
# wrote. It is a visible line with a link, not a hidden mark, because the only
# honest watermark in somebody else's repository is one they can read and
# delete. `"attribution": false` in forge.json removes every instance of it.
FORGE_NAME = "forge"
FORGE_URL = "https://github.com/vstlmkh/forge"

DEFAULT_PATHS = {"tracker": "docs/agile", "kb": "docs/knowledge",
                 "lessons": "docs/lessons"}

# The roles whose agent file carries a model. A project chooses the tier in
# forge.json under policy.models; `forge agents` renders it in. The model is
# bound to the agent file, not to a dispatch, which is why the mapping is per
# role rather than per gate.
MODEL_ROLES = ("pm", "qa", "qa_spec", "engineer")

# Dispatchable agent -> the identity it writes into a ticket's `assignee`. The
# tracker keeps three identities (pm, qa, the scope's engineer) however many
# agent files a project renders, so that invariant 7 and `forge.py agents` keep
# meaning what they say. A delegate never writes its own name.
AGENT_ALIASES = {"qa-spec": "qa"}
DEFAULT_MODELS = {"pm": "opus", "qa": "sonnet", "qa_spec": "opus", "engineer": "sonnet"}

# The knowledge-base taxonomy is deliberately *not* configurable: it is the part
# of the convention that makes notes from one project legible in the next. What
# a project may change is which scopes exist and which types are locked to one.
KB_TYPES: dict[str, list[str]] = {
    "business-rule": ["Rule", "Why", "Where enforced"],
    "troubleshooting": ["Symptom", "Root cause", "Fix", "How to detect it again"],
    "overview": ["What it does", "Structure", "Entry points"],
    "integration": ["What it is", "How we call it", "Behaviour to know"],
    "api-contract": ["Endpoint", "Request", "Response", "Consumers"],
    "decision": ["Decision", "Context", "Alternatives considered", "Consequences"],
    "runbook": ["When to run this", "Steps", "If it goes wrong"],
    "data-model": ["Entities", "Invariants", "Relations"],
}


# The lessons layer. A lesson is addressed to an audience, not to a subject:
# `scope` says which slice of the project it governs and `roles` which of the
# three identities must obey it. Both axes accept the reserved value below,
# which is why a project may not name a scope `all`.
LESSON_ROLES = ("pm", "qa", "engineer")
LESSON_ALL = "all"
# What `lessons.py for` is allowed to put in front of an agent. The cap is the
# whole point: an agent that is handed forty rules reads none of them, and the
# context it spends on them is context it does not spend on the ticket.
DEFAULT_LESSON_BUDGET = 12
DEFAULT_LESSON_STALE_DAYS = 180


class ConfigError(Exception):
    pass


class Repo:
    """One git working tree. A monorepo declares exactly one; a super-repo with
    submodules declares the super-repo plus one entry per submodule."""

    def __init__(self, name: str, data: dict):
        self.name = name
        self.path = str(data.get("path") or ".")
        self.branch = str(data.get("branch") or "main")
        self.remote = data.get("remote")          # owner/name, for `gh`
        self.submodule = bool(data.get("submodule", self.path not in (".", "")))
        self.role = data.get("role")              # "harness" marks the repo holding docs/

    @property
    def is_root(self) -> bool:
        return self.path in (".", "")

    def abspath(self, root: str) -> str:
        return root if self.is_root else os.path.join(root, self.path)

    def __repr__(self):
        return f"<Repo {self.name} path={self.path} branch={self.branch}>"


class Scope:
    """One ticket scope: a slice of the project that a single agent implements."""

    def __init__(self, name: str, data: dict, default_kb_scope: str):
        self.name = name
        self.repo = data.get("repo")                      # a key of `repos`, or None
        agents = data.get("agent") or data.get("agents") or []
        self.agents = [agents] if isinstance(agents, str) else list(agents)
        self.kb_scope = str(data.get("kb_scope") or default_kb_scope)
        self.stack = data.get("stack") or ""
        self.workdir = data.get("workdir") or None        # where this scope's commands run
        self.code = bool(data.get("code", bool(self.repo)))
        self.description = data.get("description") or ""

    def __repr__(self):
        return f"<Scope {self.name} repo={self.repo} agents={self.agents}>"


class Check:
    """One row of the Definition-of-Done matrix for a scope."""

    def __init__(self, scope: str, data: dict):
        self.scope = scope
        self.id = str(data.get("id") or data.get("name") or "check")
        self.title = str(data.get("title") or self.id)
        self.command = str(data.get("command") or "")
        self.cwd = data.get("cwd") or None
        self.available = bool(data.get("available", True))
        self.note = data.get("note") or ""
        self.blocked_by = data.get("blocked_by") or None  # ticket that will make it available
        self.when = data.get("when") or ""                # e.g. "only for component work"

    def line(self) -> str:
        where = f" (in {self.cwd})" if self.cwd else ""
        state = "available" if self.available else "UNAVAILABLE"
        tail = f" - {self.note}" if self.note else ""
        if not self.available and self.blocked_by:
            tail = f" - see {self.blocked_by}{tail}"
        return f"[{state}] {self.title}: {self.command}{where}{tail}"


class Config:
    def __init__(self, root: str, data: dict):
        self.root = root
        self.data = data

        project = data.get("project") or {}
        self.project_name = str(project.get("name") or os.path.basename(root) or "the project")
        self.project_description = str(project.get("description") or "")
        self.forge_version = str(data.get("forge_version") or "0")

        paths = {**DEFAULT_PATHS, **(data.get("paths") or {})}
        self.tracker_rel = paths["tracker"].strip("/")
        self.kb_rel = paths["kb"].strip("/")
        self.lessons_rel = paths["lessons"].strip("/")

        repos = data.get("repos") or {}
        if not repos:
            repos = {"root": {"path": ".", "branch": "main"}}
        self.repos: dict[str, Repo] = {k: Repo(k, v or {}) for k, v in repos.items()}

        kb = data.get("kb") or {}
        kb_scopes = kb.get("scopes")
        self.kb_shared = str(kb.get("shared_scope") or "shared")

        scopes = data.get("scopes") or {}
        if not scopes:
            raise ConfigError("forge.json declares no scopes; a tracker needs at least one")
        self.scopes: dict[str, Scope] = {
            k: Scope(k, v or {}, self.kb_shared) for k, v in scopes.items()
        }

        self.kb_scopes: list[str] = list(kb_scopes) if kb_scopes else sorted(
            {s.kb_scope for s in self.scopes.values()} | {self.kb_shared}
        )
        locked = kb.get("locked_types") or {"api-contract": [self.kb_shared]}
        self.kb_locked_types: dict[str, set[str]] = {
            t: set(v if isinstance(v, list) else [v]) for t, v in locked.items()
        }

        self.checks_data = data.get("checks") or {}
        git = data.get("git") or {}
        self.branch_prefixes = list(git.get("branch_prefixes") or
                                    ["feat", "fix", "chore", "style", "refactor", "docs", "test", "perf"])
        self.require_refs_trailer = bool(git.get("require_refs_trailer", True))
        self.commit_style = str(git.get("commit_style") or "conventional-third-person")
        self.never_commit = list(git.get("never_commit") or
                                 [".env", "node_modules/", "vendor/", "build/", "dist/", ".idea/"])
        self.pr_required = bool(git.get("pull_requests", True))

        self.attribution = bool(data.get("attribution", True))

        policy = data.get("policy") or {}
        self.stale_claim_hours = int(policy.get("stale_claim_hours", 24))
        self.test_first = bool(policy.get("test_first", True))
        self.require_docs = bool(policy.get("require_docs", True))
        # false only while a project upgraded mid-flight drains its board; see
        # SCHEMA.md §10 and `forge doctor`
        self.spec_first = bool(policy.get("spec_first", True))
        # false only while a project upgraded mid-flight drains its board, for
        # the same reason as spec_first above
        self.require_lessons = bool(policy.get("require_lessons", True))
        self.lesson_budget = int(policy.get("lesson_budget", DEFAULT_LESSON_BUDGET))
        self.lesson_stale_days = int(policy.get("lesson_stale_days",
                                                DEFAULT_LESSON_STALE_DAYS))
        self.models = dict(policy.get("models") or {})

    def model_for(self, role: str) -> str:
        """The model tier an agent file is rendered with. Not project
        vocabulary, but it does belong to the project, so it lives in
        forge.json rather than in the payload."""
        return str(self.models.get(role) or DEFAULT_MODELS.get(role, "sonnet"))

    # ---- derived vocabulary ------------------------------------------------

    @property
    def scope_names(self) -> list[str]:
        return list(self.scopes)

    @property
    def code_scopes(self) -> list[str]:
        return [n for n, s in self.scopes.items() if s.code]

    @property
    def agents(self) -> list[str]:
        out = ["pm", "qa"]
        for s in self.scopes.values():
            for a in s.agents:
                if a not in out:
                    out.append(a)
        return out

    @property
    def scope_owner(self) -> dict[str, set[str]]:
        return {n: set(s.agents) for n, s in self.scopes.items()}

    def repo_of_scope(self, scope: str) -> Repo | None:
        s = self.scopes.get(scope)
        if s is None or not s.repo:
            return None
        return self.repos.get(s.repo)

    def unit_of_scope(self, scope: str) -> str | None:
        """The working tree a scope occupies. Two scopes sharing a unit cannot
        both be in flight - that is the one-checkout rule, generalised."""
        repo = self.repo_of_scope(scope)
        return repo.name if repo else None

    def kb_scope_of(self, scope: str) -> str:
        s = self.scopes.get(scope)
        return s.kb_scope if s else self.kb_shared

    def checks(self, scope: str) -> list[Check]:
        rows = self.checks_data.get(scope) or []
        return [Check(scope, r) for r in rows]

    def credit(self, kind: str = "markdown") -> str:
        """The signature line, in the dialect of the file being written."""
        if not self.attribution:
            return ""
        if kind == "comment":
            return (f"<!-- Generated by {FORGE_NAME} - {FORGE_URL} - "
                    f"edit forge.json and re-run, do not edit this file -->")
        return f"_Kept by [{FORGE_NAME}]({FORGE_URL})._"

    def tracker_dir(self) -> str:
        return os.path.join(self.root, *self.tracker_rel.split("/"))

    def kb_dir(self) -> str:
        return os.path.join(self.root, *self.kb_rel.split("/"))

    def lessons_dir(self) -> str:
        return os.path.join(self.root, *self.lessons_rel.split("/"))

    def lesson_scopes(self) -> list[str]:
        """Where a lesson may be filed: any tracker scope, or every scope."""
        return list(self.scopes) + [LESSON_ALL]

    def role_of_agent(self, agent: str) -> str:
        """Which of the three identities an agent file speaks for. A delegate
        inherits its principal's role, exactly as it inherits its `assignee`."""
        agent = AGENT_ALIASES.get(agent, agent)
        if agent in ("pm", "qa"):
            return agent
        return "engineer"

    def scope_of_agent(self, agent: str) -> str | None:
        """The scope an agent owns, or None for pm and qa, who own them all.

        pm and qa are named in `scopes` too - a non-code scope usually lists
        them as its implementers - so the special case comes first, or `pm`
        would be handed only the rules of whichever scope happened to list it."""
        agent = AGENT_ALIASES.get(agent, agent)
        if agent in ("pm", "qa"):
            return None
        for name, s in self.scopes.items():
            if agent in s.agents:
                return name
        return None

    # ---- self-validation ---------------------------------------------------

    def problems(self) -> list[str]:
        out: list[str] = []
        for name, s in self.scopes.items():
            if s.repo and s.repo not in self.repos:
                out.append(f"scopes.{name}.repo: '{s.repo}' is not a key of `repos`")
            if not s.agents:
                out.append(f"scopes.{name}.agent: no agent can implement this scope")
            if s.kb_scope not in self.kb_scopes:
                out.append(f"scopes.{name}.kb_scope: '{s.kb_scope}' is not in kb.scopes")
        for agent in self.agents:
            if agent in ("pm", "qa"):
                continue
            path = os.path.join(self.root, ".claude", "agents", f"{agent}.md")
            if not os.path.exists(path):
                out.append(f"agents: '{agent}' owns a scope but .claude/agents/{agent}.md is missing")
        for scope in self.scopes:
            if scope in self.checks_data:
                continue
            out.append(f"checks.{scope}: no Definition-of-Done rows; qa has nothing to run")
        for t, scopes in self.kb_locked_types.items():
            if t not in KB_TYPES:
                out.append(f"kb.locked_types.{t}: '{t}' is not a knowledge-base type")
            for s in scopes:
                if s not in self.kb_scopes:
                    out.append(f"kb.locked_types.{t}: '{s}' is not in kb.scopes")
        if not os.path.isdir(self.tracker_dir()):
            out.append(f"paths.tracker: {self.tracker_rel}/ does not exist")
        elif not os.path.isdir(os.path.join(self.tracker_dir(), "specs")):
            out.append(f"paths.tracker: {self.tracker_rel}/specs/ does not exist - "
                       "run `forge upgrade` to create it")
        if not self.spec_first:
            out.append("policy.spec_first: off - tickets may reach writing_tests "
                       "unspecified. Turn it on once the board predating the gate "
                       "has drained; `agile.py lint` names what still would fail.")
        for agent in sorted(AGENT_ALIASES):
            if not os.path.isfile(os.path.join(self.root, ".claude", "agents", f"{agent}.md")):
                out.append(f"agents: '{agent}' is dispatched by the gate contract but "
                           f".claude/agents/{agent}.md is missing - run `forge agents --force`")
        for role, model in sorted(self.models.items()):
            if role not in MODEL_ROLES:
                out.append(f"policy.models.{role}: '{role}' is not a model role "
                           f"({', '.join(MODEL_ROLES)})")
        if not os.path.isdir(self.kb_dir()):
            out.append(f"paths.kb: {self.kb_rel}/ does not exist")
        if LESSON_ALL in self.scopes:
            out.append(f"scopes.{LESSON_ALL}: '{LESSON_ALL}' is reserved - a lesson filed "
                       "there addresses every scope, so no scope may be called that")
        if not os.path.isdir(self.lessons_dir()):
            out.append(f"paths.lessons: {self.lessons_rel}/ does not exist - "
                       "run `forge upgrade` to create it")
        if self.lesson_budget < 1:
            out.append("policy.lesson_budget: must be at least 1 - set "
                       "policy.require_lessons false to switch the layer off instead")
        if not self.require_lessons:
            out.append("policy.require_lessons: off - a ticket may close without "
                       "recording what it taught. Turn it on once the board "
                       "predating the gate has drained.")
        return out


# --------------------------------------------------------------------------
# locating and loading
# --------------------------------------------------------------------------

def find_root(explicit: str | None = None) -> str:
    """Walk up for forge.json. An explicit path, then $CLAUDE_PROJECT_DIR, then
    the script's own location, then the cwd."""
    candidates = []
    if explicit:
        candidates.append(os.path.abspath(explicit))
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        candidates.append(os.path.abspath(env))
    candidates.append(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.path.abspath(os.getcwd()))

    for start in candidates:
        cur = start
        while True:
            if os.path.exists(os.path.join(cur, CONFIG_NAME)):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    raise SystemExit(
        f"fatal: cannot locate {CONFIG_NAME}. The harness is installed by "
        "`forge init`, which writes it at the repository root."
    )


_cache: dict[str, Config] = {}


def load(root: str | None = None) -> Config:
    root = find_root(root)
    if root in _cache:
        return _cache[root]
    path = os.path.join(root, CONFIG_NAME)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"fatal: {path}: {exc}")
    try:
        cfg = Config(root, data)
    except ConfigError as exc:
        raise SystemExit(f"fatal: {path}: {exc}")
    _cache[root] = cfg
    return cfg


# --------------------------------------------------------------------------
# CLI - `forgecfg.py` doubles as the inspector the agents call
# --------------------------------------------------------------------------

USAGE = """forge.py - inspect this project's harness configuration

    scopes                 every scope, its repo, agent and knowledge-base scope
    checks [<scope>]       the Definition-of-Done matrix, from forge.json
    repos                  every git working tree the harness knows about
    agents                 the role agents this project declares
    doctor                 validate forge.json against the files on disk
    credit                 the attribution line forge signs generated files with
    json                   the raw configuration
"""


def _cmd_scopes(cfg: Config) -> int:
    for name, s in cfg.scopes.items():
        repo = cfg.repo_of_scope(name)
        where = f"{repo.path}@{repo.branch}" if repo else "-"
        print(f"{name}\trepo={where}\tagent={','.join(s.agents) or '-'}\t"
              f"kb={s.kb_scope}\tcode={'yes' if s.code else 'no'}"
              + (f"\t{s.stack}" if s.stack else ""))
    return 0


def _cmd_checks(cfg: Config, scope: str | None) -> int:
    scopes = [scope] if scope else list(cfg.scopes)
    if scope and scope not in cfg.scopes:
        print(f"fatal: unknown scope '{scope}', expected one of {cfg.scope_names}", file=sys.stderr)
        return 1
    rc = 0
    for s in scopes:
        rows = cfg.checks(s)
        print(f"# scope: {s}")
        if not rows:
            print("  (no checks declared - add them to forge.json `checks`)")
            rc = 2
        for c in rows:
            print(f"  {c.line()}")
    return rc


def _cmd_repos(cfg: Config) -> int:
    for name, r in cfg.repos.items():
        kind = "submodule" if r.submodule else "root"
        print(f"{name}\t{r.path}\t{r.branch}\t{kind}\t{r.remote or '-'}")
    return 0


def _cmd_doctor(cfg: Config) -> int:
    problems = cfg.problems()
    for p in problems:
        print(f"forge.json:{p}")
    if not problems:
        print(f"doctor: clean - {len(cfg.scopes)} scope(s), {len(cfg.repos)} repo(s), "
              f"{len(cfg.agents)} agent(s)")
    return 2 if problems else 0


def main(argv: list[str]) -> int:
    args = list(argv[1:])
    root = None
    if "--root" in args:
        i = args.index("--root")
        root = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0 if args else 1
    cfg = load(root)
    cmd = args[0]
    if cmd == "scopes":
        return _cmd_scopes(cfg)
    if cmd == "checks":
        return _cmd_checks(cfg, args[1] if len(args) > 1 else None)
    if cmd == "repos":
        return _cmd_repos(cfg)
    if cmd == "agents":
        print("\n".join(cfg.agents))
        return 0
    if cmd == "doctor":
        return _cmd_doctor(cfg)
    if cmd == "credit":
        line = cfg.credit()
        print(line if line else "attribution is off (forge.json: \"attribution\": false)")
        return 0
    if cmd == "json":
        print(json.dumps(cfg.data, indent=2, sort_keys=True))
        return 0
    print(f"fatal: unknown command '{cmd}'", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
