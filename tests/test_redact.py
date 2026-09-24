from PIL import Image

from blurkey.redact import apply_boxes, fresh_copy, is_uniform_black


def test_redact_black_and_uniform():
    img = Image.new("RGB", (100, 40), "white")
    out = apply_boxes(img, [(10, 10, 50, 30)])
    assert is_uniform_black(out, (10, 10, 50, 30))
    # outside stays white
    assert out.getpixel((5, 5)) == (255, 255, 255)


def test_preview_does_not_fill():
    img = Image.new("RGB", (100, 40), "white")
    out = apply_boxes(img, [(10, 10, 50, 30)], preview=True)
    assert not is_uniform_black(out, (10, 10, 50, 30))


def test_fresh_copy_strips_and_rgb():
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 128))
    out = fresh_copy(img)
    assert out.mode == "RGB"
    assert out.size == (10, 10)
