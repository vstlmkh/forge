#!/usr/bin/env python3
"""PreToolUse guard: the generated INDEX.md files are never hand-edited.

Reads the Claude Code PreToolUse payload on stdin and denies any file-writing
tool whose target resolves to the INDEX.md of the tracker, the knowledge base or
the lessons. Every path comes from forge.json, so a project that moved one is
still covered.

Exit codes: 0 allow, 2 deny (stderr is fed back to the model).
"""

import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never block on a payload we cannot read

    try:
        import forge
        cfg = forge.load(os.environ.get("CLAUDE_PROJECT_DIR"))
        guarded = {
            f"{cfg.tracker_rel}/INDEX.md": (
                f"{cfg.tracker_rel}/INDEX.md is generated from the ticket frontmatter and must "
                "never be edited by hand. Change the ticket file instead, then run "
                "`python3 .claude/scripts/agile.py index`."
            ),
            f"{cfg.kb_rel}/INDEX.md": (
                f"{cfg.kb_rel}/INDEX.md is generated from the notes' frontmatter and must "
                "never be edited by hand. Change the note instead, then run "
                "`python3 .claude/scripts/kb.py index`."
            ),
            f"{cfg.lessons_rel}/INDEX.md": (
                f"{cfg.lessons_rel}/INDEX.md is generated from the lessons' frontmatter and "
                "must never be edited by hand. Change the lesson instead, then run "
                "`python3 .claude/scripts/lessons.py index`."
            ),
        }
    except Exception:
        return 0

    tool_input = payload.get("tool_input") or {}
    candidates = [
        tool_input.get("file_path"),
        tool_input.get("notebook_path"),
        tool_input.get("path"),
    ]
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict):
            candidates.append(edit.get("file_path"))

    for cand in candidates:
        if not cand or not isinstance(cand, str):
            continue
        norm = os.path.normpath(cand).replace("\\", "/")
        for path, message in guarded.items():
            if norm.endswith(path):
                print("Denied: " + message, file=sys.stderr)
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
