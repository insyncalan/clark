"""#96 G7, Link preview (store type "linkcard"): a typed card, never a live embed. The checker and its limits, hostile input, one
save one step one Undo, the file left out until there is a link (a hidden section too), clark never fetching the page (no
network in the module, the build or the page part), and the page: the served View and the published file draw the same card, and
Edit saves the card in one step and refuses a bad link in words.

Run: python3 dev/run_tests.py test_tpl_linkcard
Needs Chrome (the #33 harness). Fictional data only. Laptop widths 1400 and 900 px, light and dark.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC
from clark import changes, publish, section_bodies, store as store_module
from clark.section_kinds import base, doclinks, linkcard
from test_changes import Api
from test_report_editor import EMPTY_BRANDING, Base as PageBase, Pg
from test_server import chrome
from test_tpl_doclinks import MARK, check

CARD = {"href": "https://example.org/dashboards/pilot", "title": "Pilot dashboard", "site": "Example Analytics",
        "text": ["Updated every Monday."]}


def card(**more):
    return json.dumps({"v": 1, **more})


class Checker(unittest.TestCase):
    def refused(self, text, words=None):
        with self.assertRaises(section_bodies.Bad) as e:
            check("linkcard", text)
        self.assertNotIn(MARK, str(e.exception))
        if words:
            self.assertEqual(str(e.exception), words)

    def test_a_good_card_and_a_card_without_a_link_yet(self):
        self.assertEqual(json.loads(check("linkcard", card(**CARD))), {"v": 1, **CARD})
        self.assertEqual(json.loads(check("linkcard", card(title=" Soon ", href=""))), {"v": 1, "title": "Soon", "site": "", "text": []})
        self.assertTrue(linkcard.READY)

    def test_hostile_and_too_long_cards_are_refused(self):
        for href in ("javascript:alert(1)", "http://example.org", "data:text/html,x", "//example.org", "Report files/x.pdf", "#x"):
            with self.subTest(href=href):
                self.refused(card(**dict(CARD, href=href)), doclinks.BAD_LINK)
        for bad in (card(**dict(CARD, title="x" * 121)), card(**dict(CARD, site=["x"])), card(**dict(CARD, text=["x"] * 4)),
                    card(**dict(CARD, text=["x" * 401])), json.dumps({"v": 2, **CARD}), json.dumps([CARD])):
            with self.subTest(bad=bad[:60]):
                self.refused(bad)
        self.refused(card(**dict(CARD, text=["x"] * 4)), linkcard.BAD_TEXT)
        kept = json.loads(check("linkcard", card(**dict(CARD, image="data:image/png;base64,iVBO", script=MARK))))
        self.assertEqual(kept, {"v": 1, **CARD}, "a field the card doesn't use (a picture waits for the media route) is dropped")

    def test_published_only_once_there_is_a_link(self):
        ctx = base.Context({}, "2030-01-15")
        self.assertIsNone(section_bodies.published("linkcard", {"v": 1, "title": "Soon", "site": "", "text": []}, ctx))
        self.assertEqual(section_bodies.published("linkcard", {"v": 1, **CARD}, ctx), {"content": CARD})

    def test_nothing_here_can_fetch_a_page(self):
        """A card, not a live embed: the module, its rules and its page parts name no way to reach the network."""
        sources = [SRC / "clark" / "section_kinds" / "linkcard.py", SRC / "clark" / "section_kinds" / "doclinks.py",
                   SRC / "clark" / "page" / "src" / "templates" / "LinkCard.jsx", SRC / "clark" / "page" / "src" / "templates" / "files.js",
                   SRC / "clark" / "page" / "src" / "edit" / "templates" / "LinkCard.jsx"]
        for f in sources:
            text = f.read_text(encoding="utf-8")
            for word in ("urllib", "http.client", "socket", "requests", "fetch(", "XMLHttpRequest", "<iframe", "<img"):
                self.assertNotIn(word, text, (f.name, word))


class Saved(Api):
    def test_one_save_one_step_one_undo_and_hidden_or_linkless_cards_stay_out(self):
        ref = self.ok("new", values={"type": "linkcard", "title": "Fictional card"}, after=None)["ref"]
        status, a = self.change(self.req(changes.UPDATE, id=ref, changes={"body": card(**CARD)}, place="report"))
        self.assertEqual(status, 200, a)
        status, b = self.change(self.req(changes.UPDATE, id=ref, changes={"body": card(**dict(CARD, title="Renamed"))}, place="report"))
        self.assertEqual(status, 200, b)
        self.assertEqual(self.undone(b["apply_id"])[0], 200)
        self.assertEqual(json.loads(self.s.read("report_sections", ref=ref)["body"])["title"], "Pilot dashboard")
        linkless = self.ok("new", values={"type": "linkcard", "title": "Fictional linkless"}, after=None)["ref"]
        self.change(self.req(changes.UPDATE, id=linkless, changes={"body": card(title=MARK)}, place="report"))
        hidden = self.ok("new", values={"type": "linkcard", "title": "Fictional hidden card"}, after=None)["ref"]
        self.change(self.req(changes.UPDATE, id=hidden, changes={"body": card(**dict(CARD, text=[MARK]))}, place="report"))
        self.ok(changes.UPDATE, id=hidden, changes={"hidden": 1})
        built = publish.build(self.s, "ABC", now="2030-01-15")
        sections = {s["id"]: s for s in built["published"]["sections"]}
        self.assertEqual(sections[ref]["content"], CARD)
        self.assertNotIn(linkless, sections)
        self.assertNotIn(hidden, sections)
        self.assertNotIn(MARK, built["body"].decode("utf-8"))


class InThePage(PageBase):
    def add(self, value, title="Fictional card"):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "linkcard", "title": title, "sort_order": 999})
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", ref, {"body": store_module.check_section_body("linkcard", card(**value))})
        return ref

    def drawn(self, p, ref):
        sel = f"[data-id={json.dumps(ref)}]"
        return p.js(f"[document.querySelector('{sel} .tpl-lc-site').textContent, document.querySelector('{sel} .tpl-lc-title a').textContent,"
                    f" document.querySelector('{sel} .tpl-lc-title a').getAttribute('href'),"
                    f" [...document.querySelectorAll('{sel} .tpl-lc-text')].map(e => e.textContent)]")

    def put(self, p, selector, value):
        p.js(f"(() => {{ const el = document.querySelector({json.dumps(selector)}); el.value = {json.dumps(value)};"
             " el.dispatchEvent(new Event('input', {bubbles: true})); })()")

    def test_view_draws_the_card_and_edit_saves_it_in_one_step(self):
        ref = self.add(CARD)
        linkless = self.add({"title": "Soon"}, "Fictional linkless")
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('{sel} .tpl-lc')", "the card drew")
            self.assertEqual(self.drawn(p, ref), ["Example Analytics", "Pilot dashboard", CARD["href"], ["Updated every Monday."]])
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(linkless)}]')"), "no link: left out of View")
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-save]')", "the Edit part drew")
            self.put(p, f"{sel} input[id$=-title]", "Pilot dashboard, week 3")
            self.put(p, f"{sel} input[id$=-site]", "")
            p.js(f"document.querySelector('{sel} [data-save] button').click()")
            p.until("!!document.querySelector('[data-undo]')", "saved, with Undo")
            stored = json.loads(self.store.read("report_sections", ref=ref)["body"])
            self.assertEqual((stored["title"], stored["site"]), ("Pilot dashboard, week 3", ""))
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"document.querySelector('{sel} input[id$=-title]').value === 'Pilot dashboard'", "Undo put the card back")
            sent = len(self.sent)
            self.put(p, f"{sel} input[id$=-href]", "javascript:alert(1)")
            p.js(f"document.querySelector('{sel} [data-save] button').click()")
            p.until(f"!!document.querySelector('{sel} .tpl-problem')", "the refusal is in words")
            self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-problem').textContent"), doclinks.BAD_LINK)
            self.assertEqual(len(self.sent), sent, "nothing was sent")
            labels = p.js(f"[...document.querySelectorAll('{sel} .tpl-form label')].map(l => !!document.getElementById(l.htmlFor))")
            self.assertTrue(labels and all(labels), "every field has its label")

    def test_the_published_file_draws_the_card(self):
        ref = self.add(dict(CARD, site=""))
        out = tempfile.mkdtemp(prefix="clark-96-g7-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now="2030-01-15", branding=EMPTY_BRANDING)["path"])
        for width, dark in ((1400, True), (900, False)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                p = Pg(self, cdp, sid)
                p.until("document.documentElement.dataset.ready === '1'", "the file drew")
                if dark:
                    p.js("document.documentElement.dataset.theme = 'dark'")
                p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-lc')", "the card is in the file")
                self.assertEqual(self.drawn(p, ref), ["example.org", "Pilot dashboard", CARD["href"], ["Updated every Monday."]],
                                 "without a site line the card shows the site from the link")
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), width)


if __name__ == "__main__":
    unittest.main()
