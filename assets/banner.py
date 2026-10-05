#!/usr/bin/env python3
"""Generates the README banner in a light and a dark variant.

    python3 assets/banner.py

Two files instead of one because GitHub picks between them with
`<picture><source media="(prefers-color-scheme: dark)">`, which is the only
theme switch it honours; CSS inside an SVG served as an `<img>` is not.
Everything is written as presentation attributes rather than a stylesheet,
since GitHub's SVG sanitiser is free to drop `<style>`.

The picture is the cycle itself, not decoration: the seven states a ticket
passes through, the six gates that sit on them, who holds each one, the three
ways it comes back, and the three records that make the harness work.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logo  # noqa: E402  - the mark's geometry lives in exactly one file

W, H = 1280, 620
SANS = "ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

def mark_palette(t: dict) -> dict:
    """The banner's palette, in the three keys the mark asks for."""
    return dict(accent=t["qa"], ink=t["text"], ink_opacity=t["mark_opacity"])


THEMES = {
    "light": dict(
        bg="#ffffff", panel="#f6f7f9", border="#d8dce1", text="#15181d",
        muted="#636c76", line="#b6bdc6",
        mark_opacity="0.20",
        qa="#c2410c", qa_bg="#fff3ec", qa_border="#f0b494",
        eng="#0f766e", eng_bg="#eefaf7", eng_border="#9ad3c9",
        you="#5b43b5", you_bg="#f2effc", you_border="#bfb0ea",
    ),
    "dark": dict(
        bg="#0d1117", panel="#151b23", border="#303840", text="#e6edf3",
        muted="#9198a1", line="#48505a",
        mark_opacity="0.26",
        qa="#fb923c", qa_bg="#2a1a10", qa_border="#7a4a22",
        eng="#5eead4", eng_bg="#0d2420", eng_border="#1f5a52",
        you="#b3a4f5", you_bg="#1b1830", you_border="#473d78",
    ),
}

# state, actor, actor colour key, one-line descriptor, the gate(s) it carries
STAGES = [
    ("todo", "pm", None, "groomed intent", None),
    ("speccing", "qa", "qa", "the brief, agreed", "G1"),
    ("writing_tests", "qa", "qa", "a test per REQ", "G2"),
    ("in_progress", "engineer", "eng", "makes them pass", "G3"),
    ("review", "qa + pm", "qa", "proved and filed", "G4·5·6"),
    ("verify", "you", "you", "awaiting acceptance", None),
    ("done", "you", "you", "merged, sha recorded", None),
]

RECORDS = [
    ("docs/agile/", "what we are doing",
     "epics, tasks, bugs, a generated board", "agile.py lint"),
    ("docs/knowledge/", "what we know",
     "eight typed, cross-linked note kinds", "kb.py lint"),
    ("forge.json", "what this project is made of",
     "repos, scopes, agents, runnable checks", "forge.py doctor"),
]

M = 56                      # page margin
NW, NG = 142, 28            # node width, gap
NY, NH = 216, 74            # node top, height
CW, CG = 370, 28            # record card width, gap
CY, CH = 474, 104


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, *, size=14, fill="#000", weight="400", family=SANS,
         anchor="start", spacing=None, opacity=None):
    extra = f' letter-spacing="{spacing}"' if spacing else ""
    extra += f' opacity="{opacity}"' if opacity else ""
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{extra}>'
            f'{esc(s)}</text>')


def node_x(i: int) -> int:
    return M + i * (NW + NG)


def build(t: dict) -> str:
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
         f'width="{W}" height="{H}" role="img" '
         f'aria-label="forge - the cycle a ticket goes through, and the three records behind it">',
         '<defs>',
         f'<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
         f'markerHeight="7" orient="auto-start-reverse">'
         f'<path d="M0,1 L9,5 L0,9 z" fill="{t["line"]}"/></marker>',
         '</defs>',
         f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>',
         f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="14" fill="none" '
         f'stroke="{t["border"]}"/>']

    # ---- header ----------------------------------------------------------
    # The mark carries the accent in the header, so the rule that used to sit
    # under the wordmark would be a second one saying the same thing.
    o.append(logo.mark(mark_palette(t), x=M, y=46, size=58))
    o.append(text(M + 58 + 20, 92, "forge", size=52, weight="700",
                  fill=t["text"], spacing="-1.5"))
    o.append(text(M, 142, "A reusable agent harness for software projects.",
                  size=19, fill=t["muted"]))

    chip_w, chip_x, chip_y = 300, W - M - 300, 56
    o.append(f'<rect x="{chip_x}" y="{chip_y}" width="{chip_w}" height="38" rx="8" '
             f'fill="{t["panel"]}" stroke="{t["border"]}"/>')
    o.append(text(chip_x + chip_w / 2, chip_y + 24, "forge init", size=15,
                  family=MONO, fill=t["text"], anchor="middle"))
    o.append(text(chip_x + chip_w / 2, chip_y + 58, "installs into any repository",
                  size=12, fill=t["muted"], anchor="middle"))

    # ---- the cycle -------------------------------------------------------
    o.append(text(M, 182, "SEVEN STATES, SIX GATES", size=11,
                  weight="600", fill=t["muted"], spacing="1.8"))

    for i, (state, actor, key, note, gate) in enumerate(STAGES):
        x = node_x(i)
        fill = t[f"{key}_bg"] if key else t["panel"]
        stroke = t[f"{key}_border"] if key else t["border"]
        label = t[key] if key else t["muted"]
        o.append(text(x + NW / 2, 206, actor, size=11, weight="600", fill=label,
                      anchor="middle", spacing="1.2"))
        o.append(f'<rect x="{x}" y="{NY}" width="{NW}" height="{NH}" rx="10" '
                 f'fill="{fill}" stroke="{stroke}"/>')
        o.append(text(x + NW / 2, NY + 28, state, size=14, family=MONO,
                      fill=t["text"], anchor="middle"))
        o.append(text(x + NW / 2, NY + 48, note, size=10.5, fill=t["muted"], anchor="middle"))
        # the gate the state carries, as a chip straddling its lower edge
        if gate:
            gw = 26 + 7.6 * (len(gate) - 2)
            gx, gy = x + NW / 2 - gw / 2, NY + NH - 10
            o.append(f'<rect x="{gx}" y="{gy}" width="{gw}" height="20" rx="10" '
                     f'fill="{t["bg"]}" stroke="{stroke}"/>')
            o.append(text(x + NW / 2, gy + 14, gate, size=11, weight="600",
                          family=MONO, fill=label, anchor="middle"))
        if i < len(STAGES) - 1:
            y = NY + NH / 2
            o.append(f'<path d="M{x + NW + 5} {y} L{x + NW + NG - 7} {y}" '
                     f'stroke="{t["line"]}" stroke-width="1.6" fill="none" marker-end="url(#a)"/>')

    # the two ways a ticket comes back; the label sits on the curve, over a
    # patch of background, so the edge reads as labelled rather than crossed
    def arc(src: int, dst: int, depth: int, label: str):
        top = NY + NH + 14
        x1, x2 = node_x(src) + NW / 2, node_x(dst) + NW / 2
        o.append(f'<path d="M{x1} {top} C{x1} {depth} {x2} {depth} {x2} {top + 2}" '
                 f'stroke="{t["line"]}" stroke-width="1.6" stroke-dasharray="5 4" '
                 f'fill="none" marker-end="url(#a)"/>')
        mid_x, mid_y = (x1 + x2) / 2, top + 0.75 * (depth - top)
        pad, tw = 9, len(label) * 6.3
        o.append(f'<rect x="{mid_x - tw / 2 - pad}" y="{mid_y - 11}" '
                 f'width="{tw + 2 * pad}" height="22" rx="6" fill="{t["bg"]}"/>')
        o.append(text(mid_x, mid_y + 4, label, size=12, fill=t["muted"], anchor="middle"))

    arc(4, 3, 338, "rejected")
    arc(3, 2, 382, "the test is wrong")
    arc(2, 1, 426, "the brief is wrong")

    # ---- the three records ----------------------------------------------
    o.append(text(M, 452, "AND THE THREE RECORDS BEHIND IT", size=11,
                  weight="600", fill=t["muted"], spacing="1.8"))

    for i, (name, what, detail, validator) in enumerate(RECORDS):
        x = M + i * (CW + CG)
        o.append(f'<rect x="{x}" y="{CY}" width="{CW}" height="{CH}" rx="12" '
                 f'fill="{t["panel"]}" stroke="{t["border"]}"/>')
        o.append(text(x + 20, CY + 32, name, size=15, family=MONO, fill=t["text"]))
        o.append(text(x + 20, CY + 56, what, size=13, fill=t["muted"]))
        o.append(text(x + 20, CY + 78, detail, size=12, fill=t["muted"], opacity="0.85"))
        o.append(text(x + CW - 20, CY + 32, validator, size=12, family=MONO,
                      fill=t["qa"], anchor="end"))

    o.append("</svg>")
    return "\n".join(o) + "\n"


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    for name, palette in THEMES.items():
        path = os.path.join(here, f"banner-{name}.svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(build(palette))
        print(f"wrote {os.path.relpath(path, os.path.dirname(here))}")


if __name__ == "__main__":
    main()
