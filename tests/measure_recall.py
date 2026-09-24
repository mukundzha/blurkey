"""Measure recall on synthetic fixtures with real OCR.

Usage: PYTHONPATH=src python3 tests/measure_recall.py
Uses only documented fake keys. Prints honest recall numbers for README.
"""
import sys
from pathlib import Path

sys.path.insert(0, "src")

from PIL import Image

from blurkey import detect as _detect
from blurkey import ocr as _ocr

FIX = Path(__file__).parent / "fixtures"

CASES = [
    ("terminal-dark.png", {"aws", "email", "ipv4"}),
    ("terminal-light.png", {"aws", "email", "ipv4"}),
    ("editor-dark.png", {"aws", "email", "ipv4"}),
    ("browser-light.png", {"aws", "email", "ipv4"}),
    ("clean.png", set()),
]


def main() -> int:
    if not FIX.exists():
        print("run tests/make_fixtures.py first")
        return 2
    tot_exp = tot_found = 0
    fps = 0
    for name, expected in CASES:
        p = FIX / name
        if not p.exists():
            print(f"missing {p}")
            continue
        img = Image.open(p).convert("RGB")
        lines = _ocr.ocr_image(img, min_conf=0.0)
        found: set[str] = set()
        for ln in lines:
            for m in _detect.detect_line(ln.text):
                found.add(m.kind)
        print(f"{name}: OCR={[l.text for l in lines]}")
        print(f"  expected~{sorted(expected)} found={sorted(found)}")
        for k in expected:
            tot_exp += 1
            if k in found:
                tot_found += 1
        if not expected and found:
            fps += 1
    print(f"\nrecall {tot_found}/{tot_exp} = {tot_found/max(tot_exp,1):.0%}")
    print(f"clean false-positive files: {fps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
