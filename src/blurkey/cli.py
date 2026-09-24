"""CLI: blurkey FILE [FILE...]"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image
from rich.console import Console

from . import detect as _detect
from . import gif as _gif
from . import locate as _locate
from . import ocr as _ocr
from . import redact as _redact
from . import report as _report
from . import __version__ as _version

STILL_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
GIF_EXTS = {".gif"}

console = Console()


def parse_kinds(s: str | None) -> set[str]:
    if not s:
        return set()
    out = set()
    for part in s.split(","):
        p = part.strip().lower()
        if p:
            if p not in _detect.VALID_KINDS:
                raise ValueError(f"unknown kind: {p} (valid: {', '.join(_detect.VALID_KINDS)})")
            out.add(p)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="blurkey",
        description="Find API keys/tokens/emails/IPs in screenshots and GIFs and cover them with black bars. 100% offline.",
    )
    p.add_argument("files", nargs="+", help="image files (png/jpg/webp/gif)")
    p.add_argument("-o", "--output", default=None, help="output path (single-file mode only)")
    p.add_argument("--out-dir", default=None, help="write redacted copies into this directory")
    p.add_argument("--force", action="store_true", help="allow overwriting existing outputs")
    p.add_argument("--in-place", action="store_true", help="overwrite original (opt-in)")
    p.add_argument("--preview", action="store_true", help="outline boxes in red instead of filling")
    p.add_argument("--check", action="store_true", help="write nothing; exit 1 if secrets found")
    p.add_argument("--json", action="store_true", dest="as_json", help="machine-readable report")
    p.add_argument("-q", "--quiet", action="store_true", help="only print errors and --json output")
    p.add_argument("--only", default=None, help="comma list of kinds to detect")
    p.add_argument("--skip", default=None, help="comma list of kinds to skip, e.g. --skip ipv4,email")
    p.add_argument("--allow", default=None, help="never redact matches of this regex")
    p.add_argument("--min-conf", type=float, default=0.5, help="OCR confidence floor 0-1 (default 0.5)")
    p.add_argument("--pad", type=int, default=4, help="extra pixels around each box (default 4, >=0)")
    p.add_argument("--frame-step", type=int, default=1, help="OCR every Nth GIF frame (default 1, >=1)")
    p.add_argument("--version", action="version", version=f"%(prog)s {_version}")
    return p


def default_output(path: Path) -> Path:
    return path.with_name(f"{path.stem}.redacted{path.suffix}")


def resolve_output(
    path: Path,
    *,
    output: str | None,
    out_dir: str | None,
    in_place: bool,
    force: bool,
) -> Path:
    """Centralize never-overwrite logic. Raises ValueError on misuse."""
    if in_place:
        return path
    if output and out_dir:
        raise ValueError("use only one of --output and --out-dir")
    if output:
        return Path(output)
    if out_dir:
        d = Path(out_dir)
        base = d / f"{path.stem}.redacted{path.suffix}"
        if force or not base.exists():
            return base
        c = 1
        while True:
            cand = d / f"{path.stem}.redacted-{c}{path.suffix}"
            if not cand.exists():
                return cand
            c += 1
    out_p = default_output(path)
    if force or not out_p.exists():
        return out_p
    c = 1
    while True:
        cand = path.with_name(f"{path.stem}.redacted-{c}{path.suffix}")
        if force or not cand.exists():
            return cand
        c += 1


def process_still(
    path: Path, *, min_conf, pad, only, skip, allow_pattern, preview
) -> tuple[dict[str, int], list[tuple[int, int, int, int]]]:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    lines = _ocr.ocr_image(img, min_conf=min_conf)
    boxes: list[tuple[int, int, int, int]] = []
    kinds: dict[str, int] = {}
    for ln in lines:
        for m in _detect.detect_line(ln.text, only=only, skip=skip, allow=allow_pattern):
            b = _locate.locate_match(ln.text, ln.box, m.start, m.end, pad=pad, img_w=w, img_h=h)
            boxes.append(b)
            kinds[m.kind] = kinds.get(m.kind, 0) + 1
    return kinds, _locate.merge_boxes(boxes)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        only = parse_kinds(args.only)
        skip = parse_kinds(args.skip)
    except ValueError as e:
        print(f"blurkey: error: {e}", file=sys.stderr)
        return 2
    try:
        allow_pattern = re.compile(args.allow) if args.allow else None
    except re.error as e:
        print(f"blurkey: error: bad --allow regex: {e}", file=sys.stderr)
        return 2
    if not 0.0 <= args.min_conf <= 1.0:
        print("blurkey: error: --min-conf must be between 0 and 1", file=sys.stderr)
        return 2
    if args.pad < 0:
        print("blurkey: error: --pad must be >= 0", file=sys.stderr)
        return 2
    if args.frame_step < 1:
        print("blurkey: error: --frame-step must be >= 1", file=sys.stderr)
        return 2

    if args.output and len(args.files) > 1 and not args.in_place:
        print("blurkey: error: --output only works with a single FILE", file=sys.stderr)
        return 2
    if args.in_place and (args.output or args.out_dir):
        print("blurkey: error: --in-place cannot be combined with --output/--out-dir", file=sys.stderr)
        return 2
    if args.output and args.out_dir:
        print("blurkey: error: use only one of --output and --out-dir", file=sys.stderr)
        return 2
    if args.out_dir and not args.check:
        try:
            Path(args.out_dir).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"blurkey: error: cannot create --out-dir: {e}", file=sys.stderr)
            return 2

    reports: list[dict] = []
    found_any = False
    errors = 0

    for f in args.files:
        path = Path(f)
        if not path.exists():
            print(f"blurkey: error: not found: {f}", file=sys.stderr)
            errors += 1
            continue
        ext = path.suffix.lower()
        is_gif = ext in GIF_EXTS
        is_still = ext in STILL_EXTS
        if not (is_gif or is_still):
            print(f"blurkey: error: unsupported format: {f} (use png/jpg/webp/gif)", file=sys.stderr)
            errors += 1
            continue

        try:
            extra: dict = {}
            if is_gif:
                # dry-run boxes first via redact_gif? need check-mode without write:
                if args.check:
                    im = Image.open(path)
                    n = getattr(im, "n_frames", 1)
                    frames = []
                    for i in range(n):
                        im.seek(i)
                        frames.append(im.convert("RGB").copy())
                    res = _gif.process_gif_frames(
                        frames, min_conf=args.min_conf, pad=args.pad,
                        only=only or None, skip=skip or None,
                        allow_pattern=allow_pattern, frame_step=args.frame_step,
                    )
                    kinds = res.kinds
                    out = None
                    extra = {"frames": res.n_frames, "frames_with_hits": res.frames_with_hits}
                else:
                    try:
                        out_p = resolve_output(
                            path, output=args.output, out_dir=args.out_dir,
                            in_place=args.in_place, force=args.force,
                        )
                    except ValueError as e:
                        print(f"blurkey: error: {e}", file=sys.stderr)
                        errors += 1
                        continue
                    res = _gif.redact_gif(
                        str(path), str(out_p),
                        min_conf=args.min_conf, pad=args.pad, preview=args.preview,
                        only=only or None, skip=skip or None,
                        allow_pattern=allow_pattern, frame_step=args.frame_step,
                        show_progress=(not args.as_json and not args.quiet),
                    )
                    kinds = res.kinds
                    out = str(out_p)
                    extra = {"frames": res.n_frames, "frames_with_hits": res.frames_with_hits}
            else:
                kinds, boxes = process_still(
                    path, min_conf=args.min_conf, pad=args.pad,
                    only=only or None, skip=skip or None,
                    allow_pattern=allow_pattern, preview=args.preview,
                )
                out = None
                if not args.check:
                    try:
                        out_p = resolve_output(
                            path, output=args.output, out_dir=args.out_dir,
                            in_place=args.in_place, force=args.force,
                        )
                    except ValueError as e:
                        print(f"blurkey: error: {e}", file=sys.stderr)
                        errors += 1
                        continue
                    img = Image.open(path).convert("RGB")
                    done = _redact.apply_boxes(img, boxes, preview=args.preview)
                    # strip metadata: save fresh (format from ext)
                    done.save(out_p)
                    out = str(out_p)
        except Exception as e:
            print(f"blurkey: error processing {f}: {e}", file=sys.stderr)
            errors += 1
            continue

        total = sum(kinds.values())
        if total > 0:
            found_any = True
        rep = _report.report_dict(str(path), kinds, out, extra or None)
        reports.append(rep)
        if args.as_json or args.quiet:
            pass  # printed at end / suppressed
        else:
            msg = _report.summarize(kinds, check_mode=args.check)
            if out:
                console.print(f"[green]{path}[/green] -> [bold]{out}[/bold]: {msg}")
            else:
                console.print(f"[green]{path}[/green]: {msg}")

    if args.as_json:
        print(json.dumps(reports if len(reports) > 1 else (reports[0] if reports else {}), indent=2))

    if not args.as_json and not args.quiet and reports:
        console.print(
            "[yellow]Review the output before sharing — OCR can miss garbled text.[/yellow]"
        )

    if errors:
        return 2
    if args.check and found_any:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
