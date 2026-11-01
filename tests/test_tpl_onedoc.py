"""#96 G7, One document (store type "onedoc"): the checker and its limits, hostile input, one save one step one Undo, the file
left out until there is a file (words alone stay out; a hidden section too), and the page: the served View and the published file
draw the file and its words alike, and Edit saves the words in one step. Choosing the file is tests/test_section_file_route.py.

Run: python3 dev/run_tests.py test_tpl_onedoc
Needs Chrome (the #33 harness). Fictional data only. Laptop widths 1400 and 900 px, light and dark.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from clark import changes, publish, section_bodies, store as store_module
from clark.section_kinds import base, onedoc
from test_changes import Api
from test_report_editor import EMPTY_BRANDING, Base as PageBase, Pg
from test_server import chrome
from test_tpl_doclinks import MARK, check

FILE = {"name": "Signed SOW.pdf", "rel": "Report files/Signed SOW.pdf", "bytes": 2 * 1024 * 1024}


def doc(**more):
    return json.dumps({"v": 1, **more})


class Checker(unittest.TestCase):
    def refused(self, text, words=None):
        with self.assertRaises(section_bodies.Bad) as e:
            check("onedoc", text)
        self.assertNotIn(MARK, str(e.exception))
        if words:
            self.assertEqual(str(e.exception), words)

    def test_a_good_document_and_words_alone_are_stored(self):
        got = json.loads(check("onedoc", doc(file=FILE, label=" The signed SOW ", text=["Signed on 12-01-2030.", "", "  "])))
        self.assertEqual(got, {"v": 1, "file": FILE, "label": "The signed SOW", "text": ["Signed on 12-01-2030."]})
        self.assertEqual(json.loads(check("onedoc", doc(text=["Words first"]))), {"v": 1, "label": "", "text": ["Words first"]})
        self.assertTrue(onedoc.READY)

    def test_hostile_and_too_long_content_is_refused(self):
        for bad in (doc(file=dict(FILE, rel="Report files/../x.pdf")), doc(file=dict(FILE, name="../x.pdf", rel="Report files/../x.pdf")),
                    doc(file=dict(FILE, bytes=-1)), doc(file="Report files/x.pdf"), doc(text="one line"), doc(text=[MARK] * 7), doc(text=["x" * 601]),
                    doc(label="x" * 121), doc(label=["x"]), json.dumps({"v": 2}), json.dumps([FILE])):
            with self.subTest(bad=bad[:60]):
                self.refused(bad)
        self.refused(doc(text=["a"] * 7), onedoc.BAD_TEXT)
        kept = check("onedoc", doc(file=dict(FILE, href="https://example.org/x"), extra=MARK))
        self.assertNotIn("extra", kept)
        self.assertNotIn("example.org", kept, "a field the section doesn't use is dropped, never stored")

    def test_add_file_replaces_the_file_and_keeps_the_words(self):
        value = json.loads(check("onedoc", doc(file=FILE, label="Keep", text=["Kept"])))
        got = onedoc.add_file(value, {"name": "v3.pdf", "rel": "Report files/v3.pdf", "bytes": 3})
        self.assertEqual(got, {"v": 1, "file": {"name": "v3.pdf", "rel": "Report files/v3.pdf", "bytes": 3}, "label": "Keep", "text": ["Kept"]})
        self.assertEqual(onedoc.add_file(None, FILE)["file"], FILE)

    def test_published_only_once_there_is_a_file(self):
        ctx = base.Context({}, "2030-01-15")
        self.assertIsNone(section_bodies.published("onedoc", {"v": 1, "label": "", "text": ["Words alone"]}, ctx))
        self.assertEqual(section_bodies.published("onedoc", {"v": 1, "file": FILE, "label": "x", "text": ["y"]}, ctx),
                         {"content": {"file": FILE, "label": "x", "text": ["y"]}})


class Saved(Api):
    def test_one_save_one_step_one_undo_and_the_file_keeps_hidden_and_empty_ones_out(self):
        ref = self.ok("new", values={"type": "onedoc", "title": "Fictional document"}, after=None)["ref"]
        status, a = self.change(self.req(changes.UPDATE, id=ref, changes={"body": doc(file=FILE, label="v1")}, place="report"))
        self.assertEqual(status, 200, a)
        status, b = self.change(self.req(changes.UPDATE, id=ref, changes={"body": doc(file=FILE, label="v2", text=["More"])}, place="report"))
        self.assertEqual(status, 200, b)
        self.assertEqual(self.undone(b["apply_id"])[0], 200)
        self.assertEqual(json.loads(self.s.read("report_sections", ref=ref)["body"])["label"], "v1")
        words_only = self.ok("new", values={"type": "onedoc", "title": "Fictional words only"}, after=None)["ref"]
        self.change(self.req(changes.UPDATE, id=words_only, changes={"body": doc(text=[MARK])}, place="report"))
        hidden = self.ok("new", values={"type": "onedoc", "title": "Fictional hidden document"}, after=None)["ref"]
        self.change(self.req(changes.UPDATE, id=hidden, changes={"body": doc(file=FILE, label=MARK)}, place="report"))
        self.ok(changes.UPDATE, id=hidden, changes={"hidden": 1})
        built = publish.build(self.s, "ABC", now="2030-01-15")
        sections = {s["id"]: s for s in built["published"]["sections"]}
        self.assertEqual(sections[ref]["content"]["file"], FILE)
        self.assertNotIn(words_only, sections)
        self.assertNotIn(hidden, sections)
        text = built["body"].decode("utf-8")
        self.assertNotIn(MARK, text)
        self.assertNotIn("Fictional words only", text)


class InThePage(PageBase):
    def _add(self, value, title="Fictional document"):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "onedoc", "title": title, "sort_order": 999})
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", ref, {"body": store_module.check_section_body("onedoc", json.dumps({"v": 1, **value}))})
        return ref

    def drawn(self, p, ref):
        sel = f"[data-id={json.dumps(ref)}]"
        return p.js(f"[document.querySelector('{sel} .tpl-badge').textContent, document.querySelector('{sel} .tpl-name').textContent,"
                    f" document.querySelector('{sel} .tpl-name').getAttribute('href'),"
                    f" [...document.querySelectorAll('{sel} .tpl-od-text')].map(e => e.textContent)]")

    def test_view_draws_the_file_and_words_alone_are_left_out_and_edit_saves_in_one_step(self):
        ref = self._add({"file": FILE, "label": "The signed SOW", "text": ["Signed on 12-01-2030."]})
        alone = self._add({"text": ["Words alone"]}, "Fictional words only")
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('{sel} .tpl-od')", "the document drew")
            self.assertEqual(self.drawn(p, ref), ["PDF", "The signed SOW", None, ["Signed on 12-01-2030."]])
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(alone)}]')"))
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-save]')", "the Edit part drew")
            self.assertEqual(p.js(f"document.querySelector('{sel} [data-add-file]').textContent"), "Choose another file…")
            self.assertTrue(p.js(f"document.querySelector('{sel} [data-save] button').disabled"), "nothing to save yet")
            p.js(f"(() => {{ const t = document.querySelector('{sel} textarea'); t.value = 'Signed on 12-01-2030.\\nSent to the board.';"
                 " t.dispatchEvent(new Event('input', {bubbles: true})); })()")
            p.js(f"document.querySelector('{sel} [data-save] button').click()")
            p.until("!!document.querySelector('[data-undo]')", "saved, with Undo")
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["text"], ["Signed on 12-01-2030.", "Sent to the board."])
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"document.querySelector('{sel} textarea').value === 'Signed on 12-01-2030.'", "Undo put the words back")
            p.js(f"(() => {{ const t = document.querySelector('{sel} textarea'); t.value = Array(8).fill('Line').join('\\n');"
                 " t.dispatchEvent(new Event('input', {bubbles: true})); })()")
            p.js(f"document.querySelector('{sel} [data-save] button').click()")
            p.until(f"!!document.querySelector('{sel} .tpl-problem')", "too many lines is said in words")
            self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-problem').textContent"), onedoc.BAD_TEXT)

    def test_the_published_file_links_the_document_beside_the_report(self):
        ref = self._add({"file": FILE, "label": "", "text": ["Signed on 12-01-2030."]})
        out = tempfile.mkdtemp(prefix="clark-96-g7-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now="2030-01-15", branding=EMPTY_BRANDING)["path"])
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                p = Pg(self, cdp, sid)
                p.until("document.documentElement.dataset.ready === '1'", "the file drew")
                if dark:
                    p.js("document.documentElement.dataset.theme = 'dark'")
                p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-od')", "the document is in the file")
                self.assertEqual(self.drawn(p, ref), ["PDF", "Signed SOW.pdf", "Report%20files/Signed%20SOW.pdf", ["Signed on 12-01-2030."]])
                self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-facts').textContent"), "2 MB")
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), width)


if __name__ == "__main__":
    unittest.main()
