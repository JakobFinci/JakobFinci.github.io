# Refactor Suggestions

This document outlines focused refactors to make the site easier to maintain, more readable, and less error-prone.

## 1) Adopt Jekyll layouts/includes for shared page chrome

**Problem:** Core page sections are duplicated across many pages (head metadata, navigation masthead, footer, script includes).

**Refactor:**
- Create `_layouts/default.html` for the global page structure.
- Create `_includes/head.html`, `_includes/nav.html`, and `_includes/footer.html`.
- Convert each standalone HTML page into a lightweight page file with front matter and only page-specific content.

**Benefit:**
- One place to change navigation links/metadata.
- Fewer copy-paste mistakes and broken markup.

## 2) Fix invalid document structure and nested body tags

**Problem:** Multiple pages contain malformed HTML patterns (duplicate `<body>` tags, duplicate `</html>`, and content after `</body>`).

**Refactor:**
- Ensure each page follows strict structure: `<!doctype> -> <html> -> <head> -> <body> -> </body> -> </html>`.
- Move footer and script tags inside `<body>`.
- Run an HTML validator in CI (e.g., `html-validate` or `tidy`) to catch regressions.

**Benefit:**
- Improved browser consistency.
- Better accessibility and SEO parser reliability.

## 3) Move inline CSS to reusable stylesheets

**Problem:** Pages define one-off `<style>` blocks with repeated patterns (colors, typography, spacing, card/media grid behavior).

**Refactor:**
- Move page-level styles into `assets/css/main.css` or split into logical partials (e.g., `layout.css`, `components.css`, `pages/home.css`).
- Introduce CSS custom properties (`:root`) for brand colors and spacing scales.
- Reuse utility classes for repeated spacing (replacing inline spacer divs like `style="height: 50px;"`).

**Benefit:**
- Cleaner HTML and more consistent styling.
- Easier responsive tuning and fewer styling conflicts.

## 4) Replace repeated content blocks with data-driven loops

**Problem:** Portfolio cards (media/projects/papers) are hand-authored and duplicated.

**Refactor:**
- Store portfolio items in `_data/projects.yml` and `_data/media.yml`.
- Render cards via Liquid loops in one reusable include, e.g. `_includes/card-grid.html`.
- Keep per-item fields standardized: title, href, thumbnail, alt, description, tags.

**Benefit:**
- Add/update entries without editing page structure.
- Prevents inconsistent card markup and missing alt text.

## 5) Introduce semantic and accessibility improvements

**Problem:** Some pages rely on generic `div` wrappers and visual spacing hacks.

**Refactor:**
- Use semantic landmarks (`<header>`, `<main>`, `<section>`, `<footer>`).
- Ensure a single `<h1>` per page and descending heading order.
- Add explicit `aria-label`s where needed and verify keyboard navigation through nav/menu.

**Benefit:**
- Better screen reader experience.
- Clearer document hierarchy and maintainability.

## 6) Normalize asset pathing and metadata per page

**Problem:** Mixed relative/absolute paths and page metadata appears to be identical across sections.

**Refactor:**
- Prefer root-relative paths for internal assets (`/medialib/...`) for consistency.
- Populate page-specific front matter (`title`, `description`, `permalink`, `image`) and generate Open Graph/Twitter metadata from layout templates.

**Benefit:**
- Fewer broken links when moving files.
- Better link previews and page-level SEO quality.

## 7) Add lightweight quality gates

**Problem:** Structural regressions are easy in static HTML-heavy repos.

**Refactor:**
- Add scripts for:
  - HTML lint/validate
  - Link checking (internal link integrity)
  - Optional formatting/linting for CSS/JS
- Run checks in CI on pull requests.

**Benefit:**
- Faster feedback before deploy.
- Prevents shipping broken navigation/markup.

## Recommended implementation order

1. Build layout + includes and migrate nav/head/footer.
2. Fix malformed HTML and remove nested/duplicate body/html tags.
3. Move inline styles to stylesheet + introduce design tokens.
4. Convert portfolio sections to data-driven card rendering.
5. Add validation scripts and CI checks.

This order gives the highest maintainability gains early while minimizing migration risk.
