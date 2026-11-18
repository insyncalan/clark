"""Row 1269, slice B: the served page and the published file read the install's Theme.

Classic layers the Theme block between the committed tokens and the brand; Cards is today's page byte for byte. A file made
before the Theme step keeps Cards. Fictional data only. Run: python3 dev/run_tests.py test_theme_pages
"""
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _demo import DemoStore

from clark import __main__ as launcher, page, publish, theme
from clark.store import open_store

NAME = "prototype-2.0"


def style_ids(html):
    return re.findall(r'<style\b[^>]*?\bid="([^"]*)"', html)


class Mapping(unittest.TestCase):
    def test_classic_is_the_shipped_theme_and_cards_is_none(self):
        self.assertEqual(theme.name_for("classic"), NAME)
        self.assertIn(NAME, theme.installed())
        for other in ("cards", None, "", "Classic", 5, "../x"):
            self.assertIsNone(theme.name_for(other), other)


class Served(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.db = self.dir / "clark.db"

    def served(self, project=None):
        return launcher.page_of(self.db, onedrive_roots=[])(project)

    def set_theme(self, value):
        s = open_store(self.db, onedrive_roots=[])
        try:
            with s.con:
                s.con.execute("UPDATE app_settings SET theme = ? WHERE id = 1", (value,))
        finally:
            s.close()

    def test_a_new_file_is_served_in_classic(self):
        html = self.served()
        self.assertEqual(html.count('id="theme"'), 1)
        self.assertEqual(html, page.page_html(branding=page.NO_BRAND, theme=NAME))

    def test_cards_is_the_page_as_it_was(self):
        open_store(self.db, onedrive_roots=[]).close()
        self.set_theme("cards")
        html = self.served()
        self.assertNotIn('id="theme"', html)
        self.assertEqual(html, page.page_html(branding=page.NO_BRAND))

    def test_a_change_is_read_at_the_next_request(self):
        open_store(self.db, onedrive_roots=[]).close()
        self.assertIn('id="theme"', self.served())
        self.set_theme("cards")
        self.assertNotIn('id="theme"', self.served())
        self.set_theme("classic")
        self.assertIn('id="theme"', self.served())

    def test_a_file_made_before_the_step_is_served_in_cards(self):
        from test_store_use_case_done_migration import make_at
        self.db = make_at(self.dir, 26)
        self.assertNotIn('id="theme"', self.served())

    def test_no_file_that_can_be_read_is_today_s_page(self):
        self.db.write_text("not a database", encoding="utf-8")
        self.assertEqual(self.served(), page.page_html(branding=page.NO_BRAND))

    def test_brand_wins_over_theme_and_there_is_one_block_of_each(self):
        brand = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, brand, True)
        (brand / "tokens.css").write_text(":root { --page-grad: none; }", encoding="utf-8")
        html = page.page_html(branding=brand, theme=NAME)
        self.assertEqual(style_ids(html).count("theme"), 1)
        self.assertEqual(style_ids(html).count("brand-local"), 1)
        ids = style_ids(html)
        self.assertLess(ids.index("brand-demo"), ids.index("theme"))
        self.assertLess(ids.index("theme"), ids.index("brand-local"))

    def test_style_block_count_grows_by_exactly_one_in_classic(self):
        base = page.page_html(branding=page.NO_BRAND)
        self.assertEqual(self.served().count("<style"), base.count("<style") + 1)


class Published(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def file(self):
        return publish.build(self.s, "ABC", now="2030-01-15", number=1)["body"]

    def set_theme(self, value):
        with self.s.con:
            self.s.con.execute("UPDATE app_settings SET theme = ? WHERE id = 1", (value,))

    def test_classic_file_inlines_the_theme_once_before_nothing_else_changes(self):
        self.set_theme("classic")
        text = self.file().decode("utf-8")
        self.assertEqual(text.count('id="theme"'), 1)
        self.assertLess(text.index('id="brand-demo"'), text.index('id="theme"'))

    def test_cards_file_has_no_theme_block(self):
        self.set_theme("cards")
        self.assertNotIn('id="theme"', self.file().decode("utf-8"))

    def test_a_new_publish_takes_the_choice_of_that_moment_and_an_old_file_is_untouched(self):
        self.set_theme("cards")
        old = self.file()
        self.set_theme("classic")
        new = self.file()
        self.assertNotIn(b'id="theme"', old)
        self.assertIn(b'id="theme"', new)
        self.set_theme("cards")
        self.assertEqual(self.file(), old)
        self.assertNotIn(b'id="theme"', old)

    def test_the_policy_hashes_cover_the_theme_block(self):
        self.set_theme("classic")
        text = self.file().decode("utf-8")
        self.assertEqual(len(re.findall(r"<style\b", text)), len(re.findall(r"'sha256-", re.search(r"style-src-elem([^;]*)", text).group(1))))

    def test_the_marker_page_uses_the_same_theme_as_the_file(self):
        self.set_theme("classic")
        self.assertEqual(publish.theme_of(self.s), NAME)
        self.set_theme("cards")
        self.assertIsNone(publish.theme_of(self.s))


if __name__ == "__main__":
    unittest.main()
