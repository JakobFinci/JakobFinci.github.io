"""Render the 1200x630 social-preview card to assets/og-image.png.

Content-tooling only (uses Pillow). Field-notebook styling: warm paper,
registration marks, the pixel portrait, name, and tagline.

    python _src/tools/og_image.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "og-image.png"
PORTRAIT = ROOT / "medialib" / "me.png"

W, H = 1200, 630
PAPER = (242, 238, 228)
GRID = (230, 224, 211)
INK = (27, 26, 23)
MUTED = (106, 101, 91)
RUST = (162, 73, 44)
BLUE = (51, 80, 126)


def font(names: list[str], size: int) -> ImageFont.FreeTypeFont:
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # Faint grid.
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill=GRID, width=1)

    # Frame + corner registration crosshairs.
    d.rectangle([28, 28, W - 29, H - 29], outline=(184, 176, 160), width=1)
    for cx, cy in [(28, 28), (W - 29, 28), (28, H - 29), (W - 29, H - 29)]:
        d.line([(cx - 12, cy), (cx + 12, cy)], fill=RUST, width=2)
        d.line([(cx, cy - 12), (cx, cy + 12)], fill=RUST, width=2)

    serif_lg = font(["georgiab.ttf", "Georgia Bold.ttf", "pala.ttf", "georgia.ttf"], 74)
    serif_sm = font(["georgia.ttf", "pala.ttf"], 34)
    mono = font(["consola.ttf", "cour.ttf"], 24)

    left = 80
    d.text((left, 96), "PORTFOLIO", font=mono, fill=RUST)
    d.text((left, 150), 'Elias "Eliyahu"', font=serif_lg, fill=INK)
    d.text((left, 232), "Suskind", font=serif_lg, fill=INK)
    d.text((left, 348), "Engineer, researcher,", font=serif_sm, fill=MUTED)
    d.text((left, 392), "and image-maker.", font=serif_sm, fill=MUTED)
    d.line([(left, 470), (left + 360, 470)], fill=RUST, width=2)
    d.text((left, 492), "jakobfinci.github.io", font=mono, fill=BLUE)

    # Portrait plate on the right.
    portrait = Image.open(PORTRAIT).convert("RGB")
    scale = 420 / portrait.height
    portrait = portrait.resize(
        (round(portrait.width * scale), 420), Image.NEAREST
    )
    px = W - portrait.width - 120
    py = (H - portrait.height) // 2
    d.rectangle(
        [px - 14, py - 14, px + portrait.width + 13, py + portrait.height + 13],
        fill=(251, 250, 245),
        outline=(184, 176, 160),
        width=1,
    )
    img.paste(portrait, (px, py))

    img.save(OUT, "PNG")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
