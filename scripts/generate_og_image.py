"""
Generate a static OG image (1200x630) for Toko Web Jaya.
Requires: pip install Pillow
Run: python scripts/generate_og_image.py
Output: static/og-default.png
"""
import sys
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

W, H = 1200, 630
NEON = (202, 255, 0)       # #CAFF00
BLACK = (10, 10, 10)
DARK = (20, 20, 20)
GRAY = (80, 80, 80)
WHITE = (255, 255, 255)

img = Image.new("RGB", (W, H), BLACK)
draw = ImageDraw.Draw(img)

# Background grid pattern
GRID = 48
for x in range(0, W, GRID):
    draw.line([(x, 0), (x, H)], fill=(202, 255, 0, 8), width=1)
for y in range(0, H, GRID):
    draw.line([(0, y), (W, y)], fill=(202, 255, 0, 8), width=1)

# Neon accent block top-right
draw.rectangle([(W - 200, 0), (W, 8)], fill=NEON)

# Logo box
lx, ly = 80, 80
draw.rectangle([(lx, ly), (lx + 60, ly + 60)], fill=NEON)

# Try to load fonts, fall back to default
try:
    font_big = ImageFont.truetype("arial.ttf", 72)
    font_med = ImageFont.truetype("arial.ttf", 32)
    font_sm  = ImageFont.truetype("arial.ttf", 24)
    font_logo = ImageFont.truetype("arialbd.ttf", 28)
except Exception:
    font_big = ImageFont.load_default()
    font_med = font_big
    font_sm  = font_big
    font_logo = font_big

# Logo text "TW"
draw.text((lx + 10, ly + 8), "TW", font=font_logo, fill=BLACK)

# Brand name
draw.text((lx + 72, ly + 12), "Toko Web Jaya", font=font_med, fill=WHITE)

# Divider
draw.line([(80, 175), (W - 80, 175)], fill=GRAY, width=1)

# Main headline
draw.text((80, 210), "Produk Digital Profesional", font=font_big, fill=WHITE)
draw.text((80, 300), "untuk Bisnis Modern", font=font_big, fill=NEON)

# Subtext
draw.text((80, 410), "E-Book  •  Kursus  •  Software  •  Template  •  IT Consulting", font=font_sm, fill=GRAY)

# Bottom bar
draw.rectangle([(0, H - 8), (W, H)], fill=NEON)

# URL
draw.text((80, H - 52), "tokowebjaya.com", font=font_sm, fill=GRAY)

out = "static/og-default.png"
img.save(out, "PNG")
print(f"Saved: {out}")
