"""Static site generator for jakobfinci.github.io.

Zero third-party dependencies — Python 3.11 standard library only (tomllib).
Reads structured data from _src/data/*.toml and long-form article bodies from
_src/content/, and writes plain HTML to canonical paths in the repo root. That
output is committed and served as-is by GitHub Pages (.nojekyll disables the
Ruby build), so there is no server-side build step to break.

    python _src/build.py            # build
    python _src/build.py --check    # compare in memory, without writing files

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


def photo_img(rel: str, alt: str) -> str:
    thumb, w, h = photo_variant(rel, "thumb")
    display, dw, _ = photo_variant(rel, "display")
    return (f'<img src="{e(thumb)}" srcset="{e(thumb)} {w}w, {e(display)} {dw}w" '
            f'sizes="(max-width: 40rem) 90vw, 60vw" alt="{e(alt)}" width="{w}" height="{h}" '
            'loading="lazy" decoding="async">')


# --------------------------------------------------------------------------
# Layout shell
# --------------------------------------------------------------------------
def nav_html(active: str, path: str) -> str:
    items = []
    for item in SITE["nav"]:
        cur = ""
        if item["url"] == active:
            cur = ' aria-current="page"' if item["url"] == path else ' aria-current="true"'
        items.append(f'<li><a href="{e(item["url"])}"{cur}>{e(item["label"])}</a></li>')
    return (
        '<nav class="site-nav" aria-label="Primary">\n      <ul>\n        '
        + "\n        ".join(items)
        + "\n      </ul>\n    </nav>"
    )


def header_html(active: str, path: str) -> str:
    return f"""  <header class="site-header">
    <div class="container site-header__inner">
      <a class="brand" href="/">{e(S["title"])}</a>
    {nav_html(active, path)}
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
          active: str = "", jsonld: dict | list | None = None,
          og_type: str = "website", body_class: str = "") -> str:
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
  <meta name="twitter:image" content="{e(canonical(OG_IMAGE))}">{ld}
</head>
<body class="{e(body_class)}">
  <a class="skip-link" href="#main">Skip to content</a>
{header_html(active, path)}
  <main id="main" tabindex="-1">
{main_html}
  </main>
{footer_html()}
</body>
</html>
"""


# --------------------------------------------------------------------------
# Reusable components
# --------------------------------------------------------------------------

def project_entry(p: dict) -> str:
    media = plain_img(p["thumb"].lstrip("/"), p["thumb_alt"]) if p.get("thumb") else ""
    return f"""      <article class="project-feature">
        <div class="project-feature__image">{media}</div>
        <div>
          <h3><a href="{e(p['url'])}">{e(p['title'])}</a></h3>
          <p>{e(p['summary'])}</p>
        </div>
      </article>"""


def collection_entry(c: dict) -> str:
    return f"""      <article class="photo-collection">
        <figure>
          <a href="{e(c['url'])}" aria-label="View {e(c['title'])}">{photo_img(c['cover'], c['cover_caption'])}</a>
          <figcaption>{e(c['cover_caption'])}</figcaption>
        </figure>
        <div class="photo-collection__text">
          <h2><a href="{e(c['url'])}">{e(c['title'])}</a></h2>
          <p>{e(c['summary'])}</p>
          <a href="{e(c['url'])}">View photographs →</a>
        </div>
      </article>"""


def media_nav(path: str) -> str:
    links = []
    for url, label in [("/media/", "Mixed media"), ("/media/photography/", "Photography"),
                       ("/media/pixelart/", "Pixel art")]:
        current = ' aria-current="page"' if path == url else ""
        links.append(f'<a href="{url}"{current}>{label}</a>')
    return '<nav class="section-nav" aria-label="Mixed media">' + "".join(links) + '</nav>'


def publication_entry(p: dict, brief: bool = False) -> str:
    title = p["short_title"] if brief else p["title"]
    authors = "" if brief else f'<p class="publication-authors">{e(", ".join(p["authors"]))}</p>'
    description = "" if brief else f'<p class="publication-description">{e(p["lead"])}</p>'
    doi = (f'<p><a href="https://doi.org/{e(p["doi"])}">doi:{e(p["doi"])}</a></p>'
           if p.get("doi") and not brief else "")
    return f"""<article class="publication">
        <h3><a href="{e(p['url'])}">{e(title)}</a></h3>{authors}
        <p class="publication-venue"><cite>{e(p['venue'])}</cite>, {e(p['month'])} {e(p['year'])}.</p>{description}{doi}
      </article>"""


def gallery_from_section(section: dict, pixel: bool = False) -> str:
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
    for rel, caption in entries:
        if pixel or rel not in IMAGES:
            w, h = dims_of(rel)
            dim = f' width="{w}" height="{h}"' if w else ""
            thumb = f'<img src="/{e(rel)}" alt="{e(caption)}"{dim} loading="lazy" decoding="async">'
            full = "/" + rel
        else:
            d_href, _, _ = photo_variant(rel, "display")
            thumb = photo_img(rel, caption)
            full = d_href
        cap_html = (
            f'<figcaption>{e(caption)}</figcaption>'
            if caption
            else ""
        )
        figs.append(
            f'<figure class="{"portrait" if dims_of(rel)[1] > dims_of(rel)[0] else "landscape"}"><a href="{e(full)}" '
            f'aria-label="View full size: {e(caption)}">{thumb}</a>{cap_html}</figure>'
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
    # Retain the withdrawn Currently/Creative card sections as withdrawn.
    # The original pixel portrait remains the homepage's visual centerpiece.
    washburn = next(p for p in PROJECTS if p["slug"] == "washburn")
    papers = "\n".join(publication_entry(p, brief=True) for p in sorted(PAPERS, key=lambda p: p["order"]))
    main = f"""    <div class="container">
      <section class="home-intro" aria-labelledby="home-title">
        <div class="home-intro__text">
          <div class="home-name">
            <h1 id="home-title">Elias <span>“Eliyahu”</span><br> Suskind</h1>
          </div>
          <p class="home-tagline">{e(SITE['identity']['tagline'])}</p>
          <p class="hero__intro">{e(SITE['identity']['positioning'])}</p>
          <div class="hero__links">
            <a href="/about/">A little about me →</a>
            <a href="/about/#contact">Get in touch</a>
          </div>
        </div>
        <figure class="home-portrait">
          {plain_img('medialib/me.png', 'Pixel-art portrait of Elias Suskind, arms crossed', priority=True)}
        </figure>
      </section>
      <div class="home-work" id="work-h">
        <section class="home-research" aria-labelledby="research-h">
          <h2 id="research-h"><a href="/research/">Research &amp; publications</a></h2>
          {papers}
          <a href="/research/">All research →</a>
        </section>
        <section class="home-projects" aria-labelledby="projects-h">
          <h2 id="projects-h"><a href="/projects/">Game development</a></h2>
          {project_entry(washburn)}
          <a href="/projects/">All projects →</a>
        </section>
      </div>
    </div>"""
    person = {
        "@context": "https://schema.org", "@type": "Person",
        "name": A["name"], "alternateName": A["alt_name"], "url": BASE + "/",
        "image": canonical("/medialib/me.png"),
        "sameAs": [A["github"], A["linkedin"], A["researchgate"]],
    }
    return shell(title=f'{S["title"]} — engineer, researcher, and creator',
                 description=S["description"], path="/", main_html=main,
                 active="/", jsonld=person, body_class="page--home")


def page_projects() -> str:
    # Papers have their own catalog and home at /research/. Only real, public
    # projects form groups here; withheld industry drafts do not make empty groups.
    visible = sorted((p for p in PROJECTS if p["status"] != "hidden"), key=lambda p: p["order"])
    groups = []
    for category in dict.fromkeys(p["category"] for p in visible):
        entries = "\n".join(project_entry(p) for p in visible if p["category"] == category)
        groups.append(f'<section class="project-group"><h2>{e(category)}</h2>{entries}</section>')
    main = f"""    <div class="container">
      <div class="page-head"><h1>Projects</h1></div>
      {''.join(groups)}
      <p class="related-section">For scientific work, see <a href="/research/">Research &amp; publications →</a></p>
    </div>"""
    return shell(title=f'Projects — {S["title"]}',
                 description='Engineering and independent game projects by Elias "Eliyahu" Suskind.',
                 path="/projects/", main_html=main, active="/projects/", body_class="page--projects")


def page_washburn() -> str:
    p = next(p for p in PROJECTS if p["slug"] == "washburn")
    main = f"""    <div class="container">
      <div class="game-intro">
        <figure class="game-emblem">{plain_img(p['thumb'].lstrip('/'), p['thumb_alt'], priority=True)}</figure>
        <div class="page-head prose">
          <h1>{e(p['title'])}</h1>
          <p class="page-head__lede">{e(p['summary'])} More to come soon.</p>
          <p class="back-link"><a href="/projects/">← All projects</a></p>
        </div>
      </div>
    </div>"""
    return shell(title=f'{p["title"]} — {S["title"]}', description=p["summary"],
                 path="/projects/washburn/", main_html=main, active="/projects/",
                 body_class="page--washburn")


def page_research() -> str:
    sections = []
    for group in dict.fromkeys(p["group"] for p in sorted(PAPERS, key=lambda p: p["order"])):
        entries = "\n".join(publication_entry(p) for p in PAPERS if p["group"] == group)
        representative = next(p for p in PAPERS if p["group"] == group)
        emblem = plain_img(representative["thumb"].lstrip("/"), representative["thumb_alt"], cls="research-group__art")
        sections.append(f'<section class="research-group"><div><h2>{e(group)}</h2>{emblem}</div><div>{entries}</div></section>')
    # Personal introduction restored from 70a5be4, with a small grammatical repair.
    main = f"""    <div class="container">
      <div class="page-head prose">
        <h1>Research &amp; publications</h1>
        <p class="page-head__lede">Here you can find a high-level overview of some of my favorite research papers I have either authored or co-authored.
        For a more comprehensive list, please visit my <a href="{e(A['researchgate'])}" target="_blank" rel="noopener">ResearchGate</a>.</p>
      </div>
      {''.join(sections)}
    </div>"""
    return shell(title=f'Research & publications — {S["title"]}',
                 description='Peer-reviewed articles and undergraduate research by Elias "Eliyahu" Suskind.',
                 path="/research/", main_html=main, active="/research/", body_class="page--research")


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
        <h1>{e(p["title"])}</h1>
        <p class="page-head__lede">{e(p["lead"])}</p>
        <div class="btn-row">
          <a class="btn btn--solid" href="{e(p["external_url"])}" target="_blank" rel="noopener">{e(p.get("external_label", "Read the paper"))}</a>
          {f'<a class="btn" href="{e(p["pmc_url"])}" target="_blank" rel="noopener">PubMed Central</a>' if p.get("pmc_url") else ""}
        </div>
      </div>
      <dl class="meta-grid">{meta_html}</dl>
{fig_html}
      <div class="prose stack">
{body}
        <section class="paper-citation"><h2>Cite this work</h2><p class="citation">{e(citation_text(p))}</p></section>\n        <p class="back-link"><a class="btn" href="/research/">← All research</a></p>
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
        body_class="page--paper",
    )


def page_media() -> str:
    photograph = SITE["media_photo"]
    pixel = next(c for c in COLLECTIONS if c["kind"] == "pixelart")
    main = f"""    <div class="container">
      <div class="page-head"><h1>Mixed media</h1></div>
      <section class="media-photography" aria-labelledby="photography-h">
        <figure>
          <a href="/media/photography/" aria-label="View photography">
            {photo_img(photograph['src'], photograph['caption'])}
          </a>
          <figcaption>{e(photograph['caption'])}</figcaption>
        </figure>
        <div>
          <h2 id="photography-h"><a href="/media/photography/">Photography</a></h2>
          <p>Collections shot for Golden Ratio Alchemy and around the Seattle music scene.</p>
          <a href="/media/photography/">Explore the collections →</a>
        </div>
      </section>
      <section class="media-pixel" aria-labelledby="pixel-h">
        <div>
          <h2 id="pixel-h"><a href="/media/pixelart/">Pixel art</a></h2>
          <p>{e(pixel['summary'])}</p>
          <a href="/media/pixelart/">See the artwork →</a>
        </div>
        <a href="/media/pixelart/" aria-label="View pixel art">
          {plain_img('medialib/pixelart/Sprite-0006.png', 'Goko can set against the pixel landscape')}
        </a>
      </section>
    </div>"""
    return shell(title=f'Mixed media — {S["title"]}',
                 description='Photography and pixel art by Elias "Eliyahu" Suskind.',
                 path="/media/", main_html=main, active="/media/", body_class="page--media")


def page_photography_index() -> str:
    photo = sorted((c for c in COLLECTIONS if c["kind"] == "photography"), key=lambda c: c["order"])
    # The 2025 film and assorted-digital links were empty "Coming Soon" pages.
    # Preserve that historical intent here without inventing galleries or dates.
    main = f"""    <div class="container">
      {media_nav('/media/photography/')}
      <div class="page-head"><h1>Photography</h1></div>
      <div class="photo-collections">
        {''.join(collection_entry(c) for c in photo)}
      </div>
    </div>"""
    return shell(title=f'Photography — {S["title"]}',
                 description='Photography collections by Elias "Eliyahu" Suskind, including Golden Ratio Alchemy.',
                 path="/media/photography/", main_html=main, active="/media/",
                 body_class="page--photo-index")


def page_collection(c: dict) -> str:
    pixel = c["kind"] == "pixelart"
    sections, jumps = [], []
    for section in c.get("section", []):
        title = section.get("title", "")
        anchor = section.get("id", "")
        head = f'<h2>{e(title)}</h2>' if title else ""
        attrs = f' id="{e(anchor)}"' if anchor else ""
        if anchor:
            jumps.append(f'<a href="#{e(anchor)}">{e(title)}</a>')
        note = f'<div class="collection-note prose">{section["note"]}</div>' if section.get("note") else ""
        gallery = gallery_from_section(section, pixel=pixel)
        sections.append(f'<section class="collection-section"{attrs}>{head}{note}{gallery}</section>')
    intro = c.get("intro", "")
    intro_html = f'<p class="page-head__lede">{intro}</p>' if intro else ""
    jump_nav = '<nav class="collection-jumps" aria-label="In this collection">' + "".join(jumps) + '</nav>' if len(jumps) > 1 else ""
    back = "/media/photography/" if not pixel else "/media/"
    back_label = "All photography" if not pixel else "Mixed media"
    main = f"""    <div class="container">
      {media_nav(c['url'])}
      <div class="page-head prose">
        <h1>{e(c['title'])}</h1>
        {intro_html}
      </div>{jump_nav}
      {''.join(sections)}
      <p class="back-link"><a href="{back}">← {back_label}</a></p>
    </div>"""
    return shell(title=f'{c["title"]} — {S["title"]}', description=c["summary"],
                 path=c["url"], main_html=main, active="/media/",
                 body_class="page--pixelart" if pixel else "page--photography")


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
      <div class="about-layout">
        <div class="about-sidebar">
          <h1>About</h1>
          <nav aria-label="About sections">
            <a href="#academic">Academic &amp; research direction</a>
            <a href="#technical">Technical background</a>
            <a href="#creative">Creative practice</a>
            <a href="#interests">Personal interests</a>
            <a href="#username">Why “JakobFinci”?</a>
            <a href="#contact">Contact</a>
          </nav>
        </div>
        <div class="prose stack">{body}</div>
      </div>

      <section id="contact" class="contact-section">
        <div class="section-head">
          <h2>Contact</h2>
        </div>
        <p class="lede">Happy to talk about research, engineering, or a photo shoot.</p>
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
        body_class="page--about",
    )


def page_fun_things() -> str:
    body = (CONTENT / "fun-things.html").read_text(encoding="utf-8")
    main = f"""    <div class="container">
      <div class="about-layout">
        <div class="about-sidebar">
          <h1>Fun things</h1>
          <nav aria-label="Fun things sections">
            <a href="#all-tomorrows">All Tomorrows</a>
            <a href="#bee-movie">The Bee Movie incident</a>
            <a href="#tea">Di-Er Teamaster</a>
            <a href="#pen-pal">Letters to a Pre-Scientist</a>
          </nav>
        </div>
        <div class="prose stack">{body}</div>
      </div>
    </div>"""
    return shell(
        title=f'Fun things — {S["title"]}',
        description="Side projects, curious participations, and other things Elias Suskind is glad to have done.",
        path="/fun-things/",
        main_html=main,
        active="/fun-things/",
        body_class="page--about",
    )


def page_404() -> str:
    # 1823946 + 379f173 deliberately restored the full-screen Rick Astley joke.
    # Keep its own layout and real video controls, not the portfolio shell.
    return (CONTENT / "404.html").read_text(encoding="utf-8")


def redirect_page(to: str, title: str) -> str:
    url = canonical(to)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Redirecting — {e(title)}</title>
  <link rel="canonical" href="{e(url)}">
  <meta http-equiv="refresh" content="0; url={e(to)}">
  <meta name="robots" content="noindex">
</head>
<body>
  <p>This page has moved to <a href="{e(to)}">{e(url)}</a>.</p>
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
    pages["fun-things/index.html"] = page_fun_things()
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
    routes += ["/about/", "/fun-things/"]
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
