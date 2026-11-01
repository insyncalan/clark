"""#96 G7, Documents and links (store type "doclinks"): the content's checker and its limits, hostile input, one save one step one
Undo, what the published file carries (a hidden or empty section is left out; a marker scan of the file), and the page: the
served View and the published file draw the same list, Edit adds and removes a link in one step each, and refuses a bad link
in words before anything is sent. The file part (Add a file) is tests/test_section_file_route.py.

Run: python3 dev/run_tests.py test_tpl_doclinks
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only. Laptop widths 1400 and 900 px,
light and dark.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC
from clark import changes, publish, section_bodies, store as store_module
from clark.section_kinds import base, doclinks
from test_changes import Api
from test_report_editor import EMPTY_BRANDING, Base as PageBase, Pg
from test_server import chrome

MARK = "Fictional marker kept out"        # planted where it must never reach a file
RULES = store_module.BODY_RULES


def body(items, **more):
    return json.dumps({"v": 1, "items": items, **more})


def a_file(name="Plan v2.pdf", size=340 * 1024, **more):
    return {"kind": "file", "name": name, "rel": f"Report files/{name}", "bytes": size, **more}


def a_link(href="https://example.org/plan", label="The plan", **more):
    return {"kind": "link", "href": href, "label": label, **more}


def check(kind, text):
    return section_bodies.check(kind, text, RULES)


class Checker(unittest.TestCase):
    def refused(self, kind, text, words=None):
        with self.assertRaises(section_bodies.Bad) as e:
            check(kind, text)
        self.assertNotIn(MARK, str(e.exception), "a refusal never quotes the content")
        if words:
            self.assertEqual(str(e.exception), words)
        return str(e.exception)

    def test_a_good_list_is_stored_as_canonical_text_with_words_trimmed(self):
        got = check("doclinks", body([a_link(label="  The plan  "), a_file(label="")]))
        self.assertEqual(json.loads(got), {"v": 1, "items": [
            {"kind": "link", "href": "https://example.org/plan", "label": "The plan"},
            {"kind": "file", "name": "Plan v2.pdf", "rel": "Report files/Plan v2.pdf", "bytes": 340 * 1024, "label": ""}]})
        self.assertEqual(check("doclinks", got), got, "saving it again changes nothing")
        self.assertEqual(json.loads(check("doclinks", body([a_link(href="mailto:team@example.org", label="")])))["items"][0]["href"],
                         "mailto:team@example.org")
        self.assertEqual(check("doclinks", ""), "", "no content is no content")
        self.assertTrue(doclinks.READY)

    def test_only_https_and_mailto_links_with_nothing_hidden_in_them(self):
        for href in ("javascript:alert(1)", "JaVaScRiPt:alert(1)", "http://example.org", "data:text/html,x", "//example.org",
                     "relative/page.html", "Report files/Plan.pdf", "#top", "https://", "https:///x", "https://@example.org",
                     "https://user:pass@example.org/", "https://.example.org", "https://example.org/a b", "https://example.org/\\x",
                     "mailto:", "ftp://example.org", "https://example.org/" + "a" * 2000, "", 7, None, True, ["https://example.org"]):
            with self.subTest(href=href):
                self.refused("doclinks", body([a_link(href=href)]))
        self.refused("doclinks", body([a_link(href="https://exa‮mple.org")]))      # a direction-changing character (generic wall)
        self.refused("doclinks", body([a_link(href="https://exa\tmple.org")]))

    def test_a_file_is_one_safe_name_in_report_files_with_a_true_size(self):
        bad = [dict(a_file(), rel="Report files/other.pdf"), dict(a_file(), rel="../Report files/Plan v2.pdf"),
               a_file(name="../secret.txt"), a_file(name="sub/a.pdf"), a_file(name="a\\b.pdf"), a_file(name="C:a.pdf"),
               a_file(name=".hidden"), a_file(name="trailing."), a_file(name="trailing "), a_file(name=" lead"), a_file(name=""),
               a_file(name="a" * 121), a_file(name='a"b.pdf'), a_file(name="a?.pdf"), a_file(name="a|b.pdf"),
               a_file(size=-1), a_file(size=True), a_file(size="12"), a_file(size=2 ** 41), a_file(size=None),
               {"kind": "file", "name": "a.pdf", "bytes": 1}, {"kind": "file", "rel": "Report files/a.pdf", "bytes": 1}]
        for item in bad:
            with self.subTest(item=item):
                self.refused("doclinks", body([item]))
        self.assertEqual(json.loads(check("doclinks", body([a_file(name="a#b (2).docx")])))["items"][0]["name"], "a#b (2).docx")

    def test_the_shape_is_fixed_and_nothing_unknown_is_stored(self):
        self.refused("doclinks", json.dumps({"v": 2, "items": []}), doclinks.BAD_VERSION)
        self.refused("doclinks", json.dumps({"v": True, "items": []}), doclinks.BAD_VERSION)
        self.refused("doclinks", json.dumps({"items": []}))
        for extra in (json.dumps({"v": 1, "items": [], "script": MARK}), body([dict(a_link(), onclick=MARK)]),
                      body([dict(a_file(), href="https://example.org/" + MARK.replace(" ", "-"))])):
            self.assertNotIn(MARK.split()[1], check("doclinks", extra), "a field the section doesn't use is dropped, never stored")
        self.refused("doclinks", body([{"kind": "picture", "src": "x"}]), doclinks.BAD_KIND)
        self.refused("doclinks", body(["https://example.org"]), doclinks.BAD_KIND)
        self.refused("doclinks", json.dumps({"v": 1, "items": {"0": a_link()}}))
        self.refused("doclinks", json.dumps([a_link()]))
        self.refused("doclinks", body([a_link(label=MARK * 10)]), doclinks.BAD_LABEL)
        self.refused("doclinks", body([a_link(label=12)]), doclinks.BAD_LABEL)

    def test_at_most_twenty_entries_and_the_limit_fits_the_change_route(self):
        self.assertEqual(len(json.loads(check("doclinks", body([a_link()] * 20)))["items"]), 20)
        self.refused("doclinks", body([a_link()] * 21), doclinks.TOO_MANY)
        self.refused("doclinks", body([a_link(href="https://example.org/" + "p" * 1900, label="w" * 120)] * 20), section_bodies.TOO_BIG)
        self.assertLessEqual(doclinks.LIMIT + 8 * 1024, 72 * 1024, "a full section is sent through /api/change")

    def test_add_file_puts_the_server_s_entry_at_the_end_and_refuses_a_full_list(self):
        value = json.loads(check("doclinks", body([a_link()])))
        got = doclinks.add_file(value, {"name": "Budget.xlsx", "rel": "Report files/Budget.xlsx", "bytes": 10})
        self.assertEqual(got["items"][-1], {"kind": "file", "name": "Budget.xlsx", "rel": "Report files/Budget.xlsx", "bytes": 10, "label": ""})
        self.assertEqual(doclinks.add_file(None, {"name": "a.pdf", "rel": "Report files/a.pdf", "bytes": 1})["items"][0]["name"], "a.pdf")
        with self.assertRaises(section_bodies.Bad):
            doclinks.add_file({"v": 1, "items": [a_link()] * 20}, {"name": "a.pdf", "rel": "Report files/a.pdf", "bytes": 1})
        with self.assertRaises(section_bodies.Bad):
            doclinks.add_file(None, {"name": "../a.pdf", "rel": "Report files/../a.pdf", "bytes": 1})

    def test_published_picks_the_fields_and_leaves_an_empty_list_out(self):
        ctx = base.Context({}, "2030-01-15")
        value = json.loads(check("doclinks", body([a_link(), a_file()])))
        self.assertEqual(section_bodies.published("doclinks", value, ctx), {"content": {"items": value["items"]}})
        self.assertIsNone(section_bodies.published("doclinks", {"v": 1, "items": []}, ctx))


class Saved(Api):
    def make(self, title="Fictional documents", **more):
        return self.ok("new", values={"type": "doclinks", "title": title}, after=None, **more)["ref"]

    def save(self, ref, text):
        return self.change(self.req(changes.UPDATE, id=ref, changes={"body": text}, place="report"))

    def test_one_save_is_one_step_and_one_undo_puts_the_list_back(self):
        ref = self.make()
        status, first = self.save(ref, body([a_link()]))
        self.assertEqual(status, 200, first)
        status, second = self.save(ref, body([a_link(), a_link(href="https://example.org/two", label="Two")]))
        self.assertEqual(status, 200, second)
        self.assertNotEqual(first["apply_id"], second["apply_id"])
        rows = self.s.con.execute("SELECT field FROM change_log WHERE apply_id = ? AND field != 'updated_at'", (second["apply_id"],)).fetchall()
        self.assertEqual([r["field"] for r in rows], ["body"], "one field in one step")
        status, _ = self.undone(second["apply_id"])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(self.s.read("report_sections", ref=ref)["body"])["items"], [a_link()])

    def test_a_refused_save_writes_nothing_and_says_why_without_quoting(self):
        ref = self.make()
        before = self.snapshot()
        status, got = self.save(ref, body([a_link(href="javascript:" + MARK)]))
        self.assertEqual(status, 400)
        self.assertEqual(got["message"], doclinks.BAD_LINK)
        self.assertNotIn(MARK, json.dumps(got))
        self.assertEqual(self.snapshot(), before)

    def test_the_file_carries_the_list_and_a_hidden_or_empty_section_is_left_out(self):
        shown = self.make("Fictional papers")
        self.save(shown, body([a_link(), a_file()]))
        hidden = self.make("Fictional hidden papers")
        self.save(hidden, body([a_link(label=MARK)]))
        self.ok(changes.UPDATE, id=hidden, changes={"hidden": 1})
        empty = self.make("Fictional empty papers")
        self.save(empty, body([]))
        never = self.make("Fictional never filled")
        built = publish.build(self.s, "ABC", now="2030-01-15")
        sections = {s["id"]: s for s in built["published"]["sections"]}
        self.assertEqual(sections[shown]["content"]["items"][0]["href"], "https://example.org/plan")
        self.assertEqual(sections[shown]["content"]["items"][1]["rel"], "Report files/Plan v2.pdf")
        for ref in (hidden, empty, never):
            self.assertNotIn(ref, sections)
        text = built["body"].decode("utf-8")
        self.assertNotIn(MARK, text)
        for title in ("Fictional hidden papers", "Fictional empty papers", "Fictional never filled"):
            self.assertNotIn(title, text)
        self.assertNotIn("body", sections[shown], "the stored text is never in the file")


class InThePage(PageBase):
    """The served View and the file draw the same entries; Edit adds and removes a link, one step each."""

    def add(self, items, title="Fictional papers", kind="doclinks"):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": kind, "title": title, "sort_order": 999})
        if items is not None:
            with self.store.step("dashboard", USER) as st:
                st.update("report_sections", ref, {"body": store_module.check_section_body(kind, body(items))})
        return ref

    def entries(self, p, ref):
        return p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] .tpl-dl-i')].map(li => "
                    "[li.querySelector('.tpl-badge').textContent, li.querySelector('.tpl-name').textContent, "
                    "li.querySelector('.tpl-name').tagName, li.querySelector('.tpl-name').getAttribute('href')])")

    def test_view_draws_the_list_and_an_empty_one_is_left_out(self):
        ref = self.add([a_link(), a_link(href="mailto:team@example.org", label=""), a_file()])
        empty = self.add([], "Fictional empty papers")
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-dl')", "the list drew")
            self.assertEqual(self.entries(p, ref), [
                ["Link", "The plan", "A", "https://example.org/plan"],
                ["Link", "team@example.org", "A", "mailto:team@example.org"],
                ["PDF", "Plan v2.pdf", "SPAN", None]], "the page clark serves names a file without linking it")
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(empty)}]')"), "an empty list is left out of View")
            self.assertEqual(p.js(f"document.querySelectorAll('[data-id={json.dumps(ref)}] input, [data-id={json.dumps(ref)}] button').length"), 0,
                             "View is read only")

    def test_edit_adds_a_link_in_one_step_and_undo_takes_it_back(self):
        ref = self.add([a_link()])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-add-link]')", "the Edit part drew")
            self.set_value(p, f"{sel} [data-add-link] input[type=text]", "https://example.org/budget", 0)
            self.set_value(p, f"{sel} [data-add-link] input[type=text]", "Budget", 1)
            p.js(f"document.querySelector('{sel} [data-add-link] button[type=submit]').click()")
            p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length === 2", "the new link is drawn")
            stored = json.loads(self.store.read("report_sections", ref=ref)["body"])["items"]
            self.assertEqual(stored[-1], {"kind": "link", "href": "https://example.org/budget", "label": "Budget"})
            p.until("!!document.querySelector('[data-undo]')", "the toast offers Undo")
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length === 1", "Undo took it back")
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["items"], [a_link()])
            p.js(f"document.querySelector('{sel} .tpl-remove').click()")
            p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length === 0", "Remove took it off")
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["items"], [])

    def test_edit_refuses_a_bad_link_in_words_and_sends_nothing(self):
        ref = self.add([])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-add-link]')", "the Edit part drew")
            self.assertIn("stays out of the published page", p.js(f"document.querySelector('{sel} .tpl-empty').textContent"))
            sent = len(self.sent)
            for bad in ("javascript:alert(1)", "http://example.org", "example.org"):
                self.set_value(p, f"{sel} [data-add-link] input[type=text]", bad, 0)
                p.js(f"document.querySelector('{sel} [data-add-link] button[type=submit]').click()")
                p.until(f"!!document.querySelector('{sel} .tpl-problem')", "the refusal is shown")
                self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-problem').textContent"), doclinks.BAD_LINK)
            self.assertEqual(len(self.sent), sent, "nothing was sent")
            self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-problem').getAttribute('role')"), "alert")
            p.js(f"document.querySelector('{sel} [data-add-file]').focus()")
            self.assertTrue(p.js("document.activeElement.hasAttribute('data-add-file')"), "Add a file takes focus from the keyboard")

    @staticmethod
    def set_value(p, selector, value, index=0):
        p.js(f"(() => {{ const el = document.querySelectorAll({json.dumps(selector)})[{index}]; el.focus(); el.value = {json.dumps(value)};"
             " el.dispatchEvent(new Event('input', {bubbles: true})); })()")


class Published(PageBase):
    """The published file draws the list from its own data block: a file as a link relative to the report, a link to its page."""

    def test_the_file_draws_the_list_at_both_widths_light_and_dark(self):
        ref = InThePage.add(self, [a_link(), a_file(name="Plan v2#1.pdf", label="The plan, signed")])
        hidden = InThePage.add(self, [a_link(label=MARK)], "Fictional hidden papers")
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", hidden, {"hidden": 1})
        out = tempfile.mkdtemp(prefix="clark-96-g7-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        done = publish.publish(self.store, "ABC", out, by_user=USER, now="2030-01-15", branding=EMPTY_BRANDING)
        path = Path(done["path"])
        text = path.read_text(encoding="utf-8")
        self.assertNotIn(MARK, text)
        self.assertNotIn("Fictional hidden papers", text)
        for width, dark in ((1400, False), (900, True), (900, False), (1400, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                p = Pg(self, cdp, sid)
                p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
                if dark:
                    p.js("document.documentElement.dataset.theme = 'dark'")
                p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-dl')", "the list is in the file")
                self.assertEqual(InThePage.entries(self, p, ref), [
                    ["Link", "The plan", "A", "https://example.org/plan"],
                    ["PDF", "The plan, signed", "A", "Report%20files/Plan%20v2%231.pdf"]])
                self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-facts').textContent"), "example.org")
                self.assertEqual(p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] .tpl-facts')][1].textContent"),
                                 "Plan v2#1.pdf · 340 KB")
                self.assertEqual(p.js("document.querySelectorAll('.tpl-dl input, .tpl-dl button, .tpl-form').length"), 0)
                self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(hidden)}]')"))
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), width, "no sideways scroll")
                rel = p.js(f"document.querySelector('[data-id={json.dumps(ref)}] a.tpl-name').rel")
                self.assertEqual(rel, "noopener noreferrer")

    def test_the_published_page_carries_no_edit_part(self):
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for words in ("Add a file", "api/section-file", "tpl-form", "Choose the file", "Save card"):
            self.assertNotIn(words, view)


if __name__ == "__main__":
    unittest.main()
