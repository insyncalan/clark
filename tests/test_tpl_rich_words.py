"""Row 1005, the template fields on the one editor: the words on a Link preview card (linkcard), under a One document file (onedoc)
and in a Callout (callout) are written in the editor with the / menu (edit/RichField.jsx), not in a plain box.

Storage, the same for the three: a new field `html` in the section's JSON content, kept through the server's own cleaner
(sanitise.clean_html, the allow-list a text section's body meets) and at most HTML_MAX characters once cleaned; the lines older
clarks wrote (`text`, a callout's `paras`) are still read and drawn as text, and are emptied when the editor saves. The file carries
the html cleaned AGAIN at publish, never the stored text.

Run: python3 dev/run_tests.py test_tpl_rich_words
Needs Chrome (the page tests fail, never skip, without it). Fictional data only.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from clark import changes, publish, sanitise, section_bodies, store as store_module
from clark.section_kinds import base, callout, linkcard, onedoc
from test_changes import Api, KIND
from test_report_editor import EMPTY_BRANDING, Base as PageBase, Pg
from test_server import chrome, wait
from test_tpl_doclinks import MARK, check

FILE = {"name": "Signed SOW.pdf", "rel": "Report files/Signed SOW.pdf", "bytes": 2048}
LINK = "https://example.org/dashboards/pilot"
HOSTILE = (f"<p>Kept words</p><script>alert('{MARK}')</script><img src=x onerror=\"alert('{MARK}')\">"
           f"<a href=\"javascript:alert('{MARK}')\" onclick=\"x()\">bad link</a><div style=\"x\">in a div</div>")
# what the server keeps of it: the cleaner's words, with a line break written as a space (a content field holds none)
CLEAN = sanitise.clean_html(HOSTILE).replace("\n", " ")
# plain lines an older clark saved: markup characters, an ampersand, quotes (a line is one paragraph; a newline is a line of its own)
LEGACY = ["Tom & Jerry's <b>plan</b>", 'He said "stop" <script>x</script>']

KINDS = {
    # type: (content with no words, the field that holds the old lines, the largest html, what makes the section show in a file)
    "linkcard": ({"href": LINK, "title": "Pilot", "site": "Example"}, "text", linkcard.HTML_MAX),
    "onedoc": ({"file": FILE, "label": "The SOW"}, "text", onedoc.HTML_MAX),
    "callout": ({"tone": "info", "title": "Fictional note"}, "paras", callout.HTML_MAX),
}


def body(kind, **more):
    return json.dumps({"v": 1, **KINDS[kind][0], **more})


class Checker(unittest.TestCase):
    def test_html_is_kept_through_the_server_cleaner_for_each_field(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                got = json.loads(check(kind, body(kind, html=HOSTILE)))["html"]
                self.assertEqual(got, CLEAN)
                for bad in ("<script", "onerror", "onclick", "javascript:", "<img", "<div", "style="):
                    self.assertNotIn(bad, got, bad)
                self.assertIn("Kept words", got)
                again = json.loads(check(kind, json.dumps({"v": 1, **KINDS[kind][0], "html": got})))["html"]
                self.assertEqual(again, got, "cleaning it again changes nothing")

    def test_html_with_nothing_to_read_is_no_html_and_a_non_text_html_is_refused(self):
        for kind in KINDS:
            for empty in ("", "<p></p>", "<p><br></p>", "  "):
                with self.subTest(kind=kind, empty=empty):
                    self.assertNotIn("html", json.loads(check(kind, body(kind, html=empty))))
            for bad in (["<p>x</p>"], 5, {"a": 1}):
                with self.subTest(kind=kind, bad=bad), self.assertRaises(section_bodies.Bad) as e:
                    check(kind, body(kind, html=bad))
                self.assertNotIn(MARK, str(e.exception))

    def test_html_over_the_limit_is_refused_in_plain_words_that_never_quote_it(self):
        for kind, (_, _, most) in KINDS.items():
            with self.subTest(kind=kind):
                with self.assertRaises(section_bodies.Bad) as e:
                    check(kind, body(kind, html="<p>" + MARK + "x" * most + "</p>"))
                self.assertNotIn(MARK, str(e.exception))
                self.assertTrue(str(e.exception).endswith("."))
                just = "<p>" + "x" * (most - 7) + "</p>"
                self.assertEqual(len(just), most)
                self.assertEqual(json.loads(check(kind, body(kind, html=just)))["html"], just)

    def test_a_worst_case_body_still_fits_the_section_limit(self):
        """Every character written as six ASCII bytes (canonical JSON) at the largest html, with the other fields full, is not refused for size."""
        for kind, (_, _, most) in KINDS.items():
            with self.subTest(kind=kind):
                html = "<p>" + "é" * (most - 7) + "</p>"
                full = {"title": "é" * 100, "site": "é" * 100, "label": "é" * 100}
                extra = {k: v for k, v in full.items() if k in KINDS[kind][0]}
                text = json.dumps({"v": 1, **KINDS[kind][0], **extra, "html": html})
                self.assertLessEqual(len(section_bodies.canonical(json.loads(check(kind, text)))), section_bodies.LIMITS[kind])

    def test_legacy_plain_lines_still_read_unchanged_with_markup_characters_in_them(self):
        for kind, (_, old, _) in KINDS.items():
            with self.subTest(kind=kind):
                got = json.loads(check(kind, body(kind, **{old: LEGACY})))
                self.assertEqual(got[old], LEGACY, "plain lines are stored as typed: text, never markup")
                self.assertNotIn("html", got)

    def test_published_carries_the_html_and_the_old_lines_as_they_were(self):
        ctx = base.Context({}, "2030-01-15")
        for kind, (_, old, _) in KINDS.items():
            with self.subTest(kind=kind):
                got = section_bodies.published(kind, {"v": 1, **KINDS[kind][0], "tone": "info", "paras": [], "html": "<p>Words</p>"}, ctx)["content"]
                self.assertEqual(got["html"], "<p>Words</p>")
                old_only = section_bodies.published(kind, {"v": 1, **KINDS[kind][0], "tone": "info", old: LEGACY}, ctx)["content"]
                self.assertEqual(old_only[old], LEGACY)
                self.assertNotIn("html", old_only)

    def test_a_callout_with_only_words_in_the_editor_is_not_empty(self):
        ctx = base.Context({}, "2030-01-15")
        self.assertIsNone(section_bodies.published("callout", {"v": 1, "tone": "info", "title": "", "paras": [], "html": ""}, ctx))
        got = section_bodies.published("callout", {"v": 1, "tone": "info", "title": "", "paras": [], "html": "<p>Only words</p>"}, ctx)
        self.assertEqual(got, {"content": {"tone": "info", "title": "", "paras": [], "html": "<p>Only words</p>"}})

    def test_onedoc_add_file_keeps_the_words_the_editor_wrote(self):
        value = json.loads(check("onedoc", body("onedoc", html="<p>Kept</p>")))
        got = onedoc.add_file(value, {"name": "v3.pdf", "rel": "Report files/v3.pdf", "bytes": 3})
        self.assertEqual(got["html"], "<p>Kept</p>")


class Saved(Api):
    def raw(self, ref, text):
        import sqlite3
        con = sqlite3.connect(str(self.path))
        con.execute("UPDATE report_sections SET body = ? WHERE id = ?", (text, ref))
        con.commit()
        con.close()

    def make(self, kind):
        return self.ok("new", values={"type": kind, "title": f"Fictional {kind}"}, after=None)["ref"]

    def test_a_save_is_one_step_one_undo_clean_in_the_store_and_in_the_file(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                ref = self.make(kind)
                status, got = self.change(self.req(changes.UPDATE, id=ref, changes={"body": body(kind, html=HOSTILE)}, place="report"))
                self.assertEqual(status, 200, got)
                stored = self.s.read(KIND, ref=ref)["body"]
                self.assertEqual(json.loads(stored)["html"], CLEAN)
                self.assertNotIn(MARK, stored.replace("Kept", ""))
                built = publish.build(self.s, "ABC", now="2030-01-15")
                sec = {s["id"]: s for s in built["published"]["sections"]}[ref]
                self.assertEqual(sec["content"]["html"], CLEAN)
                status, back = self.undone(got["apply_id"])
                self.assertEqual(status, 200, back)
                self.assertEqual(self.s.read(KIND, ref=ref)["body"], "")
                self.raw(ref, json.dumps({"v": 1, **KINDS[kind][0], "html": HOSTILE}))      # written past the store: a publish checks the content again
                built = publish.build(self.s, "ABC", now="2030-01-15")
                sec = {s["id"]: s for s in built["published"]["sections"]}[ref]
                self.assertEqual(sec["content"]["html"], CLEAN, "a hostile row is cleaned again at publish")
                self.assertNotIn("<script", json.dumps(sec["content"]))
                self.assertNotIn("onerror", json.dumps(sec["content"]))


class InThePage(PageBase):
    def add(self, kind, title="Fictional section", **more):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": kind, "title": title, "sort_order": 999})
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", ref, {"body": store_module.check_section_body(kind, body(kind, **more))})
        return ref

    def raw(self, ref, value):
        """A body written past the store's checker (a hand-edited or older file), as the page reads it."""
        import sqlite3
        con = sqlite3.connect(str(self.store.path))
        con.execute("UPDATE report_sections SET body = ? WHERE id = ?", (json.dumps(value), ref))
        con.commit()
        con.close()

    def words(self, kind):
        return {"linkcard": ".tpl-lc-text", "onedoc": ".tpl-od-text", "callout": ".tpl-callout-p"}[kind]

    def mod(self, p):
        return 4 if p.js("/Mac/.test(navigator.platform)") else 2

    def test_view_draws_legacy_lines_as_text_and_html_as_cleaned_words(self):
        refs = {k: self.add(k, **{KINDS[k][1]: LEGACY}) for k in KINDS}
        with chrome() as cdp:
            p = self.visit(cdp)
            for kind, ref in refs.items():
                sel = f"[data-id={json.dumps(ref)}] {self.words(kind)}"
                p.until(f"!!document.querySelector({json.dumps(sel)})", f"{kind} drew")
                self.assertEqual(p.js(f"[...document.querySelectorAll({json.dumps(sel)})].map(e => e.textContent)"), LEGACY, kind)
                self.assertEqual(p.js(f"document.querySelectorAll({json.dumps(sel + ' b, ' + sel + ' script')}).length"), 0, "a < in an old line is text, not a tag")
        for kind, ref in refs.items():
            self.raw(ref, {"v": 1, **KINDS[kind][0], "html": HOSTILE})
        with chrome() as cdp:
            p = self.visit(cdp)
            for kind, ref in refs.items():
                sec = f"[data-id={json.dumps(ref)}]"
                p.until(f"!!document.querySelector({json.dumps(sec + ' .prose')})", f"{kind} drew its html")
                self.assertEqual(p.js(f"document.querySelector({json.dumps(sec + ' .prose')}).textContent.includes('Kept words')"), True)
                self.assertEqual(p.js(f"document.querySelectorAll({json.dumps(sec + ' script, ' + sec + ' img, ' + sec + ' [onerror], ' + sec + ' [onclick], ' + sec + ' [style]')}).length"), 0, kind)
                self.assertEqual(p.js(f"[...document.querySelectorAll({json.dumps(sec + ' a')})].some(a => /^javascript:/i.test(a.getAttribute('href') || ''))"), False, kind)

    def test_edit_opens_the_one_editor_with_the_old_lines_and_saves_html(self):
        refs = {k: self.add(k, **{KINDS[k][1]: LEGACY}) for k in KINDS}
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for kind, ref in refs.items():
                sec = f"[data-id={json.dumps(ref)}]"
                p.until(f"!!document.querySelector({json.dumps(sec + ' [data-rich=' + kind + ']')})", f"{kind} has a rich field")
                self.assertEqual(p.js(f"document.querySelectorAll({json.dumps(sec + ' textarea')}).length"), 0, "no plain box for the words")
                p.js(f"document.querySelector({json.dumps(sec + ' [data-rich]')}).click()")
                p.until(f"!!document.querySelector({json.dumps(sec + ' .ProseMirror')})", f"{kind} opened the editor")
                p.until(f"document.activeElement && document.activeElement.classList.contains('ProseMirror')", "the editor has the focus")
                self.assertEqual(p.js(f"!!document.querySelector({json.dumps(sec + ' .ProseMirror')}).cxed"), True, "it is clarkEditor")
                self.assertIn("Tom & Jerry's <b>plan</b>", p.js(f"document.querySelector({json.dumps(sec + ' .ProseMirror')}).textContent"))
                p.js(f"document.querySelector({json.dumps(sec + ' .ProseMirror')}).cxed.editor.commands.insertContent('<h2>ZQ-NEW</h2>'); true")
                p.key("Enter", self.mod(p), code="Enter", vk=13)
                self.assertTrue(wait(lambda: "ZQ-NEW" in self.store.read("report_sections", ref=ref)["body"], 15), kind)
                got = json.loads(self.store.read("report_sections", ref=ref)["body"])
                self.assertEqual(got["html"], sanitise.clean_html(got["html"]), "clean in the store")
                self.assertIn("<h2>", got["html"])
                self.assertIn("&lt;b&gt;plan&lt;/b&gt;", got["html"], "the old line's < is escaped text in the html")
                self.assertEqual(got.get(KINDS[kind][1], []), [], "the old lines are emptied once the editor wrote them")
                p.until(f"!document.querySelector({json.dumps(sec + ' .ProseMirror')})", "the field closed")

    def test_the_published_file_draws_the_html_and_the_old_lines(self):
        refs = {"linkcard": self.add("linkcard", html="<p>Kept <strong>words</strong></p>"),
                "onedoc": self.add("onedoc", text=LEGACY), "callout": self.add("callout", html="<ul><li>One</li></ul>")}
        out = tempfile.mkdtemp(prefix="clark-1005-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now="2030-01-15", branding=EMPTY_BRANDING)["path"])
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
            p = Pg(self, cdp, sid)
            p.until("document.documentElement.dataset.ready === '1'", "the file drew")
            sec = lambda k: f"[data-id={json.dumps(refs[k])}]"  # noqa: E731
            self.assertEqual(p.js(f"document.querySelector({json.dumps(sec('linkcard') + ' .tpl-lc-text strong')}).textContent"), "words")
            self.assertEqual(p.js(f"document.querySelector({json.dumps(sec('callout') + ' .tpl-callout-p li')}).textContent"), "One")
            self.assertEqual(p.js(f"[...document.querySelectorAll({json.dumps(sec('onedoc') + ' .tpl-od-text')})].map(e => e.textContent)"), LEGACY)
            self.assertEqual(p.js(f"document.querySelectorAll({json.dumps(sec('onedoc') + ' .tpl-od-text b')}).length"), 0)


if __name__ == "__main__":
    unittest.main()
