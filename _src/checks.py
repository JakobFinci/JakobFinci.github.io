"""Verification checks for the generated site. Standard library only.

Run after `python _src/build.py`:

    python _src/checks.py

Verifies, without needing a running server:
  1. Build is not stale (committed output matches a fresh build).
  2. Every internal link and asset reference resolves to a real file.
  3. Every rendered page has title, meta description, canonical, and OG tags.
  4. Every page's HTML parses cleanly and tags are balanced.

Exits non-zero if any check fails, so CI can gate on it.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

ROOT = build.ROOT
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}


class Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.stack: list[str] = []
        self.imbal:  list[str] = []
        self.has_title = False
        self._in_title = False
        self.title_text = ""

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        for key in ("href", "src"):
            if d.get(key):
                self.links.append(d[key])
        if tag == "title":
            self.has_title = True
            self._in_title = True
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        d = dict(attrs)
        for key in ("href", "src"):
            if d.get(key):
                self.links.append(d[key])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            # Close intervening auto-closed tags.
            while self.stack and self.stack.pop() != tag:
                pass
        else:
            self.imbal.append(tag)

    def handle_data(self, data):
        if self._in_title:
            self.title_text += data


def resolve(link: str, pages: dict[str, str]) -> bool:
    path = link.split("#", 1)[0].split("?", 1)[0]
    if not path:
        return True  # pure in-page anchor
    if path.endswith("/"):
        stripped = path.strip("/")
        cand = f"{stripped}/index.html" if stripped else "index.html"
    else:
        cand = path.lstrip("/")
    return cand in pages or (ROOT / cand).exists()


def is_external(link: str) -> bool:
    return bool(re.match(r"^(https?:|mailto:|tel:|data:)", link)) or link.startswith("//")


def main() -> int:
    errors: list[str] = []
    pages = build.build_pages()

    # 1. Drift.
    for rel, content in pages.items():
        existing = ROOT / rel
        if not existing.exists() or existing.read_text(encoding="utf-8") != content:
            errors.append(f"[drift] {rel} differs from a fresh build (run build.py)")

    html_pages = {r: c for r, c in pages.items() if r.endswith((".html",))}
    for rel, content in html_pages.items():
        p = Extractor()
        try:
            p.feed(content)
        except Exception as exc:  # pragma: no cover
            errors.append(f"[parse] {rel}: {exc}")
            continue
        if p.stack:
            errors.append(f"[html] {rel}: unclosed tags {p.stack}")
        if p.imbal:
            errors.append(f"[html] {rel}: stray closing tags {p.imbal}")

        # 2. Link/asset resolution.
        for link in p.links:
            if is_external(link):
                continue
            if link.startswith("/") and not resolve(link, pages):
                errors.append(f"[link] {rel}: unresolved -> {link}")

        # 3. Metadata (rendered pages only; redirect stubs are exempt).
        is_rendered = '<main id="main">' in content
        if is_rendered:
            if not p.title_text.strip():
                errors.append(f"[meta] {rel}: empty <title>")
            for pat, label in [
                (r'<meta name="description" content="[^"]+">', "meta description"),
                (r'<link rel="canonical" href="https://[^"]+">', "canonical"),
                (r'<meta property="og:title" content="[^"]+">', "og:title"),
                (r'<meta property="og:image" content="https://[^"]+">', "og:image"),
            ]:
                if not re.search(pat, content):
                    errors.append(f"[meta] {rel}: missing {label}")

    total = len(pages)
    if errors:
        print(f"FAIL — {len(errors)} problem(s) across {total} files:")
        for err in errors:
            print("  " + err)
        return 1
    print(f"PASS — {total} files: no drift, all links resolve, metadata complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
