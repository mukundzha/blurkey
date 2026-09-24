"""Redaction: draw opaque black bars onto a fresh image (no metadata survives)."""
from __future__ import annotations

from PIL import Image, ImageDraw


def fresh_copy(img: Image.Image) -> Image.Image:
    """Return a metadata-free RGB copy."""
    rgb = img.convert("RGB")
    fresh = Image.new("RGB", rgb.size)
    fresh.paste(rgb)
    return fresh


def apply_boxes(
    img: Image.Image,
    boxes: list[tuple[int, int, int, int]],
    *,
    preview: bool = False,
) -> Image.Image:
    out = fresh_copy(img)
    d = ImageDraw.Draw(out)
    for x0, y0, x1, y1 in boxes:
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        if x1 <= x0 or y1 <= y0:
            continue
        if preview:
            d.rectangle([x0, y0, x1, y1], outline=(255, 0, 0), width=2)
        else:
            d.rectangle([x0, y0, x1, y1], fill=(0, 0, 0))
    return out


def is_uniform_black(img: Image.Image, box: tuple[int, int, int, int]) -> bool:
    x0, y0, x1, y1 = box
    crop = img.crop((x0, y0, x1, y1)).convert("RGB")
    colors = crop.getcolors(maxcolors=1 << 20)
    return colors is not None and len(colors) == 1 and colors[0][1] == (0, 0, 0)
