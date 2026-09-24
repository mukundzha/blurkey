from pathlib import Path

from blurkey.cli import main, resolve_output
from blurkey.report import summarize


def test_resolve_output_never_overwrites(tmp_path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    out = resolve_output(src, output=None, out_dir=None, in_place=False, force=False)
    assert out.name == "a.redacted.png"
    out.write_bytes(b"y")
    out2 = resolve_output(src, output=None, out_dir=None, in_place=False, force=False)
    assert out2.name == "a.redacted-1.png"
    out3 = resolve_output(src, output=None, out_dir=None, in_place=False, force=True)
    assert out3.name == "a.redacted.png"


def test_resolve_output_out_dir(tmp_path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    out = resolve_output(src, output=None, out_dir=str(tmp_path / "out"),
                         in_place=False, force=False)
    assert out.parent.name == "out"
    assert out.name == "a.redacted.png"


def test_check_wording():
    assert summarize({"aws": 1}, check_mode=True).startswith("Found")
    assert summarize({"aws": 1}, check_mode=False).startswith("Redacted")
    assert summarize({}) == "No secrets found"


def test_validation_errors():
    assert main(["--min-conf", "2.0", "x.png"]) == 2
    assert main(["--pad", "-1", "x.png"]) == 2
    assert main(["--frame-step", "0", "x.png"]) == 2
    assert main(["--allow", "([", "x.png"]) == 2


def test_version_flag(capsys):
    import pytest
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0


def test_check_mode_no_write(tmp_path):
    from PIL import Image
    from blurkey import ocr as _ocr

    src = tmp_path / "s.png"
    Image.new("RGB", (200, 60), "white").save(src)

    class E:
        def lines(self, img):
            from blurkey.ocr import TextLine
            return [TextLine("AKIAIOSFODNN7EXAMPLE", (10, 10, 190, 30), 0.99)]

    _ocr.set_engine(E())
    try:
        rc = main(["--check", str(src)])
    finally:
        _ocr.set_engine(None)
    assert rc == 1
    assert not (tmp_path / "s.redacted.png").exists()
    # quiet check still returns 1 without stdout noise
    _ocr.set_engine(E())
    try:
        rc2 = main(["--check", "-q", str(src)])
    finally:
        _ocr.set_engine(None)
    assert rc2 == 1


def test_out_dir_write(tmp_path):
    from PIL import Image
    from blurkey import ocr as _ocr

    src = tmp_path / "s.png"
    Image.new("RGB", (200, 60), "white").save(src)

    class E:
        def lines(self, img):
            from blurkey.ocr import TextLine
            return [TextLine("a@b.com", (10, 10, 100, 30), 0.99)]

    _ocr.set_engine(E())
    try:
        rc = main(["--out-dir", str(tmp_path / "out"), str(src)])
    finally:
        _ocr.set_engine(None)
    assert rc == 0
    assert (tmp_path / "out" / "s.redacted.png").exists()
