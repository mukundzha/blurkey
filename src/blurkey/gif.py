"""GIF pipeline: keep timing, skip OCR on near-identical frames, smooth boxes."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from . import detect as _detect
from . import locate as _locate
from . import ocr as _ocr
from . import redact as _redact

Box = tuple[int, int, int, int]


@dataclass
class GifResult:
    kinds: dict[str, int]
    boxes_per_frame: list[list[Box]]
    n_frames: int
    frames_with_hits: int = 0
    ocr_calls: int = 0


def _frame_signature(frame: Image.Image, size: int = 48) -> np.ndarray:
    small = frame.convert("L").resize((size, size), Image.BILINEAR)
    return np.asarray(small, dtype=np.float32)


def frames_changed(prev: np.ndarray, cur: np.ndarray, thresh: float = 4.0) -> bool:
    return float(np.mean(np.abs(prev - cur))) > thresh


def smooth_boxes(
    per_frame: list[list[Box]], *, window: int = 2
) -> list[list[Box]]:
    """Union boxes over +/-window neighbours so one OCR miss never flashes."""
    n = len(per_frame)
    out: list[list[Box]] = []
    for i in range(n):
        union: list[Box] = []
        for j in range(max(0, i - window), min(n, i + window + 1)):
            union.extend(per_frame[j])
        out.append(_locate.merge_boxes(union))
    return out


def process_gif_frames(
    frames: list[Image.Image],
    *,
    min_conf: float = 0.5,
    pad: int = 4,
    only: set[str] | None = None,
    skip: set[str] | None = None,
    allow_pattern=None,
    frame_step: int = 1,
) -> GifResult:
    per_frame: list[list[Box]] = []
    kinds: dict[str, int] = {}
    last_sig: np.ndarray | None = None
    last_boxes: list[Box] = []
    ocr_calls = 0

    for i, fr in enumerate(frames):
        w, h = fr.size
        should_ocr = (i % max(frame_step, 1) == 0)
        if should_ocr and last_sig is not None:
            sig = _frame_signature(fr)
            if not frames_changed(last_sig, sig):
                should_ocr = False
            else:
                last_sig = sig
        elif should_ocr:
            last_sig = _frame_signature(fr)

        if not should_ocr:
            # Reuse previous boxes but do NOT inflate kind counts:
            # kinds count unique OCR detections only.
            per_frame.append(list(last_boxes))
            continue

        ocr_calls += 1
        lines = _ocr.ocr_image(fr, min_conf=min_conf)
        boxes: list[Box] = []
        fk: list[str] = []
        for ln in lines:
            for m in _detect.detect_line(
                ln.text, only=only, skip=skip, allow=allow_pattern
            ):
                b = _locate.locate_match(
                    ln.text, ln.box, m.start, m.end,
                    pad=pad, img_w=w, img_h=h,
                )
                boxes.append(b)
                fk.append(m.kind)
        boxes = _locate.merge_boxes(boxes)
        per_frame.append(boxes)
        last_boxes = boxes
        for k in fk:
            kinds[k] = kinds.get(k, 0) + 1

    smoothed = smooth_boxes(per_frame)
    frames_with_hits = sum(1 for b in smoothed if b)
    return GifResult(
        kinds=kinds,
        boxes_per_frame=smoothed,
        n_frames=len(frames),
        frames_with_hits=frames_with_hits,
        ocr_calls=ocr_calls,
    )


def redact_gif(
    path: str,
    out_path: str,
    *,
    min_conf: float = 0.5,
    pad: int = 4,
    preview: bool = False,
    only: set[str] | None = None,
    skip: set[str] | None = None,
    allow_pattern=None,
    frame_step: int = 1,
    show_progress: bool = False,
) -> GifResult:
    im = Image.open(path)
    n = getattr(im, "n_frames", 1)
    frames: list[Image.Image] = []
    durations: list[int] = []
    for i in range(n):
        im.seek(i)
        frames.append(im.convert("RGB").copy())
        durations.append(im.info.get("duration", 100))
    loop = im.info.get("loop", 0)

    res = process_gif_frames(
        frames, min_conf=min_conf, pad=pad, only=only, skip=skip,
        allow_pattern=allow_pattern, frame_step=frame_step,
    )
    if show_progress and len(frames) > 10:
        from rich.progress import track

        iterator = track(
            zip(frames, res.boxes_per_frame),
            total=len(frames),
            description="Redacting GIF",
        )
        redacted = [
            _redact.apply_boxes(fr, boxes, preview=preview)
            for fr, boxes in iterator
        ]
    else:
        redacted = [
            _redact.apply_boxes(fr, boxes, preview=preview)
            for fr, boxes in zip(frames, res.boxes_per_frame)
        ]
    redacted[0].save(
        out_path,
        save_all=True,
        append_images=redacted[1:] if len(redacted) > 1 else [],
        duration=durations,
        loop=loop,
        optimize=True,
    )
    return res
