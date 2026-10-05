#!/usr/bin/env python3
"""Generates the forge mark in a light and a dark variant.

    python3 assets/logo.py

Same two-file arrangement as the banner, and for the same reason: GitHub only
switches between images with `<picture><source media="(prefers-color-scheme:
dark)">`, and a `<style>` inside an SVG served as an `<img>` may be dropped by
its sanitiser. Everything is a presentation attribute.

The mark is the product's one idea: six gates around a ring, four cleared and
two still ahead. Nothing else is in it - no anvil, no monogram - because at
16px there is room for exactly one idea, and this is the one that distinguishes
a harness from a task runner.

Geometry worth not "tidying":

- the run of cleared gates starts at twelve o'clock and goes clockwise, so the
  mark reads as progress rather than as a spinner frozen mid-turn;
- the gaps are wide (14 degrees) and the caps are butt, not round. Narrow gaps
  and round caps close up at favicon size and the six gates become one circle,
  which is the whole mark gone;
- the ring is open. A dot in the middle reads as a record button.
"""

import math
import os

SIZE = 64
R = 22                      # ring radius on the 64px artboard
STROKE = 10                 # thick enough to survive being scaled to 16px
GAP = 14                    # degrees of empty space between gates
GATES = 6
CLEARED = 4                 # how many the mark shows as passed

THEMES = {
    "light": dict(accent="#c2410c", ink="#15181d", ink_opacity="0.20"),
    "dark":  dict(accent="#fb923c", ink="#e6edf3", ink_opacity="0.26"),
}


def arc(i: int) -> str:
    """The path for gate `i`, swept clockwise from twelve o'clock."""
    c = SIZE / 2
    span = 360 / GATES
    a0 = math.radians(-90 + i * span + GAP / 2)
    a1 = math.radians(-90 + (i + 1) * span - GAP / 2)
    x0, y0 = c + R * math.cos(a0), c + R * math.sin(a0)
    x1, y1 = c + R * math.cos(a1), c + R * math.sin(a1)
    return f'M{x0:.2f} {y0:.2f} A{R} {R} 0 0 1 {x1:.2f} {y1:.2f}'


def mark(t: dict, x: float = 0, y: float = 0, size: float = SIZE) -> str:
    """The mark as an SVG fragment, so the banner can place it in its header
    without a second copy of the geometry living there."""
    k = size / SIZE
    o = [f'<g transform="translate({x} {y}) scale({k:.4f})" fill="none" '
         f'stroke-width="{STROKE}" stroke-linecap="butt">']
    for i in range(GATES):
        if i < CLEARED:
            o.append(f'<path d="{arc(i)}" stroke="{t["accent"]}"/>')
        else:
            o.append(f'<path d="{arc(i)}" stroke="{t["ink"]}" '
                     f'opacity="{t["ink_opacity"]}"/>')
    o.append('</g>')
    return "\n".join(o)


def build(t: dict) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
            f'width="{SIZE}" height="{SIZE}" role="img" '
            f'aria-label="forge - six gates, four of them cleared">\n'
            f'{mark(t)}\n</svg>\n')


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    for name, palette in THEMES.items():
        path = os.path.join(here, f"logo-{name}.svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(build(palette))
        print(f"wrote {os.path.relpath(path, os.path.dirname(here))}")


if __name__ == "__main__":
    main()
