#!/usr/bin/env python3
"""PostToolUse nudge: catch an undocumented ticket at the moment it moves.

`agile.py lint` already refuses a ticket that reaches review with an empty
`docs:` - but it runs at the end of a turn, long after the transition. This
fires on the edit itself, while the agent still has the context to write the
note rather than a waiver.

Silent unless there is something to say. Never blocks the edit.
Exit codes: 0 nothing to report, 2 feedback on stderr for the model.
"""

import json
import os
import re
import sys

sys.dont_write_bytecode = True   # never leave __pycache__ in the repo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WATCHED = ("review", "verify", "done")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool_input = payload.get("tool_input") or {}
        path = tool_input.get("file_path") or tool_input.get("path")
        if not isinstance(path, str):
            return 0

        import agile
        import forge

        root = agile.find_root(os.environ.get("CLAUDE_PROJECT_DIR"))
        cfg = forge.load(root)
        norm = os.path.normpath(path).replace("\\", "/")
        if not re.search(re.escape(cfg.tracker_rel) + r"/(tasks|bugs)/[^/]+\.md$", norm):
            return 0
        if not os.path.exists(path):
            return 0

        with open(path, encoding="utf-8") as fh:
            fm = agile.parse_frontmatter(fh.read())
        status = fm.get("status")
        if status not in WATCHED:
            return 0

        entries = fm.get("docs") or []
        entries = entries if isinstance(entries, list) else [entries]
        entries = [e for e in entries if e]
        waiver = fm.get("docs_waiver")

        tid = fm.get("id") or os.path.basename(norm)
        if not entries and waiver is None:
            print(
                f"{tid} is now '{status}' with an empty `docs:` and no waiver, which "
                f"`agile.py lint` will reject.\n"
                "This work either revealed durable knowledge or it did not. If it did, file it:\n"
                "  python3 .claude/scripts/kb.py new <type> <scope> \"<description>\" "
                f"--ticket {tid}\n"
                "  # types: business-rule troubleshooting overview integration "
                "api-contract decision runbook data-model\n"
                "then list the note in `docs:`. If it genuinely did not, say so honestly:\n"
                "  docs_waiver: NO-DOCS (<why this work left nothing worth knowing>)\n"
                f"One finding per note, and cross-link it in `## Related` - see "
                f"{cfg.kb_rel}/README.md.",
                file=sys.stderr,
            )
            return 2

        if status == "done" and entries:
            stale = []
            for e in entries:
                cand = os.path.join(cfg.kb_dir(), str(e))
                if os.path.exists(cand):
                    with open(cand, encoding="utf-8") as fh:
                        nfm = agile.parse_frontmatter(fh.read())
                    if str(nfm.get("updated")) != str(fm.get("updated")):
                        stale.append(str(e))
            if stale:
                print(
                    f"{tid} closed on {fm.get('updated')}, but these notes it claims were not "
                    "touched today:\n  " + "\n  ".join(stale) + "\n"
                    "Actualising the knowledge base is part of closing: correct anything the work "
                    "disproved, bump `updated:`, add the ticket to `tickets:`, and keep "
                    "`## Related` current. If a note genuinely needed no change, drop it from "
                    "`docs:` or leave it - but check rather than assume.",
                    file=sys.stderr,
                )
                return 2
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
