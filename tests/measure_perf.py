"""Benchmark GIF frame-diff + smoothing path (no OCR model needed).

Usage: PYTHONPATH=src python3 tests/measure_perf.py [--frames N]
Uses FakeEngine so it measures pipeline overhead, not OCR model speed.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

from PIL import Image

from blurkey import gif as _gif
from blurkey import ocr as _ocr
from blurkey.ocr import TextLine


def main() -> int:
    n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--frames" else 100
    frames = [Image.new("RGB", (640, 200), "white") for _ in range(n)]

    class E:
        def lines(self, img):
            return [TextLine("AKIAIOSFODNN7EXAMPLE", (10, 10, 300, 40), 0.99)]

    _ocr.set_engine(E())
    try:
        t0 = time.perf_counter()
        res = _gif.process_gif_frames(frames)
        dt = time.perf_counter() - t0
    finally:
        _ocr.set_engine(None)
    print(f"frames={res.n_frames} ocr_calls={res.ocr_calls} "
          f"hits={res.frames_with_hits} kinds={res.kinds} time={dt:.2f}s")
    print(f"target: 100-frame GIF pipeline overhead (excl. OCR model) well under 60s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
