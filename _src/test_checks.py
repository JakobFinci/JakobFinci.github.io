"""Regression tests for failures the old checker missed. No third-party packages."""
import tempfile
import unittest
from pathlib import Path

import build
import checks


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = build.build_pages()
        cls.files = checks.public_files(build.ROOT)

    def changed(self, path, old, new):
        self.assertIn(old, self.pages[path])
        pages = dict(self.pages)
        pages[path] = pages[path].replace(old, new, 1)
        return pages

    def test_clean_build(self):
        self.assertEqual([], checks.validate_pages(self.pages, self.files))
        self.assertEqual([], checks.check_editorial(self.pages))
        self.assertEqual([], checks.check_media(self.files))

    def test_build_is_deterministic(self):
        self.assertEqual(self.pages, build.build_pages())

    def test_drift_and_missing_output_are_detected_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build.write(self.pages, root)
            self.assertEqual([], checks.check_drift(self.pages, root))
            home = root / 'index.html'
            home.write_text('intentional manual edit', encoding='utf-8')
            (root / '404.html').unlink()
            errors = checks.check_drift(self.pages, root)
            self.assertEqual(2, len(errors))
            self.assertEqual('intentional manual edit', home.read_text(encoding='utf-8'))

    def test_missing_about_closing_div_is_not_silently_autoclosed(self):
        doc = checks.Document('<html><head><title>About</title></head><body><main><div><div>About</div></main></body></html>')
        self.assertTrue(any('expected </div>' in e for e in doc.errors))

    def test_invalid_nesting_and_duplicate_attributes(self):
        for html in ('<p><div>text</div></p>', '<a><a>nested</a></a>', '<div class="a" class="b"></div>'):
            with self.subTest(html=html):
                self.assertTrue(checks.Document(html).errors)

    def test_relative_links_and_encoded_fragments(self):
        self.assertEqual(('about/index.html', 'contact'), checks.local_target('../about/#cont%61ct', 'projects/index.html'))
        self.assertEqual(('index.html', 'work-h'), checks.local_target('#work-h', 'index.html'))
        self.assertIsNone(checks.local_target('mailto:a@example.com', 'index.html'))

    def test_missing_cross_page_anchor(self):
        pages = self.changed('index.html', '/about/#contact', '/about/#missing')
        self.assertTrue(any('[anchor]' in e for e in checks.validate_pages(pages, self.files)))

    def test_relative_missing_asset(self):
        pages = self.changed('index.html', 'src="/medialib/me.png"', 'src="missing.png"')
        self.assertTrue(any('missing.png' in e for e in checks.validate_pages(pages, self.files)))

    def test_same_host_asset_and_case_sensitivity(self):
        pages = self.changed('index.html', 'src="/medialib/me.png"', f'src="{build.BASE}/medialib/Me.png"')
        self.assertTrue(any('Me.png' in e for e in checks.validate_pages(pages, self.files)))

    def test_srcset_candidate_is_checked(self):
        pages = self.changed('media/index.html', '.display.webp 1400w', '.missing.webp 1400w')
        self.assertTrue(any('.missing.webp' in e for e in checks.validate_pages(pages, self.files)))

    def test_metadata_does_not_depend_on_exact_main_markup(self):
        pages = self.changed('index.html', 'name="description"', 'name="missing"')
        pages['index.html'] = pages['index.html'].replace('<main id="main" tabindex="-1">', '<main id="main" class="different">')
        self.assertTrue(any('missing description' in e for e in checks.validate_pages(pages, self.files)))

    def test_duplicate_ids(self):
        pages = self.changed('index.html', '<h1 id="home-title">', '<h1 id="main">')
        self.assertTrue(any('duplicate id' in e for e in checks.validate_pages(pages, self.files)))

    def test_invalid_jsonld(self):
        pages = self.changed('index.html', '"@type": "Person"', '"@type": invalid')
        self.assertTrue(any('invalid JSON-LD' in e for e in checks.validate_pages(pages, self.files)))

    def test_image_dimensions(self):
        pages = self.changed('index.html', 'width="171"', 'width="172"')
        self.assertTrue(any('dimensions disagree' in e for e in checks.validate_pages(pages, self.files)))

    def test_missing_derivative(self):
        files = self.files - {next(iter(build.IMAGES.values()))['thumb']['path']}
        self.assertTrue(checks.check_media(files))

    def test_legacy_contact_target(self):
        pages = self.changed('contact/index.html', '0; url=/about/#contact', '0; url=/about/#missing')
        self.assertTrue(any('[redirect]' in e for e in checks.validate_pages(pages, self.files)))

    def test_sitemap_does_not_list_redirects(self):
        pages = self.changed('sitemap.xml', '</urlset>', f'<url><loc>{build.BASE}/contact/</loc></url></urlset>')
        self.assertTrue(any('[sitemap]' in e for e in checks.validate_pages(pages, self.files)))

    def test_authorial_corrections_cannot_be_replaced_by_a_matching_build(self):
        for path, old, new in [
            ('about/index.html', 'Mr. Dell Conagher', 'a practical engineer'),
            ('404.html', '/medialib/404.mp4', '/medialib/missing.mp4'),
            ('media/pixelart/index.html', 'never actually used in any official Goko adverts or media', 'commercial work'),
            ('index.html', '</main>', '<section id="now-h">Currently</section></main>'),
            ('index.html', '</main>', '<section id="creative-h">Creative work</section></main>'),
            ('projects/index.html', '</main>', '<p>Goko Energy</p></main>'),
        ]:
            with self.subTest(path=path, old=old):
                self.assertTrue(checks.check_editorial(self.changed(path, old, new)))

    def test_redundant_metadata_heading_is_rejected(self):
        pages = self.changed('index.html', '</main>', '<p class="eyebrow">Research · 2025</p></main>')
        self.assertTrue(any('decorative metadata' in e for e in checks.check_editorial(pages)))

    def test_publications_have_one_catalog_and_do_not_reappear_as_projects(self):
        paper_urls = {p['url'] for p in build.PAPERS}
        project_urls = {p.get('url') for p in build.PROJECTS}
        self.assertTrue(paper_urls.isdisjoint(project_urls))
        paper = build.PAPERS[0]
        pages = self.changed('projects/index.html', '</main>', f'<a href="{paper["url"]}">Paper</a></main>')
        self.assertTrue(checks.check_editorial(pages))

    def test_unpublished_photography_categories_stay_unpublished(self):
        pages = self.changed('media/photography/index.html', '</main>', '<a href="/media/photography/asfilm/">Film</a></main>')
        self.assertTrue(checks.check_editorial(pages))


if __name__ == '__main__':
    unittest.main()
