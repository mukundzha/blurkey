"""Map a character range within an OCR line to pixel coordinates.

OCR boxes cover whole lines, so we interpolate proportionally
and pad slightly. Monospace assumption is imperfect but safe:
we slightly over-cover rather than under-cover.
"""
from __future__ import annotations


def locate_match(
    line_text: str,
    line_box: tuple[float, float, float, float],
    start: int,
    end: int,
    *,
    pad: int = 4,
    img_w: int | None = None,
    img_h: int | None = None,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = line_box
    n = max(len(line_text), 1)
    s = max(0, min(start, n))
    e = max(0, min(end, n))
    if e <= s:
        e = min(n, s + 1)
    w = x1 - x0
    bx0 = x0 + w * (s / n)
    bx1 = x0 + w * (e / n)
    # ensure minimum 1px width and apply pad
    if bx1 - bx0 < 1:
        bx1 = bx0 + 1
    bx0 -= pad
    bx1 += pad
    y0 -= pad
    y1 += pad
    ix0, iy0, ix1, iy1 = int(bx0), int(y0), int(bx1), int(y1)
    if img_w is not None:
        ix0 = max(0, ix0)
        ix1 = min(img_w, ix1)
    if img_h is not None:
        iy0 = max(0, iy0)
        iy1 = min(img_h, iy1)
    return (ix0, iy0, ix1, iy1)


def merge_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """Merge overlapping boxes (union)."""
    if not boxes:
        return []
    ordered = sorted(boxes)
    out = [ordered[0]]
    for b in ordered[1:]:
        lx0, ly0, lx1, ly1 = out[-1]
        x0, y0, x1, y1 = b
        if x0 <= lx1 and y0 <= ly1 and ly0 <= y1:
            # overlapping (rough): union
            out[-1] = (min(lx0, x0), min(ly0, y0), max(lx1, x1), max(ly1, y1))
        else:
            out.append(b)
    return out
