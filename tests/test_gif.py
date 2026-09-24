from PIL import Image

from blurkey import gif as _gif
from blurkey import ocr as _ocr


class FakeEngine:
    def __init__(self, lines_per_frame):
        self.lpf = lines_per_frame

    def lines(self, img):
        # return based on image identity? caller sets engine per test via index hack:
        return []


def test_smooth_boxes_window():
    per = [[(0, 0, 10, 10)], [], [(0, 0, 10, 10)]]
    sm = _gif.smooth_boxes(per, window=2)
    # middle frame inherits neighbours
    assert sm[1] == [(0, 0, 10, 10)]


def test_frames_changed():
    a = Image.new("RGB", (32, 32), "white")
    b = Image.new("RGB", (32, 32), "white")
    c = Image.new("RGB", (32, 32), "black")
    sa, sb, sc = (_gif._frame_signature(x) for x in (a, b, c))
    assert not _gif.frames_changed(sa, sb)
    assert _gif.frames_changed(sa, sc)


def test_process_gif_with_fake_ocr(tmp_path):
    frames = [Image.new("RGB", (200, 60), "white") for _ in range(3)]

    class E:
        def lines(self, img):
            from blurkey.ocr import TextLine
            return [TextLine("AKIAIOSFODNN7EXAMPLE", (10, 10, 190, 30), 0.99)]

    _ocr.set_engine(E())
    try:
        res = _gif.process_gif_frames(frames)
    finally:
        _ocr.set_engine(None)
    assert res.n_frames == 3
    assert res.kinds.get("aws", 0) >= 1
    # all frames got boxes after smoothing even with frame_step reuse
    assert all(len(b) >= 1 for b in res.boxes_per_frame)


def test_gif_counts_not_inflated_on_static_frames():
    from blurkey.ocr import TextLine

    frames = [Image.new("RGB", (200, 60), "white") for _ in range(4)]

    class E:
        def lines(self, img):
            return [TextLine("AKIAIOSFODNN7EXAMPLE", (10, 10, 190, 30), 0.99)]

    _ocr.set_engine(E())
    try:
        res = _gif.process_gif_frames(frames)
    finally:
        _ocr.set_engine(None)
    # identical frames -> OCR once, kinds count unique detections only
    assert res.ocr_calls == 1
    assert res.kinds.get("aws", 0) == 1
    assert res.frames_with_hits == 4


def test_redact_gif_roundtrip(tmp_path):
    from blurkey.ocr import TextLine

    src = tmp_path / "a.gif"
    frames = [Image.new("RGB", (200, 60), "white") for _ in range(2)]
    frames[0].save(src, save_all=True, append_images=frames[1:], duration=100, loop=0)

    class E:
        def lines(self, img):
            return [TextLine("a@b.com", (10, 10, 100, 30), 0.99)]

    _ocr.set_engine(E())
    try:
        out = tmp_path / "a.redacted.gif"
        res = _gif.redact_gif(str(src), str(out))
    finally:
        _ocr.set_engine(None)
    assert out.exists()
    assert res.kinds.get("email", 0) >= 1
