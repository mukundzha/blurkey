"""Build demo/app.png: dark terminal-style screenshot with fake secrets only."""
from PIL import Image, ImageDraw, ImageFont

W, H = 1000, 380
BG = (24, 24, 32)
FG = (230, 230, 235)
DIM = (140, 140, 150)

FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 30)

LINES = [
    ("$ cat .env", DIM),
    ("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE", FG),
    ("APP_SECRET=topsecret-demo-12345", FG),
    ("ADMIN_EMAIL=alice@example.com", FG),
    ("SERVER=192.168.1.10", FG),
]

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)
y = 36
for text, color in LINES:
    d.text((36, y), text, font=FONT, fill=color)
    y += 56
img.save("demo/app.png")
print("wrote demo/app.png")
