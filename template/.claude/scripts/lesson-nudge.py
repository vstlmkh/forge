#!/usr/bin/env python3
"""PostToolUse nudge: a ticket moving backwards has just taught something.

A bounce - review back to in_progress, in_progress back to writing_tests - is
the only evidence this harness generates that the *process* went wrong rather
than the code. It is also the moment the agent still knows why. By gate 5,
where `lessons:` is required, whoever bounced has moved on and the reason has
decayed into one line of '## Log'.

So this fires on the edit itself. It reads the transition out of the edit's own
before/after strings, which the compare-and-swap protocol in `agile-artifacts`
guarantees are there, and says what is owed. It never blocks: a bounce is
correct behaviour, and the lesson is the point, not the permission.

Silent unless a ticket moved backwards.
Exit codes: 0 nothing to report, 2 feedback on stderr for the model.
"""

import json
import os
import re
import sys

sys.dont_write_bytecode = True   # never leave __pycache__ in the repo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATUS_RE = re.compile(r"^status:\s*(\S+)\s*$", re.MULTILINE)


def statuses(text: str) -> list[str]:
    return STATUS_RE.findall(text or "")


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
        if not cfg.require_lessons:
            return 0

        # The ladder a ticket climbs. A move to a lower rung is a bounce; a move
        # to a terminal status is not, however far back it looks.
        order = ["todo", "speccing", "writing_tests", "in_progress", "review", "verify", "done"]
        pairs = []
        edits = tool_input.get("edits")
        if isinstance(edits, list):
            for e in edits:
                if isinstance(e, dict):
                    pairs.append((e.get("old_string") or "", e.get("new_string") or ""))
        else:
            pairs.append((tool_input.get("old_string") or "",
                          tool_input.get("new_string") or ""))

        bounce = None
        for old, new in pairs:
            was, now = statuses(old), statuses(new)
            if not was or not now:
                continue
            if was[0] in order and now[0] in order and order.index(now[0]) < order.index(was[0]):
                bounce = (was[0], now[0])
                break
        if bounce is None:
            return 0

        with open(path, encoding="utf-8") as fh:
            fm = agile.parse_frontmatter(fh.read())
        tid = fm.get("id") or os.path.basename(norm)
        scope = fm.get("scope") or "<scope>"
        was, now = bounce

        print(
            f"{tid} just went {was} -> {now}. That bounce is the one signal this harness "
            f"produces that the process went wrong rather than the code, and you are the "
            f"only one who still knows why.\n"
            f"Record it now, while the reason is in front of you:\n"
            f"  python3 .claude/scripts/lessons.py list --scope {scope}\n"
            f"  # confirm an existing rule rather than filing a near-duplicate:\n"
            f"  python3 .claude/scripts/lessons.py confirm <LESSON-NNNN> --ticket {tid}\n"
            f"  # or file the new one, then put its id in the ticket's `lessons:`\n"
            f"  python3 .claude/scripts/lessons.py new \"<two to five words>\" "
            f"--scope {scope} --roles <role> --ticket {tid} --rule \"<one imperative line>\"\n"
            f"If nothing here is learnable - the bounce was noise, not a pattern - say so in "
            f"lessons_waiver: NO-LESSON (<reason>). qa judges that claim at gate 5 and will "
            f"not accept it from a ticket that bounced without an argument.",
            file=sys.stderr,
        )
        return 2
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
