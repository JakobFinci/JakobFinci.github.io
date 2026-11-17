"""Render the 1200x630 social-preview card to assets/og-image.png.

Content-tooling only (uses Pillow). The existing pixel portrait and site identity;
no generated artwork, grid, or registration marks.

    python _src/tools/og_image.py
"""

from __future__ import annotations

from pathlib import Path
import tomllib

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "og-image.png"
PORTRAIT = ROOT / "medialib" / "me.png"

W, H = 1200, 630
PAPER = (248, 247, 242)
INK = (36, 44, 41)
MUTED = (85, 95, 89)
GREEN = (48, 92, 80)


def font(names: list[str], size: int) -> ImageFont.FreeTypeFont:
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    raise RuntimeError("Install a supported font before regenerating the social image.")


def main() -> None:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    site = tomllib.loads((ROOT / "_src/data/site.toml").read_text(encoding="utf-8"))
    serif_lg = font(["georgia.ttf", "Georgia.ttf", "DejaVuSerif.ttf"], 70)
    sans = font(["segoeui.ttf", "Arial.ttf", "DejaVuSans.ttf"], 30)
    small = font(["segoeui.ttf", "Arial.ttf", "DejaVuSans.ttf"], 24)

    left = 80
    first, surname = site["site"]["title"].rsplit(" ", 1)
    d.text((left, 160), first, font=serif_lg, fill=INK)
    d.text((left, 248), surname, font=serif_lg, fill=INK)
    d.text((left, 370), site["identity"]["tagline"], font=sans, fill=MUTED)
    d.line([(left, 465), (W - left, 465)], fill=GREEN, width=2)
    d.text((left, 495), site["site"]["url"].removeprefix("https://"), font=small, fill=GREEN)

    # Keep the original pixels and transparency intact.
    with Image.open(PORTRAIT) as original:
        portrait = original.convert("RGBA")
    px = W - portrait.width - 110
    py = 465 - portrait.height
    img.paste(portrait, (px, py), portrait)

    img.save(OUT, "PNG")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
