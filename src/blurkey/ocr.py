"""OCR adapter returning TextLine(text, box, conf).

Wraps RapidOCR (ONNX, offline) so the engine can be swapped.
Models ship inside the wheel -> works fully offline after install.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from PIL import Image


@dataclass
class TextLine:
    text: str
    box: tuple[float, float, float, float]  # x0, y0, x1, y1
    conf: float


class OcrEngine(Protocol):
    def lines(self, img: Image.Image) -> list[TextLine]: ...


class RapidOcrEngine:
    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR

        self._engine = RapidOCR()

    def lines(self, img: Image.Image) -> list[TextLine]:
        rgb = img.convert("RGB")
        arr = np.array(rgb)
        result, _ = self._engine(arr)
        out: list[TextLine] = []
        if not result:
            return out
        for quad, text, conf in result:
            try:
                xs = [p[0] for p in quad]
                ys = [p[1] for p in quad]
                x0, x1 = min(xs), max(xs)
                y0, y1 = min(ys), max(ys)
                c = float(conf) if isinstance(conf, (int, float, str)) else 0.0
            except Exception:
                continue
            text = (text or "").strip()
            if not text:
                continue
            out.append(TextLine(text=text, box=(x0, y0, x1, y1), conf=c))
        return out


_engine: OcrEngine | None = None


def get_engine() -> OcrEngine:
    global _engine
    if _engine is None:
        _engine = RapidOcrEngine()
    return _engine


def set_engine(engine: OcrEngine | None) -> None:
    """Inject a fake engine for tests."""
    global _engine
    _engine = engine


def ocr_image(img: Image.Image, *, min_conf: float = 0.5) -> list[TextLine]:
    lines = get_engine().lines(img)
    return [ln for ln in lines if ln.conf >= min_conf]
