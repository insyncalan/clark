"""Row 1214: the preview a drag draws, set by the signals alone (edit/drag.js, a later step, will set them).

With dragList set the Dashboard draws that list, the dragged section is the drag-slot (dashed, its content hidden), the others
stay and the dragged one's id is drag-from while no place is shown; with dragList unset the stored order is drawn; leave() clears
both; sections that changed place glide (components/glide.js) and none do when motion is reduced.
Run: python3 dev/run_tests.py test_drag_preview_1214. The real Dashboard and Section in headless Chrome, at 1400 and 900 px.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "drag_preview_demo.jsx"
CSS = SRC / "clark" / "page" / "shell.css"


def sec(id, title):
    return {"id": id, "type": "text", "title": title, "body": f"<p>{title} text</p>", "beside": 0, "hidden": 0}


SECTIONS = [sec("a", "Summary"), sec("b", "Milestones"), sec("c", "Risks and issues"), sec("d", "Decisions")]
MOVED = [SECTIONS[0], SECTIONS[3], SECTIONS[1], SECTIONS[2]]      # d dragged to the second place
_PAGE = {}


def page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}", "--jsx=automatic",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        css = build_page.TOKENS.read_text(encoding="utf-8") + CSS.read_text(encoding="utf-8")      # the tokens too: a border that names var(--brand-cyan) is invalid without them
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title><style>{css}</style></head>\n'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


class DragPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def draw_at(self, width, motion="no-preference"):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": motion}]}, self.sid)
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.js("!!(window.T && window.mount)")), "the test bundle ran")
        self.js(f"mount({json.dumps(SECTIONS)}, {width - 100}); 1")
        self.until("document.querySelectorAll('.secs > .sec').length === 4", "four sections")

    def until(self, expr, what):
        self.assertTrue(wait(lambda: self.js(expr)), what)

    def order(self):
        return self.js("[...document.querySelectorAll('.secs > .sec')].map(e => e.dataset.id).join('')")

    def set(self, frm, lst):
        self.js(f"(function(){{ T.store.dragFrom.value = {json.dumps(frm)}; T.store.dragList.value = {json.dumps(lst)}; }})(); 1")

    def test_the_page_is_drawn_from_the_list_and_the_dragged_section_is_the_slot(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.draw_at(width)
                self.assertEqual(self.order(), "abcd")
                self.set("d", None)
                self.until("!!document.querySelector('.sec.drag-from[data-id=d]')", "dragged, no place shown yet")
                self.assertEqual(self.order(), "abcd", "the stored order while no place is shown")
                self.assertEqual(self.js("document.querySelectorAll('.drag-slot').length"), 0)
                self.set("d", MOVED)
                self.until("!!document.querySelector('.sec.drag-slot[data-id=d]')", "the slot")
                self.assertEqual(self.order(), "adbc", "the others made room")
                self.assertEqual(self.js("document.querySelectorAll('.drag-slot').length"), 1, "one slot")
                self.assertEqual(self.js("getComputedStyle(document.querySelector('.drag-slot')).borderTopStyle"), "dashed")
                self.assertEqual(self.js("getComputedStyle(document.querySelector('.drag-slot > .sec-body, .drag-slot > header')).visibility"), "hidden",
                                 "its content is not drawn")
                self.assertEqual(self.js("getComputedStyle(document.documentElement).getPropertyValue('--dur-glide').trim()"), "160ms")
                self.assertEqual(self.js("T.store.data.value.report_sections.map(s => s.id).join('')"), "abcd", "the stored list is not touched")

    def test_the_drop_line_is_not_drawn_while_the_list_is_shown_and_leaving_clears_the_signals(self):
        self.draw_at(1400)
        self.js("T.store.dropAt.value = { line: 'end' }; 1")
        self.until("document.querySelector('.secs').classList.contains('drop-end')", "the end line without a list")
        self.set("d", MOVED)
        self.until("!document.querySelector('.secs').classList.contains('drop-end')", "no end line with a list")
        self.js("T.store.mode.value = 'view'; 1")
        self.until("!document.querySelector('.drag-slot')", "View draws no slot")
        self.assertEqual(self.order(), "abcd", "View draws the stored order")

    def glides(self):
        """The glides glide.js starts (script animations, not the CSS ones): id, first-frame offset, duration."""
        return self.js("""[...document.querySelectorAll('.secs > .sec')].flatMap(e => e.getAnimations()
            .filter(a => !(a instanceof CSSAnimation) && a.effect.getKeyframes().some(k => k.transform && k.transform !== 'none'))
            .map(a => ({ id: e.dataset.id, from: a.effect.getKeyframes()[0].transform, ms: a.effect.getTiming().duration })))""")

    def test_the_sections_that_moved_glide_and_none_do_when_motion_is_reduced(self):
        for motion, moved in (("no-preference", True), ("reduce", False)):
            with self.subTest(motion=motion):
                self.draw_at(1400, motion)
                self.js("T.noteRects(); 1")
                self.set("d", MOVED)
                self.until("!!document.querySelector('.sec.drag-slot')", "the slot")
                got = self.glides()
                if not moved:
                    self.assertEqual(got, [], "nothing glides when motion is reduced")
                    continue
                self.assertEqual(sorted(g["id"] for g in got), ["b", "c", "d"], "the sections that changed place glide, the one that did not stays")
                self.assertTrue(all(g["ms"] == 160 for g in got), "each glide lasts the --dur-glide time")
                for g in got:
                    self.assertRegex(g["from"], r"translate\(-?[\d.]+px, -?[\d.]+px\)")
                    self.assertNotRegex(g["from"], r"translate\(0px, 0px\)", "it starts from where it was")
                up = next(g for g in got if g["id"] == "d")["from"]
                self.assertRegex(up, r"translate\(-?[\d.]+px, [\d.]+px\)", "d moved up, so it starts from its old place, lower down")
                down = next(g for g in got if g["id"] == "b")["from"]
                self.assertRegex(down, r"translate\(-?[\d.]+px, -[\d.]+px\)", "b moved down, so it starts from its old place, higher up")

    def test_no_glide_when_nothing_was_noted_or_the_sections_did_not_move(self):
        self.draw_at(1400)
        self.set("a", SECTIONS)                      # a list in the stored order: nothing changes place
        self.until("!!document.querySelector('.sec.drag-slot')", "the slot")
        self.assertEqual(self.glides(), [], "no sections moved, so none glide")

    def test_the_drop_line_of_a_section_is_not_drawn_while_the_list_is_shown(self):
        self.draw_at(1400)
        self.js("T.store.dropAt.value = { line: 'before', ids: ['b'] }; 1")
        self.until("!!document.querySelector('.sec.drop-before[data-id=b]')", "the line before b without a list")
        self.set("d", MOVED)
        self.until("!!document.querySelector('.sec.drag-slot[data-id=d]')", "the slot")
        self.assertEqual(self.js("document.querySelectorAll('.drop-before, .drop-left, .drop-right').length"), 0, "only the slot marks the place")

    def test_leaving_clears_the_drag_signals_and_the_stored_order_is_drawn(self):
        self.draw_at(1400)
        self.js("T.store.dropAt.value = { line: 'end' }; 1")
        self.set("d", MOVED)
        self.until("!!document.querySelector('.sec.drag-slot')", "the slot")
        self.js("location.hash = '#left'; 1")       # a move through history calls leave() in stores/report.js
        self.until("T.store.dragList.value === undefined", "dragList cleared")
        self.assertIsNone(self.js("T.store.dragFrom.value === undefined ? null : T.store.dragFrom.value"), "dragFrom cleared")
        self.assertIsNone(self.js("T.store.dropAt.value === undefined ? null : 1"), "dropAt cleared")
        self.until("!document.querySelector('.drag-slot, .drag-from')", "no slot, no dragged mark")
        self.assertEqual(self.order(), "abcd", "the stored order is drawn")


if __name__ == "__main__":
    unittest.main()
