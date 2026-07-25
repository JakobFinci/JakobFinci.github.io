"""Static site generator for jakobfinci.github.io.

Zero third-party dependencies — Python 3.11 standard library only (tomllib).
Reads structured data from _src/data/*.toml and long-form article bodies from
_src/content/, and writes plain HTML to canonical paths in the repo root. That
output is committed and served as-is by GitHub Pages (.nojekyll disables the
Ruby build), so there is no server-side build step to break.

    python _src/build.py            # build
    python _src/build.py --check    # build to a temp dir and diff (CI drift)

Add a page by adding data and a builder in `build_pages()`. Design tokens live
in assets/css/site.css; nothing here emits inline styles.
"""

from __future__ import annotations

import html
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "_src"
DATA = SRC / "data"
CONTENT = SRC / "content"

CSS_HREF = "/assets/css/site.css"
FAVICON = "/assets/favicon.svg"
OG_IMAGE = "/assets/og-image.png"


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
def load_toml(name: str) -> dict:
    return tomllib.loads((DATA / name).read_text(encoding="utf-8"))


SITE = load_toml("site.toml")
PROJECTS = load_toml("projects.toml")["project"]
PAPERS = load_toml("research.toml")["paper"]
COLLECTIONS = load_toml("collections.toml")["collection"]
IMAGES = json.loads((DATA / "images.json").read_text(encoding="utf-8"))
DIMS = json.loads((DATA / "dims.json").read_text(encoding="utf-8"))

S = SITE["site"]
A = SITE["author"]
BASE = S["url"].rstrip("/")


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def e(value) -> str:
    return html.escape(str(value), quote=True)


def natkey(text: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def canonical(path: str) -> str:
    return BASE + path


def json_ld(obj: dict) -> str:
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(obj, indent=2)
        + "\n</script>"
    )


# --------------------------------------------------------------------------
# Image rendering
# --------------------------------------------------------------------------
def dims_of(rel: str) -> tuple[int, int]:
    w, h = DIMS.get(rel, [None, None])
    return w, h


def photo_variant(rel: str, variant: str) -> tuple[str, int, int]:
    """Return (href, w, h) for a photography derivative ('thumb'/'display')."""
    entry = IMAGES[rel][variant]
    return "/" + entry["path"], entry["w"], entry["h"]


def plain_img(rel: str, alt: str, *, cls: str = "", loading: str = "lazy",
              priority: bool = False) -> str:
    w, h = dims_of(rel)
    dim = f' width="{w}" height="{h}"' if w else ""
    load = ' loading="eager" fetchpriority="high"' if priority else f' loading="{loading}" decoding="async"'
    c = f' class="{cls}"' if cls else ""
    return f'<img{c} src="/{e(rel)}" alt="{e(alt)}"{dim}{load}>'


# --------------------------------------------------------------------------
# Layout shell
# --------------------------------------------------------------------------
def nav_html(active: str) -> str:
    items = []
    for item in SITE["nav"]:
        cur = ' aria-current="page"' if item["url"] == active else ""
        items.append(f'<li><a href="{e(item["url"])}"{cur}>{e(item["label"])}</a></li>')
    return (
        '<nav class="site-nav" aria-label="Primary">\n      <ul>\n        '
        + "\n        ".join(items)
        + "\n      </ul>\n    </nav>"
    )


def header_html(active: str) -> str:
    return f"""  <header class="site-header">
    <div class="container site-header__inner">
      <a class="brand" href="/">{e(S["title"])} <span class="reg" aria-hidden="true">/ES</span></a>
    {nav_html(active)}
    </div>
  </header>"""


def footer_html() -> str:
    links = [
        ("Email", f'mailto:{A["email"]}', A["email"], False),
        ("GitHub", A["github"], "GitHub", True),
        ("LinkedIn", A["linkedin"], "LinkedIn", True),
        ("ResearchGate", A["researchgate"], "ResearchGate", True),
    ]
    out = []
    for _label, href, text, ext in links:
        attrs = ' target="_blank" rel="noopener" class="ext"' if ext else ""
        out.append(f'<a href="{e(href)}"{attrs}>{e(text)}</a>')
    return f"""  <footer class="site-footer">
    <div class="container site-footer__inner">
      <p>&copy; {e(S["copyright_year"])} {e(S["copyright_holder"])}</p>
      <div class="site-footer__links">
        {"".join(out)}
      </div>
    </div>
  </footer>"""


def shell(*, title: str, description: str, path: str, main_html: str,
          active: str = "", extra_head: str = "", jsonld: dict | list | None = None,
          og_type: str = "website") -> str:
    url = canonical(path)
    ld = ""
    if jsonld is not None:
        blocks = jsonld if isinstance(jsonld, list) else [jsonld]
        ld = "\n  " + "\n  ".join(json_ld(b) for b in blocks)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)}</title>
  <meta name="description" content="{e(description)}">
  <link rel="canonical" href="{e(url)}">
  <link rel="icon" href="{FAVICON}" type="image/svg+xml">
  <link rel="stylesheet" href="{CSS_HREF}">
  <meta name="color-scheme" content="light dark">
  <meta property="og:type" content="{og_type}">
  <meta property="og:site_name" content="{e(S["title"])}">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(description)}">
  <meta property="og:url" content="{e(url)}">
  <meta property="og:image" content="{e(canonical(OG_IMAGE))}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{e(title)}">
  <meta name="twitter:description" content="{e(description)}">
  <meta name="twitter:image" content="{e(canonical(OG_IMAGE))}">{extra_head}{ld}
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
{header_html(active)}
  <main id="main">
{main_html}
  </main>
{footer_html()}
</body>
</html>
"""


# --------------------------------------------------------------------------
# Reusable components
# --------------------------------------------------------------------------
def project_card(p: dict) -> str:
    thumb = p.get("thumb")
    media = ""
    if thumb:
        rel = thumb.lstrip("/")
        media = f'<div class="card__media pixel">{plain_img(rel, p.get("thumb_alt", ""))}</div>'
    status = p.get("status", "")
    year = p.get("year", "")
    meta = f'<span class="status status--{e(status)}">{e(status.replace("-", " "))}</span>'
    if year:
        meta += f'<span aria-hidden="true">·</span><span>{e(year)}</span>'
    tags = "".join(f'<span class="tag">{e(d)}</span>' for d in p.get("disciplines", []))
    link_label = p.get("link_label", "View project")
    href = p.get("url") or p.get("external_url") or "#"
    ext = ""
    if not p.get("url") and p.get("external_url"):
        ext = ' target="_blank" rel="noopener"'
    return f"""      <article class="card">
        {media}
        <div class="card__body">
          <p class="card__meta">{e(p.get("category", ""))}</p>
          <h3 class="card__title">{e(p["title"])}</h3>
          <p class="card__summary">{e(p["summary"])}</p>
          <p class="card__meta" style="margin-top:.5rem">{meta}</p>
          <div class="card__foot">{tags}</div>
          <p style="margin-top:.75rem"><a class="btn" href="{e(href)}"{ext}>{e(link_label)} →</a></p>
        </div>
      </article>"""


def collection_card(c: dict) -> str:
    cover = c.get("cover")
    if cover:
        rel = cover.lstrip("/")
        if rel in IMAGES:
            href, w, h = photo_variant(rel, "thumb")
            img = f'<img src="{e(href)}" alt="" width="{w}" height="{h}" loading="lazy" decoding="async">'
        else:
            img = plain_img(rel, "")
        media = f'<div class="card__media">{img}</div>'
    else:
        # Pixel collection: show first section image.
        first = c["section"][0]["image"][0]["src"]
        media = f'<div class="card__media pixel">{plain_img(first, "")}</div>'
    return f"""      <a class="card" href="{e(c["url"])}">
        {media}
        <div class="card__body">
          <p class="card__meta">{e(c["kind"].title())}</p>
          <h3 class="card__title">{e(c["title"])}</h3>
          <p class="card__summary">{e(c["summary"])}</p>
        </div>
      </a>"""


def gallery_from_section(section: dict, prefix: str, pixel: bool = False) -> str:
    figs = []
    if "image" in section:
        entries = [(im["src"], im.get("caption", "")) for im in section["image"]]
    else:
        folder = section["folder"]
        keys = sorted(
            (k for k in IMAGES if k.rsplit("/", 1)[0] == folder),
            key=lambda k: natkey(k.rsplit("/", 1)[1]),
        )
        cp = section.get("caption_prefix", "")
        credit = section.get("credit", "")
        entries = []
        for i, k in enumerate(keys, 1):
            cap = f"{cp} — frame {i}"
            if credit:
                cap += f". {credit}"
            entries.append((k, cap))
    for i, (rel, caption) in enumerate(entries, 1):
        num = f"{prefix}-{i:02d}"
        if pixel or rel not in IMAGES:
            w, h = dims_of(rel)
            dim = f' width="{w}" height="{h}"' if w else ""
            thumb = f'<img src="/{e(rel)}" alt="{e(caption)}"{dim} loading="lazy" decoding="async">'
            full = "/" + rel
        else:
            t_href, t_w, t_h = photo_variant(rel, "thumb")
            d_href, _, _ = photo_variant(rel, "display")
            thumb = f'<img src="{e(t_href)}" alt="{e(caption)}" width="{t_w}" height="{t_h}" loading="lazy" decoding="async">'
            full = d_href
        cap_html = (
            f'<figcaption><span class="n">{num}</span><span>{e(caption)}</span></figcaption>'
            if caption
            else ""
        )
        figs.append(
            f'<figure><a href="{e(full)}" target="_blank" rel="noopener" '
            f'aria-label="Open image {num} full size">{thumb}</a>{cap_html}</figure>'
        )
    cls = "gallery gallery--pixel" if pixel else "gallery"
    return f'<div class="{cls}">\n        ' + "\n        ".join(figs) + "\n      </div>"


def citation_text(p: dict) -> str:
    authors = p["authors"]
    if len(authors) == 1:
        who = authors[0]
    else:
        who = ", ".join(authors[:-1]) + " & " + authors[-1]
    parts = [f"{who} ({p['year']}). {p['title']}. {p['venue']}."]
    if p.get("doi"):
        parts.append(f"https://doi.org/{p['doi']}")
    return " ".join(parts)


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
def page_home() -> str:
    featured_projects = [p for p in PROJECTS if p.get("featured")]
    cur = "".join(
        f'<div class="currently__item"><span class="currently__key">{e(c["key"])}</span>'
        f'<span class="currently__val">{e(c["value"])}</span></div>'
        for c in SITE["current"]
    )
    # Selected work = featured projects (which already include the two papers).
    cards = "\n".join(project_card(p) for p in sorted(featured_projects, key=lambda p: p["order"]))
    # Selected creative work.
    creative = "\n".join(
        collection_card(c) for c in sorted(COLLECTIONS, key=lambda c: c["order"])
    )
    me_w, me_h = dims_of("medialib/me.png")
    main = f"""    <div class="container">
      <section class="hero">
        <div class="hero__body">
          <p class="eyebrow">Portfolio — {e(A["name"])} / {e(A["alt_name"])}</p>
          <h1>{e(S["title"])}</h1>
          <p class="hero__lede">{e(SITE["identity"]["tagline"])}</p>
          <p class="hero__intro">{e(SITE["identity"]["positioning"])}</p>
          <div class="btn-row">
            <a class="btn btn--solid" href="/projects/">See the work</a>
            <a class="btn" href="/about/#contact">Get in touch</a>
          </div>
        </div>
        <figure class="hero__portrait">
          <span class="crosshair tl" aria-hidden="true"></span>
          <span class="crosshair br" aria-hidden="true"></span>
          <img src="/medialib/me.png" alt="Pixel-art portrait of Elias Suskind, arms crossed" width="{me_w}" height="{me_h}" fetchpriority="high">
          <figcaption>Fig. — self-portrait, pixel</figcaption>
        </figure>
      </section>

      <section aria-labelledby="work-h">
        <div class="section-head">
          <h2 id="work-h">Selected work</h2>
          <span class="index"><a href="/projects/">All projects →</a></span>
        </div>
        <div class="card-grid">
{cards}
        </div>
      </section>

      <section aria-labelledby="now-h" style="margin-top:var(--space-2xl)">
        <div class="section-head">
          <h2 id="now-h">Currently</h2>
          <span class="index">STATUS · {e(S["copyright_year"])}</span>
        </div>
        <div class="currently">{cur}</div>
      </section>

      <section aria-labelledby="creative-h" style="margin-top:var(--space-2xl)">
        <div class="section-head">
          <h2 id="creative-h">Creative work</h2>
          <span class="index"><a href="/media/">All collections →</a></span>
        </div>
        <div class="card-grid">
{creative}
        </div>
      </section>
    </div>"""
    person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": A["name"],
        "alternateName": A["alt_name"],
        "url": BASE + "/",
        "image": canonical("/medialib/me.png"),
        "sameAs": [A["github"], A["linkedin"], A["researchgate"]],
    }
    return shell(
        title=f'{S["title"]} — engineer, researcher, image-maker',
        description=S["description"],
        path="/",
        main_html=main,
        active="/",
        jsonld=person,
    )


def page_projects() -> str:
    visible = [p for p in PROJECTS if p.get("status") != "hidden"]
    cards = "\n".join(project_card(p) for p in sorted(visible, key=lambda p: p["order"]))
    main = f"""    <div class="container">
      <div class="page-head prose">
        <p class="eyebrow">Index 01 — Projects</p>
        <h1>Projects</h1>
        <p class="page-head__lede">Engineering, research, and creative-technical work. Research write-ups live in <a href="/research/">Research</a>; image collections in <a href="/media/">Creative</a>.</p>
      </div>
      <div class="card-grid">
{cards}
      </div>
    </div>"""
    return shell(
        title=f'Projects — {S["title"]}',
        description="Selected engineering, research, and creative-technical projects by Elias \"Eliyahu\" Suskind.",
        path="/projects/",
        main_html=main,
        active="/projects/",
    )


def page_washburn() -> str:
    p = next(p for p in PROJECTS if p["slug"] == "washburn")
    rel = p["thumb"].lstrip("/")
    tags = "".join(f'<span class="tag">{e(d)}</span>' for d in p.get("disciplines", []))
    main = f"""    <div class="container">
      <div class="page-head prose">
        <p class="eyebrow">Project — {e(p["category"])}</p>
        <h1>{e(p["title"])}</h1>
        <p class="page-head__lede">{e(p["summary"])}</p>
        <p class="card__foot" style="margin-top:1rem">
          <span class="status status--{e(p["status"])}">{e(p["status"].replace("-", " "))}</span>
          {tags}
        </p>
      </div>
      <figure class="hero__portrait" style="display:inline-block">
        <span class="crosshair tl" aria-hidden="true"></span>
        <span class="crosshair br" aria-hidden="true"></span>
        {plain_img(rel, p.get("thumb_alt", ""))}
      </figure>
      <div class="prose stack" style="margin-top:var(--space-l)">
        <div class="note">
          <strong>Dossier in progress.</strong> Washburn is an in-development horror
          farming simulator. Screenshots, design notes, tooling, and a playable build
          will be published here as the project matures. In the meantime, project
          updates surface on my <a href="{e(A["github"])}" target="_blank" rel="noopener" class="ext">GitHub</a>.
        </div>
        <p><a class="btn" href="/projects/">← Back to all projects</a></p>
      </div>
    </div>"""
    return shell(
        title=f'{p["title"]} — {S["title"]}',
        description=p["summary"],
        path="/projects/washburn/",
        main_html=main,
        active="/projects/",
    )


def page_research() -> str:
    items = []
    for i, p in enumerate(sorted(PAPERS, key=lambda p: p["order"]), 1):
        meta = [p["kind"], f'{p["month"]} {p["year"]}']
        if p.get("doi"):
            meta.append(f'DOI {p["doi"]}')
        meta_html = "".join(f"<span>{e(m)}</span>" for m in meta)
        items.append(f"""      <li class="index-list__item">
        <span class="index-list__num">{i:02d}</span>
        <h2 class="index-list__title"><a href="{e(p["url"])}">{e(p["title"])}</a></h2>
        <p class="index-list__meta">{meta_html}</p>
        <p class="index-list__desc">{e(p["lead"])}</p>
      </li>""")
    main = f"""    <div class="container">
      <div class="page-head prose">
        <p class="eyebrow">Index 02 — Research &amp; publications</p>
        <h1>Research &amp; publications</h1>
        <p class="page-head__lede">Peer-reviewed and undergraduate research across biochemistry, immunology, and the life sciences. Full list on my <a href="{e(A["researchgate"])}" target="_blank" rel="noopener" class="ext">ResearchGate</a>.</p>
      </div>
      <ol class="index-list">
{chr(10).join(items)}
      </ol>
    </div>"""
    return shell(
        title=f'Research & publications — {S["title"]}',
        description="Peer-reviewed and undergraduate research by Elias \"Eliyahu\" Suskind, spanning biochemistry, immunology, and sensory science.",
        path="/research/",
        main_html=main,
        active="/research/",
    )


def page_paper(p: dict) -> str:
    body = (CONTENT / "research" / f'{p["slug"]}.html').read_text(encoding="utf-8")
    authors = ", ".join(p["authors"])
    meta_rows = [
        ("Authors", authors),
        ("Type", p["kind"]),
        ("Venue", p["venue"]),
        ("Published", f'{p["month"]} {p["year"]}'),
    ]
    if p.get("doi"):
        meta_rows.append(("DOI", p["doi"]))
    meta_html = "".join(
        f"<div><dt>{e(k)}</dt><dd>{e(v)}</dd></div>" for k, v in meta_rows
    )
    fig = p.get("figure")
    fig_html = ""
    if fig:
        rel = fig.lstrip("/")
        fig_html = f"""      <figure class="figure">
        <a href="/{e(rel)}" target="_blank" rel="noopener">{plain_img(rel, p.get("figure_alt", ""))}</a>
        <figcaption><span class="n">FIG. 1</span> — {e(p.get("figure_alt", ""))}</figcaption>
      </figure>"""
    main = f"""    <div class="container">
      <div class="page-head prose">
        <p class="eyebrow">{e(p["kind"])}</p>
        <h1>{e(p["title"])}</h1>
        <p class="page-head__lede">{e(p["lead"])}</p>
        <div class="btn-row">
          <a class="btn btn--solid" href="{e(p["external_url"])}" target="_blank" rel="noopener">{e(p.get("external_label", "Read the paper"))}</a>
          {f'<a class="btn" href="{e(p["pmc_url"])}" target="_blank" rel="noopener">PubMed Central</a>' if p.get("pmc_url") else ""}
        </div>
      </div>
      <dl class="meta-grid">{meta_html}</dl>
      <p class="citation">{e(citation_text(p))}</p>
{fig_html}
      <div class="prose stack">
{body}
        <p style="margin-top:var(--space-l)"><a class="btn" href="/research/">← All research</a></p>
      </div>
    </div>"""
    article = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "headline": p["title"],
        "author": [{"@type": "Person", "name": n} for n in p["authors"]],
        "datePublished": p["year"],
        "isPartOf": {"@type": "Periodical", "name": p["venue"]},
        "url": canonical(p["url"]),
    }
    if p.get("doi"):
        article["identifier"] = {"@type": "PropertyValue", "propertyID": "DOI", "value": p["doi"]}
    return shell(
        title=f'{p["title"]} — {S["title"]}',
        description=p["lead"],
        path=p["url"],
        main_html=main,
        active="/research/",
        jsonld=article,
        og_type="article",
    )


def page_media() -> str:
    cards = "\n".join(
        collection_card(c) for c in sorted(COLLECTIONS, key=lambda c: c["order"])
    )
    main = f"""    <div class="container">
      <div class="page-head prose">
        <p class="eyebrow">Index 03 — Creative work</p>
        <h1>Creative work</h1>
        <p class="page-head__lede">Photography and pixel art. Each collection opens to a full gallery — click any frame to view it larger.</p>
      </div>
      <div class="card-grid">
{cards}
      </div>
    </div>"""
    return shell(
        title=f'Creative work — {S["title"]}',
        description="Photography and pixel art by Elias \"Eliyahu\" Suskind.",
        path="/media/",
        main_html=main,
        active="/media/",
    )


def page_photography_index() -> str:
    photo = [c for c in COLLECTIONS if c["kind"] == "photography"]
    items = []
    for i, c in enumerate(sorted(photo, key=lambda c: c["order"]), 1):
        items.append(f"""      <li class="index-list__item">
        <span class="index-list__num">{i:02d}</span>
        <h2 class="index-list__title"><a href="{e(c["url"])}">{e(c["title"])}</a></h2>
        <p class="index-list__desc">{e(c["summary"])}</p>
      </li>""")
    # Documented but not-yet-published sets, preserved honestly from the old site.
    upcoming = [
        "Black &amp; white Pacific Northwest film photography",
        "Assorted digital photography",
    ]
    up_html = "".join(f"<li>{u} <span class=\"tag\">In preparation</span></li>" for u in upcoming)
    main = f"""    <div class="container">
      <div class="page-head prose">
        <p class="eyebrow">Creative — Photography</p>
        <h1>Photography</h1>
        <p class="page-head__lede">Collections shot for Golden Ratio Alchemy and around the Seattle music scene.</p>
      </div>
      <ol class="index-list">
{chr(10).join(items)}
      </ol>
      <div class="prose" style="margin-top:var(--space-l)">
        <h2>In preparation</h2>
        <ul class="prose">{up_html}</ul>
      </div>
    </div>"""
    return shell(
        title=f'Photography — {S["title"]}',
        description="Photography collections by Elias \"Eliyahu\" Suskind, including Golden Ratio Alchemy.",
        path="/media/photography/",
        main_html=main,
        active="/media/",
    )


def page_collection(c: dict) -> str:
    pixel = c["kind"] == "pixelart"
    prefix = c["slug"][:3].upper()
    sections = []
    for s in c.get("section", []):
        head = ""
        if s.get("title"):
            head = f'<h2 style="margin-bottom:var(--space-m)">{e(s["title"])}</h2>'
        note = f'<div class="note" style="margin-bottom:var(--space-m)">{s["note"]}</div>' if s.get("note") else ""
        gal = gallery_from_section(s, prefix, pixel=pixel)
        sections.append(f'<section style="margin-top:var(--space-l)">{head}{note}{gal}</section>')
    intro = c.get("intro", "")
    intro_html = f'<p class="page-head__lede">{intro}</p>' if intro else ""
    back = "/media/photography/" if c["kind"] == "photography" else "/media/"
    main = f"""    <div class="container">
      <div class="page-head prose">
        <p class="eyebrow">Collection — {e(c["kind"].title())}</p>
        <h1>{e(c["title"])}</h1>
        {intro_html}
      </div>
{chr(10).join(sections)}
      <p style="margin-top:var(--space-xl)"><a class="btn" href="{back}">← Back</a></p>
    </div>"""
    return shell(
        title=f'{c["title"]} — {S["title"]}',
        description=c["summary"],
        path=c["url"],
        main_html=main,
        active="/media/",
    )


def page_about() -> str:
    contact = [
        ("Email", f'mailto:{A["email"]}', A["email"], False),
        ("LinkedIn", A["linkedin"], "Eliyahu Suskind", True),
        ("GitHub", A["github"], "@JakobFinci", True),
        ("ResearchGate", A["researchgate"], "Elias Suskind", True),
        ("Photography", A["gra_site"], "Golden Ratio Alchemy", True),
    ]
    rows = []
    for k, href, v, ext in contact:
        attrs = ' target="_blank" rel="noopener" class="ext"' if ext else ""
        rows.append(
            f'<a href="{e(href)}"{attrs}><span class="k">{e(k)}</span><span class="v">{e(v)}</span></a>'
        )
    body = (CONTENT / "about.html").read_text(encoding="utf-8")
    main = f"""    <div class="container">
      <div class="page-head prose">
        <p class="eyebrow">Index 04 — About</p>
        <h1>About</h1>
      </div>
      <div class="prose stack">
{body}
      </div>

      <section id="contact" style="margin-top:var(--space-2xl)">
        <div class="section-head">
          <h2>Contact</h2>
          <span class="index">Reach out</span>
        </div>
        <p class="lede" style="margin-bottom:var(--space-m)">Happy to talk about research, engineering, or a photo shoot.</p>
        <div class="contact-list">
          {"".join(rows)}
        </div>
      </section>
    </div>"""
    return shell(
        title=f'About — {S["title"]}',
        description="About Elias \"Eliyahu\" Suskind — interdisciplinary background across engineering, biology, scientific computing, and visual media, plus contact links.",
        path="/about/",
        main_html=main,
        active="/about/",
    )


def page_404() -> str:
    main = """    <div class="container">
      <div class="notfound">
        <p class="code">404</p>
        <h1>Page not found</h1>
        <p class="lede center" style="margin:var(--space-m) auto 0">
          That page doesn't exist — it may have moved. Try one of these:
        </p>
        <div class="btn-row" style="justify-content:center;margin-top:var(--space-l)">
          <a class="btn btn--solid" href="/">Home</a>
          <a class="btn" href="/projects/">Projects</a>
          <a class="btn" href="/research/">Research</a>
          <a class="btn" href="/media/">Creative</a>
          <a class="btn" href="/about/">About</a>
        </div>
      </div>
    </div>"""
    doc = shell(
        title=f'404 — {S["title"]}',
        description="Page not found.",
        path="/404.html",
        main_html=main,
    )
    return doc


def redirect_page(to: str, title: str) -> str:
    url = canonical(to)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Redirecting — {e(title)}</title>
  <link rel="canonical" href="{e(url)}">
  <meta http-equiv="refresh" content="0; url={e(to)}">
  <meta name="robots" content="noindex">
</head>
<body>
  <p>This page has moved to <a href="{e(to)}">{e(url)}</a>.</p>
  <script>location.replace({json.dumps(to)});</script>
</body>
</html>
"""


# --------------------------------------------------------------------------
# Sitemap + robots
# --------------------------------------------------------------------------
def build_sitemap(paths: list[str]) -> str:
    urls = "\n".join(
        f"  <url><loc>{e(canonical(p))}</loc></url>" for p in paths
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>\n"
    )


def build_robots() -> str:
    return f"User-agent: *\nAllow: /\n\nSitemap: {canonical('/sitemap.xml')}\n"


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def build_pages() -> dict[str, str]:
    pages: dict[str, str] = {}
    pages["index.html"] = page_home()
    pages["projects/index.html"] = page_projects()
    pages["projects/washburn/index.html"] = page_washburn()
    pages["research/index.html"] = page_research()
    for p in PAPERS:
        pages[p["url"].strip("/") + "/index.html"] = page_paper(p)
    pages["media/index.html"] = page_media()
    pages["media/photography/index.html"] = page_photography_index()
    for c in COLLECTIONS:
        pages[c["url"].strip("/") + "/index.html"] = page_collection(c)
    pages["about/index.html"] = page_about()
    pages["404.html"] = page_404()

    # Redirect stubs for previously-published URLs.
    pages["contact/index.html"] = redirect_page("/about/#contact", "About")
    pages["projects/papers/index.html"] = redirect_page("/research/", "Research")
    pages["projects/papers/tea/index.html"] = redirect_page("/research/puerh-tea/", "Aging Gracefully")
    pages["projects/papers/EoE/index.html"] = redirect_page("/research/eoe-therapies/", "EoE therapies review")

    # Sitemap: canonical routes only (skip 404 + redirect stubs).
    routes = ["/", "/projects/", "/projects/washburn/", "/research/"]
    routes += [p["url"] for p in PAPERS]
    routes += ["/media/", "/media/photography/"]
    routes += [c["url"] for c in COLLECTIONS]
    routes += ["/about/"]
    pages["sitemap.xml"] = build_sitemap(routes)
    pages["robots.txt"] = build_robots()
    return pages


def write(pages: dict[str, str], root: Path) -> None:
    for rel, content in pages.items():
        out = root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    pages = build_pages()
    if "--check" in sys.argv:
        mismatched = []
        for rel, content in pages.items():
            existing = ROOT / rel
            if not existing.exists() or existing.read_text(encoding="utf-8") != content:
                mismatched.append(rel)
        if mismatched:
            print("DRIFT: committed output is stale. Run `python _src/build.py`:")
            for m in mismatched:
                print("  -", m)
            return 1
        print(f"OK: {len(pages)} generated files match committed output.")
        return 0
    write(pages, ROOT)
    print(f"Built {len(pages)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
