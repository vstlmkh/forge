#!/usr/bin/env python3
"""PreToolUse guard: a new ticket reaches the board only if the operator says so.

An agent opens tickets far more readily than a person does - a `qa` run that
trips over an unrelated defect, a `pm` that splits one request into six tasks, an
engineer that spots a follow-up. Each one is individually defensible and
collectively a board nobody trusts, because the backlog stops being the set of
things the project decided to do and becomes the set of things an agent noticed.

So the *creation* of a ticket is put in front of the operator. This guard fires
only on a write that would create a file under <tracker>/{backlog,tasks,bugs}/
that does not exist yet; every later edit of that ticket is the gates' business
and passes straight through. The decision returned is `ask`, not `deny`: the
operator approves in one keystroke when the ticket is wanted, and the prompt
carries the ID, the scope and the title so the answer does not require opening
the file.

A project that does not want the prompt sets `policy.ticket_consent` to `off`
in forge.json, which restores the previous behaviour everywhere at once.

Any failure here allows the write - a guard that breaks the session is worse
than a guard that misses one file.

Exit code 0 always; the decision is the JSON on stdout.
"""

import json
import os
import re
import sys

sys.dont_write_bytecode = True   # never leave __pycache__ in the repo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

KIND_OF_DIR = {"backlog": "epic or story", "tasks": "task", "bugs": "bug"}


def targets(payload) -> list[str]:
    tool_input = payload.get("tool_input") or {}
    out = [tool_input.get("file_path"), tool_input.get("notebook_path"), tool_input.get("path")]
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict):
            out.append(edit.get("file_path"))
    return [t for t in out if isinstance(t, str) and t]


def field(content: str, name: str) -> str:
    m = re.search(r"^%s:[ \t]*(.+?)[ \t]*$" % re.escape(name), content, re.MULTILINE)
    if not m:
        return ""
    return m.group(1).strip().strip("'\"")


def summary(path: str, content: str, sub: str) -> str:
    """One line the operator can decide on without opening anything."""
    ident = field(content, "id") or os.path.basename(path).split("-")[0:2]
    if not isinstance(ident, str):
        ident = "-".join(ident)
    bits = [ident or os.path.basename(path)]
    kind = field(content, "kind") or KIND_OF_DIR.get(sub, "ticket")
    bits.append(kind)
    for name in ("scope", "priority", "severity"):
        value = field(content, name)
        if value and value not in ("null", "~"):
            bits.append(value)
    head = "  ".join(b for b in bits if b)
    title = field(content, "title")
    return f"{head}\n  {title}" if title else head


def reason(rel: str, body: str) -> str:
    return (
        "A new ticket would be added to the board:\n\n"
        f"  {body}\n  {rel}\n\n"
        "Approve to open it. Deny if it does not belong on the board - the agent is "
        "told to say in one line what it wanted to file and carry on, rather than "
        "writing it anywhere else.\n"
        "To stop being asked, set \"ticket_consent\": \"off\" under `policy` in forge.json."
    )


def main() -> int:
    try:
        import forge
        cfg = forge.load(os.environ.get("CLAUDE_PROJECT_DIR"))
        if cfg.ticket_consent == "off":
            return 0
        payload = json.load(sys.stdin)
        pattern = re.compile(re.escape(cfg.tracker_rel) + r"/(backlog|tasks|bugs)/[^/]+\.md$")
        for path in targets(payload):
            norm = os.path.normpath(path).replace("\\", "/")
            m = pattern.search(norm)
            if not m:
                continue
            full = path if os.path.isabs(path) else os.path.join(cfg.root, norm)
            if os.path.exists(full):
                continue        # an existing ticket is the gates' business
            content = (payload.get("tool_input") or {}).get("content") or ""
            out = {"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason(norm, summary(norm, content, m.group(1))),
            }}
            print(json.dumps(out))
            return 0
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
