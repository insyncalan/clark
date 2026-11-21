"""Row 1299 S3 (the Projects overview table on the All projects page, Classic only, read only), in a real browser at 1400 and 900 px, light and dark.
Run: python3 dev/run_tests.py test_projects_overview_ui_1299

Asserted: the page draws the ticket's intro, the issue line ("<n> to look at: ..." with the ruled words, singulars), the two filters with their counts, the seven columns, a row for
each project with Not set / Today / n days ago words; Needs attention keeps only the projects with something to look at; a click on a value opens that setting
for that project (the page, the Affects line, the chosen tab). Cards draws none of it. Chrome is required: these tests fail, never skip, without it."""
import unittest

from clark import page, theme
import _testpage as testpage
from test_publish_dialog import Base
from test_publish_route import Rig
from test_server import chrome
from test_settings_bar import calm
from test_settings_head import address

WIDTHS = (1400, 900)
TWO = [{"code": "PUB", "name": "Harbour Bridge Programme", "open": 3}, {"code": "ABC", "name": "Second Programme", "open": 1}]


def row(code, name, **kw):
    r = {"code": code, "name": name, "asking": False, "brand": "generic", "brand_override": False, "folders": 0, "review_days": 14, "review_override": False,
         "client_folder": "Clients/" + code, "last_backup_days": 0, "attention": []}
    r.update(kw)
    return r


ROWS = [row("PUB", "Harbour Bridge Programme"),
        row("ABC", "Second Programme", asking=True, client_folder="", last_backup_days=3, review_days=30, review_override=True, brand="acme", brand_override=True,
            attention=["no_client_folder", "backup_old", "asking_no_folders"])]


class Service:
    def __init__(self, rows):
        self.rows = rows

    def read(self):
        return 200, {"ok": True, "projects": self.rows, "attention_count": sum(1 for r in self.rows if r["attention"]), "default_brand": "generic", "default_review_days": 14}


class Overview(Base):
    classic = True
    rows = ROWS

    def setUp(self):
        css = theme.css("prototype-2.0")
        layer = (lambda: page.layer_theme(testpage.html(), css)) if self.classic else testpage.html
        self.rig = Rig(self, saved=self.saved, page_html=layer)
        self.rig.httpd.projects = lambda archived=False: TWO
        self.rig.httpd.projects_overview = Service(self.rows)

    def open_settings(self, p, w, mode="light", slug="projects"):
        p.width(w)
        calm(p, mode)
        p.js(f"location.hash = '{address(slug)}'")
        p.until("!!document.querySelector('.set-nav .set-chip[aria-current]') && !!document.querySelector('.set-cards').children.length", "Settings drew")

    def test_O_the_page_draws_the_ruled_words_and_one_row_for_each_project(self):
        for w in WIDTHS:
            for mode in ("light", "dark"):
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    p.until("!!document.querySelector('#projects-overview .ov-table')", "the overview drew")
                    self.assertTrue(p.js("document.querySelector('#projects-overview > p.muted').textContent.startsWith('Every project at a glance. Click a value to open that setting for the project. Grey is the default, amber is an override or something to fix.')"))
                    self.assertEqual(p.js("document.querySelector('#ov-issues').textContent"), "1 to look at: ABC has no client folder; ABC: last backup 3 days ago; ABC: asking is on, no folders")
                    self.assertEqual(p.js("[...document.querySelectorAll('.ov-filters button')].map(b => b.textContent)"), ["All (2)", "Needs attention (1)"])
                    self.assertEqual(p.js("[...document.querySelectorAll('.ov-table th')].map(b => b.textContent)"),
                                     ["Project", "Asking", "Brand", "Read folders", "Review days", "Client folder", "Last backup"])
                    self.assertEqual(p.js("[...document.querySelectorAll('.ov-table tbody tr:nth-child(2) td')].slice(1).map(b => b.textContent)"), ["On", "acme", "0", "30", "Not set", "3 days ago"])
                    self.assertEqual(p.js("[...document.querySelectorAll('.ov-table tbody tr:nth-child(1) td')].slice(-1)[0].textContent"), "Today")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                    amber, grey = p.js("[getComputedStyle(document.querySelector('tr[data-ov-project=ABC] [data-ov=client]')).color, getComputedStyle(document.querySelector('tr[data-ov-project=PUB] [data-ov=client]')).color]")
                    self.assertNotEqual(amber, grey, "amber is not the grey of a default")

    def test_O_needs_attention_keeps_only_the_projects_with_something_to_look_at(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            p.until("!!document.querySelector('#projects-overview .ov-table')", "the overview drew")
            p.js("document.querySelector('[data-ov-filter=attention]').click()")
            p.until("document.querySelectorAll('.ov-table tbody tr').length === 1", "filtered")
            self.assertEqual(p.js("document.querySelector('.ov-table tbody tr').getAttribute('data-ov-project')"), "ABC")
            p.js("document.querySelector('[data-ov-filter=all]').click()")
            p.until("document.querySelectorAll('.ov-table tbody tr').length === 2", "all again")

    def test_O_a_click_on_a_value_opens_that_setting_for_that_project(self):
        for key, slug in (("client", "Brand and publishing"), ("review", "Reports and pages"), ("asking", "ask clark"), ("backup", "Backups")):
            with self.subTest(value=key), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, 1400)
                p.until("!!document.querySelector('#projects-overview .ov-table')", "the overview drew")
                p.js(f"document.querySelector('tr[data-ov-project=ABC] [data-ov={key}]').click()")
                p.until(f"document.querySelector('.set-chip[aria-current]').textContent.trim() === {slug!r}", "the page opened")
                if key != "backup":
                    self.assertEqual(p.js("document.querySelector('.set-affects').textContent.trim()"), "Affects: ABC")


class OverviewClean(Overview):
    rows = [ROWS[0]]

    def test_O_the_page_draws_the_ruled_words_and_one_row_for_each_project(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            p.until("!!document.querySelector('#projects-overview .ov-table')", "the overview drew")
            self.assertFalse(p.js("!!document.querySelector('#ov-issues')"), "nothing to look at: no issue line")
            self.assertEqual(p.js("[...document.querySelectorAll('.ov-filters button')].map(b => b.textContent)"), ["All (1)", "Needs attention (0)"])

    test_O_needs_attention_keeps_only_the_projects_with_something_to_look_at = None
    test_O_a_click_on_a_value_opens_that_setting_for_that_project = None


class OverviewCards(Overview):
    classic = False

    def test_O_the_page_draws_the_ruled_words_and_one_row_for_each_project(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            self.assertFalse(p.js("!!document.querySelector('#projects-overview')"), "Cards draws no overview")

    test_O_needs_attention_keeps_only_the_projects_with_something_to_look_at = None
    test_O_a_click_on_a_value_opens_that_setting_for_that_project = None


if __name__ == "__main__":
    unittest.main()
