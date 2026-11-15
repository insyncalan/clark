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

    def open(self, width, motion="no-preference"):
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
                self.open(width)
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
        self.open(1400)
        self.js("T.store.dropAt.value = { line: 'end' }; 1")
        self.until("document.querySelector('.secs').classList.contains('drop-end')", "the end line without a list")
        self.set("d", MOVED)
        self.until("!document.querySelector('.secs').classList.contains('drop-end')", "no end line with a list")
        self.js("T.store.mode.value = 'view'; 1")
        self.until("!document.querySelector('.drag-slot')", "View draws no slot")
        self.assertEqual(self.order(), "abcd", "View draws the stored order")

    def test_the_sections_that_moved_glide_and_none_do_when_motion_is_reduced(self):
        for motion, moved in (("no-preference", True), ("reduce", False)):
            with self.subTest(motion=motion):
                self.open(1400, motion)
                self.js("T.noteRects(); 1")
                self.set("d", MOVED)
                self.until("!!document.querySelector('.sec.drag-slot')", "the slot")
                n = self.js("document.querySelectorAll('.secs > .sec').length && [...document.querySelectorAll('.secs > .sec')].reduce((n, e) => n + e.getAnimations().filter(a => a.effect.getKeyframes().some(k => k.transform && k.transform !== 'none')).length, 0)")
                if moved:
                    self.assertGreater(n, 0, "a section that changed place glides")
                else:
                    self.assertEqual(n, 0, "nothing glides when motion is reduced")


if __name__ == "__main__":
    unittest.main()
