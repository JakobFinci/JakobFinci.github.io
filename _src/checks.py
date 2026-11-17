"""Check committed HTML, local links/anchors, metadata, media and editorial regressions.

Standard library only. Run after build.py; never repairs files to make checks pass.
HTML is intentionally explicit: mismatched closing tags are errors, not silently
auto-closed as in the browser. Both disk content and fresh output are inspected.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from xml.etree import ElementTree

import build

ROOT = build.ROOT
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
BLOCK = {"div", "section", "article", "h1", "h2", "h3", "ul", "ol", "table", "p"}


class Document(HTMLParser):
    def __init__(self, content: str):
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.stack: list[str] = []
        self.tags: Counter = Counter()
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.title = ""
        self.images: list[dict] = []
        self.videos: list[dict] = []
        self.sources: list[dict] = []
        self.jsonld: list[str] = []
        self._jsonld = False
        self.feed(content)
        self.close()
        if self.stack:
            self.errors.append(f"unclosed tags: {self.stack}")
        for value in self.jsonld:
            try:
                data = json.loads(value)
                if isinstance(data, dict):
                    self.links.extend(data[k] for k in ("url", "image") if isinstance(data.get(k), str))
            except ValueError:
                self.errors.append("invalid JSON-LD")

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.tags[tag] += 1
        if len(d) != len(attrs):
            self.errors.append(f"duplicate attribute on <{tag}>")
        if tag in BLOCK and "p" in self.stack:
            self.errors.append(f"<{tag}> nested inside <p>")
        if tag == "a" and "a" in self.stack:
            self.errors.append("nested links")
        if d.get("id"):
            if d["id"] in self.ids:
                self.errors.append(f"duplicate id: {d['id']}")
            self.ids.add(d["id"])
        if tag == "html" and not d.get("lang"):
            self.errors.append("missing document language")
        if tag == "a" and d.get("target") == "_blank" and "noopener" not in d.get("rel", "").split():
            self.errors.append("new-tab link missing noopener")
        for key in ("href", "src", "poster"):
            if d.get(key):
                self.links.append(d[key])
        if d.get("srcset"):
            self.links.extend(part.strip().split()[0] for part in d["srcset"].split(",") if part.strip())
        if tag == "img":
            self.images.append(d)
            if "alt" not in d:
                self.errors.append("image missing alt attribute")
            if not all(d.get(k, "").isdigit() and int(d[k]) > 0 for k in ("width", "height")):
                self.errors.append(f"image missing positive dimensions: {d.get('src')}")
        if tag == "video":
            self.videos.append(d)
        if tag == "source":
            self.sources.append(d)
        if tag == "link" and d.get("rel") == "canonical":
            if self.canonical:
                self.errors.append("multiple canonical links")
            self.canonical = d.get("href", "")
        if tag == "meta":
            key = d.get("name") or d.get("property") or d.get("http-equiv", "").lower()
            self.meta[key] = d.get("content", "")
            if key in {"og:image", "twitter:image"}:
                self.links.append(d.get("content", ""))
        if tag == "script" and d.get("type") == "application/ld+json":
            self._jsonld = True
            self.jsonld.append("")
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "script":
            self._jsonld = False
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}>; expected </{self.stack[-1] if self.stack else 'nothing'}>")
            if tag in self.stack:
                self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]
        else:
            self.stack.pop()

    def handle_data(self, data):
        if self.stack and self.stack[-1] == "title":
            self.title += data
        if self._jsonld:
            self.jsonld[-1] += data


def public_files(root: Path) -> set[str]:
    """Exact case matters on GitHub Pages, even when this check runs on Windows."""
    files = set()
    for directory, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"_src", "venv", "__pycache__"}]
        files.update((Path(directory) / name).relative_to(root).as_posix() for name in names)
    return files


def local_target(link: str, source: str) -> tuple[str, str] | None:
    url = urlsplit(urljoin(build.BASE + "/" + source, link))
    if url.scheme not in {"https", "http"} or url.netloc.lower() != urlsplit(build.BASE).netloc.lower():
        return None
    path = unquote(url.path).lstrip("/")
    if not path or path.endswith("/"):
        path += "index.html"
    return path, unquote(url.fragment)


def route(rel: str) -> str:
    return "/" + (rel[:-10] if rel.endswith("index.html") else rel)


def validate_pages(pages: dict[str, str], files: set[str]) -> list[str]:
    errors = []
    docs = {rel: Document(content) for rel, content in pages.items() if rel.endswith(".html")}
    canonical_routes = set()
    for rel, doc in docs.items():
        errors.extend(f"[html] {rel}: {err}" for err in doc.errors)
        for tag in ("html", "head", "body", "title"):
            if doc.tags[tag] != 1:
                errors.append(f"[html] {rel}: expected exactly one <{tag}>")
        if not doc.title.strip() or not doc.meta.get("viewport"):
            errors.append(f"[meta] {rel}: missing title or viewport")
        refresh = doc.meta.get("refresh")
        if refresh:
            match = re.fullmatch(r"0;\s*url=(.+)", refresh)
            target = match[1] if match else ""
            if not target or doc.canonical != urljoin(build.BASE, target) or doc.meta.get("robots") != "noindex":
                errors.append(f"[redirect] {rel}: inconsistent target, canonical or noindex")
            if target:
                doc.links.append(target)
        else:
            if doc.tags["main"] != 1 or doc.tags["h1"] != 1 or "main" not in doc.ids:
                errors.append(f"[a11y] {rel}: expected one main landmark and h1")
            expected = build.canonical(route(rel))
            if doc.canonical != expected or doc.meta.get("og:url") != expected:
                errors.append(f"[meta] {rel}: canonical/og:url must be {expected}")
            for key in ("description", "og:title", "og:description", "og:image", "og:type", "twitter:card"):
                if not doc.meta.get(key):
                    errors.append(f"[meta] {rel}: missing {key}")
            if rel != "404.html":
                canonical_routes.add(expected)
        for link in doc.links:
            target = local_target(link, rel)
            if target is None:
                continue
            path, fragment = target
            if path not in files:
                errors.append(f"[link] {rel}: missing file (case-sensitive): {link}")
            elif fragment and path.endswith(".html") and (path not in docs or fragment not in docs[path].ids):
                errors.append(f"[anchor] {rel}: missing anchor: {link}")
        for img in doc.images:
            path = local_target(img.get("src", ""), rel)
            dims = build.DIMS.get(path[0]) if path else None
            if dims and [img.get("width"), img.get("height")] != [str(n) for n in dims]:
                errors.append(f"[image] {rel}: dimensions disagree with manifest: {img.get('src')}")
    try:
        tree = ElementTree.fromstring(pages["sitemap.xml"])
        urls = [node.text for node in tree.findall("{*}url/{*}loc")]
        if len(urls) != len(set(urls)) or set(urls) != canonical_routes:
            errors.append("[sitemap] canonical routes are missing, duplicated or unexpected")
    except (KeyError, ElementTree.ParseError):
        errors.append("[sitemap] missing or invalid XML")
    if f"Sitemap: {build.BASE}/sitemap.xml" not in pages.get("robots.txt", ""):
        errors.append("[robots] missing sitemap")
    return errors


def check_editorial(pages: dict[str, str]) -> list[str]:
    """Guard explicit reversals, not a generic blacklist of the author's diction.

    Update deliberately alongside future author revisions. These phrases encode
    05c4124, 87b5890, cbf4b52, c0b2bb7, 1823946 and 2c27c6d.
    """
    required = {
        "index.html": ["Engineer, researcher, and creator."],
        "about/index.html": ["Mr. Dell Conagher", "I solve practical problems.",
                             "TL;DR: Dumb and meaningless reference to a fellow Jew.",
                             "plants, mushrooms, and cats", "Hoffman Lab", "dual master's degrees"],
        "media/pixelart/index.html": ["never actually used in any official Goko adverts or media", "Aseprite"],
        "projects/washburn/index.html": ["More to come soon."],
        "404.html": ["/medialib/404.mp4", "I am not Rick Astley.", "controls", "noindex"],
    }
    forbidden = {
        "index.html": ['id="now-h"', 'id="creative-h"', 'class="currently"'],
        "projects/index.html": ["Goko Energy"],
        "projects/washburn/index.html": ["Dossier in progress", "will be published"],
    }
    errors = []
    for rel, phrases in required.items():
        text = " ".join(pages.get(rel, "").split())
        for phrase in phrases:
            if phrase not in text:
                errors.append(f"[preservation] {rel}: missing author-approved content: {phrase}")
    for rel, phrases in forbidden.items():
        for phrase in phrases:
            if phrase in pages.get(rel, ""):
                errors.append(f"[preservation] {rel}: reintroduced withdrawn content: {phrase}")
    for rel, content in pages.items():
        for phrase in ("A full project dossier", "Dossier in progress.", "image-maker"):
            if phrase in content:
                errors.append(f"[preservation] {rel}: reintroduced withdrawn wording: {phrase}")
    notfound = Document(pages.get("404.html", ""))
    if (len(notfound.videos) != 1
            or not {"autoplay", "loop", "controls", "playsinline"} <= set(notfound.videos[0])
            or not any(s.get("src") == "/medialib/404.mp4" and s.get("type") == "video/mp4" for s in notfound.sources)):
        errors.append("[preservation] 404.html: missing full-screen video playback contract")
    return errors


def check_media(files: set[str]) -> list[str]:
    errors = []
    originals = {p for p in files if p.startswith("medialib/photography/") and Path(p).suffix.lower() in {".jpg", ".jpeg", ".png"}}
    if originals != set(build.IMAGES):
        errors.append("[media] photography originals and derivative manifest disagree")
    for original, entry in build.IMAGES.items():
        for variant in ("thumb", "display"):
            asset = entry[variant]
            if asset["path"] not in files or build.DIMS.get(asset["path"]) != [asset["w"], asset["h"]]:
                errors.append(f"[media] missing derivative or inconsistent dimensions: {original} ({variant})")
    for path, dims in build.DIMS.items():
        if path not in files or len(dims) != 2 or any(n <= 0 for n in dims):
            errors.append(f"[media] missing image or invalid dimensions: {path}")
    return errors


def check_drift(expected: dict[str, str], root: Path) -> list[str]:
    return [f"[drift] {rel} differs from a fresh build (run build.py)"
            for rel, content in expected.items()
            if not (root / rel).is_file() or (root / rel).read_text(encoding="utf-8") != content]


def main() -> int:
    expected = build.build_pages()
    files = public_files(ROOT)
    committed = {rel: (ROOT / rel).read_text(encoding="utf-8")
                 for rel in files if rel.endswith(".html") or rel in {"sitemap.xml", "robots.txt"}}
    errors = check_drift(expected, ROOT)
    extras = set(committed) - set(expected)
    errors.extend(f"[source] {rel} is not owned by the generator" for rel in sorted(extras))
    errors += validate_pages(committed, files)
    errors += check_editorial(committed)
    # Also catch a source regression when the committed HTML is still correct.
    errors += check_editorial(expected)
    errors += check_media(files)
    if ".nojekyll" not in files:
        errors.append("[deploy] missing .nojekyll")
    errors = list(dict.fromkeys(errors))
    if errors:
        print(f"FAIL - {len(errors)} problem(s):")
        for err in errors:
            print("  " + err)
        return 1
    print(f"PASS - {len(expected)} files: no drift; HTML, links, anchors, metadata, media and preservation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
