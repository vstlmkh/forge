#!/usr/bin/env python3
"""UserPromptSubmit hook: put the knowledge base in front of the development cycle.

When a turn starts one of the cycle commands, this prints the knowledge base's
current coverage and the consult obligation. Stdout from a UserPromptSubmit hook
is added to the turn's context, so the agent sees what knowledge already exists
*before* it starts grooming, implementing or closing anything - which is the one
moment at which consulting the knowledge base is cheap.

Silent for every other prompt. Never blocks: any failure prints nothing.
"""

import json
import os
import re
import sys

sys.dont_write_bytecode = True   # never leave __pycache__ in the repo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TRIGGER = re.compile(
    r"/(agile:(groom|work|next|bug|close|verify)|kb:(consult|new|audit|lint))\b|"
    r"\bgroom\b|\bdocument\b|\bдокумент",
    re.IGNORECASE,
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        prompt = payload.get("prompt") or ""
        if not TRIGGER.search(prompt):
            return 0

        import kb

        root = kb.agile.find_root(os.environ.get("CLAUDE_PROJECT_DIR"))
        cfg = kb.forgecfg.load(root)
        notes, fatal = kb.load_notes(root)
        if fatal:
            return 0

        current = [n for n in notes if n.status != "superseded"]
        lines = [
            "<knowledge-base-state>",
            f"{cfg.kb_rel}/ holds {len(current)} current note(s). This is the project's durable "
            "knowledge and consulting it is a required step of the cycle, not optional reading.",
            "",
            "Coverage (type x scope, zeros are gaps worth filling when the work touches them):",
        ]
        for t in sorted(kb.TYPES):
            cells = []
            for s in cfg.kb_scopes:
                locked = cfg.kb_locked_types.get(t)
                if locked and s not in locked:
                    continue
                k = sum(1 for n in current if n.fm.get("type") == t and n.fm.get("scope") == s)
                cells.append(f"{s}:{k}")
            lines.append(f"  {t:<16} " + "  ".join(cells))
        lines += [
            "",
            "Before writing a ticket or touching business logic, integrations, domain "
            "workflows or architecture:",
            "  python3 .claude/scripts/kb.py find <keyword> [...]      # what do we already know?",
            "  python3 .claude/scripts/kb.py for-ticket <TICKET-ID>    # notes bound to the ticket",
            "After the work reveals something durable:",
            "  python3 .claude/scripts/kb.py new <type> <scope> \"<description>\" --ticket <ID>",
            "  # then list it in the ticket's docs: and cross-link it in ## Related",
            f"Rules: {cfg.kb_rel}/README.md. Procedure: .claude/skills/project-knowledge/SKILL.md.",
            "A ticket that reaches review with an empty docs: and no "
            "docs_waiver: NO-DOCS (<reason>) fails `agile.py lint`.",
            "</knowledge-base-state>",
        ]
        print("\n".join(lines))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
