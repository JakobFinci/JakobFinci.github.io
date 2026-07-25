"""Generate optimized WebP derivatives for photography and a dimensions manifest.

Run from the repository root:

    python _src/tools/derivatives.py

Requires Pillow (content-tooling only; the deployed site never needs it).
Originals are never modified. Derivatives land in medialib/derived/ mirroring
the source tree, and _src/data/images.json records dimensions for the build.

Re-running is incremental: existing derivatives are kept unless the source
image is newer.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
PHOTO_ROOT = ROOT / "medialib" / "photography"
DERIVED_ROOT = ROOT / "medialib" / "derived"
MANIFEST = ROOT / "_src" / "data" / "images.json"

SIZES = {"thumb": (640, 78), "display": (1400, 84)}  # long edge px, webp quality
PHOTO_EXTS = {".jpg", ".jpeg", ".png"}


def resized(img: Image.Image, long_edge: int) -> Image.Image:
    w, h = img.size
    scale = long_edge / max(w, h)
    if scale >= 1:
        return img.copy()
    return img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)


def main() -> None:
    manifest: dict[str, dict] = {}
    count = 0
    for src in sorted(PHOTO_ROOT.rglob("*")):
        if src.suffix.lower() not in PHOTO_EXTS or not src.is_file():
            continue
        rel = src.relative_to(ROOT)
        with Image.open(src) as raw:
            img = ImageOps.exif_transpose(raw)
            img = img.convert("RGB")
            entry: dict = {"w": img.width, "h": img.height}
            for name, (edge, quality) in SIZES.items():
                out = DERIVED_ROOT / rel.parent.relative_to("medialib") / (
                    src.stem + f".{name}.webp"
                )
                out.parent.mkdir(parents=True, exist_ok=True)
                if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
                    small = resized(img, edge)
                    small.save(out, "WEBP", quality=quality, method=6)
                    count += 1
                with Image.open(out) as d:
                    entry[name] = {
                        "path": out.relative_to(ROOT).as_posix(),
                        "w": d.width,
                        "h": d.height,
                    }
            manifest[rel.as_posix()] = entry
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(f"{len(manifest)} photos indexed, {count} derivatives written")


if __name__ == "__main__":
    main()
