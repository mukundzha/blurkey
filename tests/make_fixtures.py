"""Generate synthetic fixtures (terminal/editor/browser, light/dark) with fake keys only."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent / "fixtures"
FAKE_AWS = "AKIAIOSFODNN7EXAMPLE"
FAKE_EMAIL = "alice@example.com"
FAKE_IP = "192.168.1.10"

STYLES = {
    "terminal-dark": {"bg": (20, 20, 20), "fg": (220, 220, 220)},
    "terminal-light": {"bg": (255, 255, 255), "fg": (20, 20, 20)},
    "editor-dark": {"bg": (30, 30, 40), "fg": (200, 230, 200)},
    "browser-light": {"bg": (245, 245, 245), "fg": (10, 10, 10)},
}

LINES = [
    f"export AWS_ACCESS_KEY_ID={FAKE_AWS}",
    f"contact {FAKE_EMAIL} server {FAKE_IP}",
    "fix the login bug on line 42",
]


def make(style: str, bg, fg, dest: Path):
    img = Image.new("RGB", (800, 200), bg)
    d = ImageDraw.Draw(img)
    y = 20
    for line in LINES:
        d.text((20, y), line, fill=fg)
        y += 40
    img.save(dest)


def main():
    OUT.mkdir(exist_ok=True)
    for name, s in STYLES.items():
        make(name, s["bg"], s["fg"], OUT / f"{name}.png")
    # clean image (no secrets)
    img = Image.new("RGB", (800, 120), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 20), "hello world, fix the bug in app.py", fill=(0, 0, 0))
    img.save(OUT / "clean.png")
    print(f"wrote {len(list(OUT.glob('*')))} fixtures to {OUT}")


if __name__ == "__main__":
    main()
