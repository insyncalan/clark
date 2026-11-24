"""Row 1225 (template family redesign): AP1 to AP4, the checks the template family owns (the ticket names this file and these test names).

AP1: the Add a section box offers no Needs from you template, and a Needs from you section already stored is not drawn.
AP2: the box offers one Image template (full-image) and not Image with caption (image-caption); a stored Image with caption
     section (store type imagecap) is still drawn, because full-image uses the same store type.
AP3: every template's View is its Edit look without the controls (ViewIsEditWithoutControls, WorkItemsHeads, ViewKeepsTheTitle).
AP4: every template's text is 4.5 to 1 in Edit and View, light and dark (TextContrast).
Run: python3 dev/run_tests.py test_template_family_1225
Needs Chrome (the harness of test_templates): fails, never skips, without it. The widths 1400 and 900 do not change the list.
"""
import contextlib
import json
import unittest

import _tpl_family as F
import test_placement as tp
from test_report_editor import tearDownModule  # noqa: F401
from _paths import ROOT, SRC
from test_server import Running, chrome, wait  # noqa: F401

tp.DEMO = ROOT / "tests" / "fixtures" / "templates_demo.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_PAGE = {}


def page_html():
    if "html" not in _PAGE:
        tp._PAGE.pop("html", None)
        _PAGE["html"] = tp.test_page_html()
        tp._PAGE.pop("html", None)
    return _PAGE["html"]


class TemplateList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_server import Running
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.templates)", self.sid)), "the test bundle ran")

    def templates(self):
        got = self.cdp.js("JSON.stringify(T.templates.TEMPLATES)", self.sid)
        self.assertIsNotNone(got)
        return json.loads(got)

    def test_needs_from_you_is_not_in_the_template_list(self):
        cat = self.templates()
        self.assertEqual([x["id"] for x in cat if x["name"] == "Needs from you" or x["type"] == "needs" or "needs" in x["id"]], [])
        self.assertTrue(len(cat) > 20, "the list is read, not empty")
        # a stored Needs from you section is filtered out before it is drawn (Dashboard.jsx)
        src = (PAGE_SRC / "components" / "Dashboard.jsx").read_text(encoding="utf-8")
        self.assertIn('.filter((s) => s.type !== "needs")', src)

    def test_picker_has_image_and_not_image_with_caption(self):
        cat = self.templates()
        ids = [x["id"] for x in cat]
        self.assertEqual(ids.count("image-caption"), 0)
        self.assertEqual(ids.count("full-image"), 1)
        self.assertEqual([x["name"] for x in cat if x["name"] == "Image with caption"], [])
        # the store type stays offered through Image, so a stored Image with caption section is still found and drawn
        full = next(x for x in cat if x["id"] == "full-image")
        self.assertEqual(full["type"], "imagecap")
        self.assertEqual(self.cdp.js("JSON.stringify(T.templates.find('image-caption'))", self.sid), "null")


# Measured on the 24 templates as built (the same at 1400 and 900, light and dark): template id -> {control: count}
# Each entry is a View control as measured. The audit lists 18 of them as reader tools (gallery 1, work-items 2 rows and Review, gantt, gantt-table 3); the 6 work-items cell-pick pickers (row 1287) are not among them.
# AP3's pin is 0 AUTHORING controls in View (asserted above for every template); what is listed here are reader tools (open, review, zoom, pick), a finding and not an approval.
FINDINGS = {
    "gallery": {"button.tpl-gal-open": 1},
    "work-items": {"tr.wil-k-action": 1, "tr.wil-k-risk": 1, "button.wil-review": 1, "button.cell-pick": 6},      # 2 rows (tabindex 0, role button) + the Review button + 6 in-place pickers (row 1287 puts pickers in View on the Dashboard lists); the 5 column heads are plain th (AP3)
    "gantt": {"button.gt-ib": 7, "button.gt-zf": 1, "button.gt-wd": 1, "button.gt-tflag": 1, "div.gt-b.gt-b-phase": 1, "div.gt-b.gt-b-task": 1},
    "gantt-table": {"button": 3},
}


def counts(names):
    out = {}
    for n in names:
        out[n] = out.get(n, 0) + 1
    return out


class ViewIsEditWithoutControls(F.Family):
    def check(self, width):
        for dark in (False, True):
            with self.subTest(width=width, theme="dark" if dark else "light"):
                got = self.read(width, dark, F.READ_JS)
                self.assertEqual(sorted(got["view"]), sorted(got["edit"]), "the same 24 templates in both")
                self.assertEqual(len(got["view"]), 24)
                for tid, view in got["view"].items():
                    edit = got["edit"][tid]
                    with self.subTest(template=tid):
                        self.assertIsNotNone(view, f"{tid}: View draws the section")
                        self.assertIsNotNone(edit, f"{tid}: Edit draws the section")
                        self.assertEqual(view["type"], edit["type"], f"{tid}: View and Edit draw the same kind of section")
                        self.assertTrue(view["words"], f"{tid}: View shows words")
                        self.assertTrue(any(c.startswith("div.sec-ctl") or c.startswith("button.handle") for c in edit["controls"]), f"{tid}: Edit has its controls")
                        authoring = [c for c in view["controls"] if c.startswith("div.sec-ctl") or c.startswith("button.handle")]
                        self.assertEqual(len(authoring), 0, f"{tid}: AP3: 0 authoring controls (section controls, drag handles) in View")
                        self.assertEqual(counts(view["controls"]), FINDINGS.get(tid, {}), f"{tid}: the only controls in View are the reader tools listed in FINDINGS")

    def test_every_template_view_is_edit_without_controls(self):
        for width in (1400, 900):
            self.check(width)

HEADS_JS = """(ref) => {
  const sec = document.querySelector('.sec[data-id="' + ref + '"]');
  if (!sec) return null;
  const shown = (e) => { for (let n = e; n && n !== document; n = n.parentElement) { const s = getComputedStyle(n); if (s.display === 'none' || s.visibility === 'hidden') return false; } return true; };
  const ths = [...sec.querySelectorAll('.wil-table thead th')].filter(shown);
  return { n: ths.length, drag: ths.filter((t) => t.getAttribute('draggable') === 'true').length, grips: sec.querySelectorAll('.wil-table thead .cgrip').length,
    tab: ths.filter((t) => t.hasAttribute('tabindex')).length, aria: ths.filter((t) => /Drag/.test(t.getAttribute('aria-label') || '')).length };
}"""


class WorkItemsHeads(F.Family):
    """Row 1225 AP3: the Work items list column heads are plain in View and still draggable in Edit."""
    def check(self, width):
        got = self.read(width, False, HEADS_JS)
        view, edit = got["view"]["work-items"], got["edit"]["work-items"]
        self.assertGreater(view["n"], 5, "View draws the heads")
        self.assertEqual((view["drag"], view["grips"], view["tab"], view["aria"]), (0, 0, 0, 0), "View: plain th, no drag, no grip, no tabindex, no drag label")
        self.assertGreater(edit["drag"], 0, "Edit: the heads after Item are draggable")
        self.assertGreater(edit["grips"], 0, "Edit: the heads keep their width grip")
        self.assertGreater(edit["tab"], 0, "Edit: the heads keep their tab stop")
        self.assertGreater(edit["aria"], 0, "Edit: the heads keep their drag label")

    def test_heads_at_1400(self):
        self.check(1400)

    def test_heads_at_900(self):
        self.check(900)


FLOOR = 4.5


class TextContrast(F.Family):
    def check(self, width):
        for dark in (False, True):
            with self.subTest(width=width, theme="dark" if dark else "light"):
                got = self.read(width, dark, F.CONTRAST_JS)
                self.assertEqual(len(got["view"]), 24)
                for mode, by in got.items():
                    for tid, texts in by.items():
                        with self.subTest(mode=mode, template=tid):
                            self.assertTrue(texts, f"{tid} in {mode}: some text was measured")
                            low = [(t["ratio"], t["text"], t["tag"]) for t in texts if t["ratio"] < FLOOR or t["image"]]
                            self.assertEqual(low, [], f"{tid} in {mode}: text under {FLOOR} to 1 or over an image (ratio, text, element)")

    def test_every_template_text_is_4_5_to_1_in_both_themes(self):
        for width in (1400, 900):
            self.check(width)


TITLE_JS = """(ref) => { const h = document.querySelector('.sec[data-id="' + ref + '"] .sec-h'); return h ? h.textContent.replace(/\\s+/g, ' ').trim() : null; }"""


class ViewKeepsTheTitle(F.Family):
    """Row 1225 AP3 (the ticket ruling of 23-11): View shows a section's title as Edit does (the Full width image and the stored Image with caption included)."""
    def test_view_shows_the_title_edit_shows(self):
        for width in (1400, 900):
            got = self.read(width, False, TITLE_JS)
            for tid, edit in got["edit"].items():
                with self.subTest(width=width, template=tid):
                    self.assertTrue(edit, f"{tid}: Edit shows a title")
                    self.assertEqual(got["view"][tid], edit, f"{tid}: View shows the same title")


if __name__ == "__main__":
    unittest.main()
