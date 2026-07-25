"""Record pixel dimensions of every image under medialib/ into dims.json.

Lets the build set explicit width/height on every <img> (no layout shift)
without importing Pillow at build time. Content-tooling only.

    python _src/tools/dims.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "medialib"
OUT = ROOT / "_src" / "data" / "dims.json"
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def main() -> None:
    dims: dict[str, list[int]] = {}
    for p in sorted(MEDIA.rglob("*")):
        if p.suffix.lower() in EXTS and p.is_file():
            with Image.open(p) as im:
                dims[p.relative_to(ROOT).as_posix()] = [im.width, im.height]
    OUT.write_text(json.dumps(dims, indent=0, sort_keys=True) + "\n")
    print(f"{len(dims)} images measured")


if __name__ == "__main__":
    main()
