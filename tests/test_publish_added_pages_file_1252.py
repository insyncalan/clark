"""Row 1252 main-fix: a PUBLISHED file draws an added page. publish.py writes the client's pages as data.pages and their tabs as page:<id>;
the file's loader used to drop those tabs and never gave the view data.added_pages, so #page:<id> drew the Dashboard.
Real publish (publish.build of a demo store), Chrome opens the built file at 1400 and 900, light and dark (Classic theme only).
An internal page and a page hidden from the menu are in neither the file nor the bar. Fictional data only.

Run: python3 dev/run_tests.py test_publish_added_pages_file_1252
"""
import json
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import changes, publish
from test_publish import chrome, opened, wait  # noqa: E402
import test_server  # noqa: E402,F401  (browser tier)

DAY = "2026-10-28"
SECTIONS = json.dumps([{"id": "s1", "type": "text", "title": "Notes head", "body": "<p>Hello from the notes page</p>"},
                       {"id": "s2", "type": "text", "title": "Second head", "body": "<p>Two words more</p>"}])
TEXT = "document.body.innerText"


class FilePage(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)

    def page(self, name, sections=SECTIONS, **values):
        status, body = self.change({"project": "ABC", "kind": "added_pages", "op": "new",
                                    "values": {"name": name, "starter": "blank", "sections": sections, **values}})
        self.assertEqual(status, 200, body)
        return self.s.read("added_pages", project="ABC")[-1]["id"]

    def built(self, tmp):
        path = Path(tmp) / "f.html"
        path.write_bytes(publish.build(self.s, "ABC", DAY, None)["body"])
        return path

    def open(self, cdp, path, width, scheme, frag=""):
        sid = opened(cdp, path.as_uri() + frag, width)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
        if scheme == "dark":
            cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
        return sid


class Drawn(FilePage):
    def test_the_built_file_shows_the_added_page_tab_words_and_route(self):
        pid = self.page("Notes", client=1)
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                    path = self.built(tmp)
                    sid = self.open(cdp, path, width, scheme)
                    tabs = cdp.js("[...document.querySelectorAll('[role=tab]')].map((e) => e.dataset.view)", sid)
                    self.assertIn("page:" + pid, tabs, f"the page's tab is in the bar: {tabs}")
                    self.assertEqual(tabs[-1], "page:" + pid, f"the tab is after the built-in tabs: {tabs}")
                    self.assertEqual(cdp.js(f"document.querySelector('[data-view=\"page:{pid}\"]').textContent.trim()", sid), "Notes", "the tab carries the page's name")
                    cdp.js(f"document.querySelector('[data-view=\"page:{pid}\"]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js(f"location.hash.includes('page:{pid}')", sid)))
                    self.assertTrue(wait(lambda: "Notes head" in cdp.js(TEXT, sid)), "the heading is drawn")
                    text = cdp.js(TEXT, sid)
                    for word in ("Notes head", "Hello from the notes page", "Second head", "Two words more"):
                        self.assertIn(word, text)
                    self.assertEqual(cdp.js("[...document.querySelectorAll('#main [data-id], section[data-id]')].map((e) => e.dataset.id).filter((d) => d.startsWith('" + pid + "'))", sid),
                                     [pid + "-s1", pid + "-s2"], "each section id is the page id, a dash, the section id, once (as the served page draws it)")
                    # the address itself: a fresh open of #page:<id> draws the page, not the Dashboard
                    sid = self.open(cdp, path, width, scheme, "#page:" + pid)
                    self.assertTrue(wait(lambda: "Notes head" in cdp.js(TEXT, sid)), "#page:<id> draws the added page")
                    self.assertEqual(cdp.js(f"document.querySelector('[data-view=\"page:{pid}\"]').getAttribute('aria-selected')", sid), "true")
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no sideways scroll")


class Absent(FilePage):
    def test_an_internal_page_and_a_hidden_page_are_not_in_the_file_or_the_bar(self):
        shown = self.page("Notes", client=1)
        internal = self.page("Internal", sections=json.dumps([{"id": "s1", "type": "text", "title": "Internal head", "body": "<p>Team only words</p>"}]), client=0)
        hidden = self.page("Hidden", sections=json.dumps([{"id": "s1", "type": "text", "title": "Hidden head", "body": "<p>Menu hidden words</p>"}]), client=1, hidden=1)
        with tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
            path = self.built(tmp)
            raw = path.read_text(encoding="utf-8")
            for gone in ("Internal head", "Team only words", "Hidden head", "Menu hidden words", internal, hidden):
                self.assertNotIn(gone, raw, gone)
            sid = self.open(cdp, path, 1400, "light")
            tabs = cdp.js("[...document.querySelectorAll('[role=tab]')].map((e) => e.dataset.view)", sid)
            self.assertIn("page:" + shown, tabs)
            self.assertNotIn("page:" + internal, tabs)
            self.assertNotIn("page:" + hidden, tabs)
            for pid in (internal, hidden):                       # their addresses draw no such page
                sid = self.open(cdp, path, 1400, "light", "#page:" + pid)
                self.assertNotIn("Team only words", cdp.js(TEXT, sid))
                self.assertNotIn("Menu hidden words", cdp.js(TEXT, sid))


if __name__ == "__main__":
    unittest.main()
