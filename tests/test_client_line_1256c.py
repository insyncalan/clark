"""Row 1256 (item C): the Client visible line (.cv) is 14 px / 500, muted with an eye, teal when the item is shown to the client, and it is drawn in View, in Edit
(read only in View; row 1466: never in a published file). The words are the Edit line's own.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_client_line_1256c
Demo project: TUL-007 is a client-visible risk, TUL-008 a risk the test hides from the client.
"""
import json
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

import test_peek_ruled_1077 as base  # noqa: E402
import test_publish as tp  # noqa: E402
from test_server import chrome, wait  # noqa: E402

ON, OFF = "TUL-007", "TUL-008"
LINE = ("(() => { const e = document.querySelector('#peek [data-pk-client-row] .cv'); if (!e) return null; const c = getComputedStyle(e), r = e.getBoundingClientRect();"
        " return { text: e.textContent.trim(), tag: e.tagName, size: c.fontSize, weight: c.fontWeight, colour: c.color, eye: !!e.querySelector('svg'), on: e.classList.contains('on'), h: r.height, w: r.width }; })()")
ICON = ("(() => { const e = document.querySelector('#peek [data-pk-client-row] .cv svg'); return e ? e.innerHTML : null; })()")
ROLE = ("(() => { const e = document.querySelector('#peek [data-pk-client-row] .cv'); return e ? [e.getAttribute('role'), e.getAttribute('tabindex')] : null; })()")
TEAL = "rgb(0, 134, 117)"      # --status-green, the brand's teal-green (the mock-up's #0A8F9C has no token)


class Line(base.Peeks):
    def hide(self, ref):
        with self.store.step("dashboard", "Demo User") as st:
            st.update("raid", ref, {"client_visible": 0})

    def line(self, cdp, sid):
        self.assertTrue(wait(lambda: cdp.js(LINE, sid) is not None), "the Client visible line drew")
        return cdp.js(LINE, sid)

    def look(self, got, on):
        self.assertEqual((got["size"], got["weight"]), ("14px", "500"), got)
        self.assertTrue(got["eye"], "an eye icon")
        self.assertEqual(got["on"], on)
        self.assertEqual(got["text"], "Client visible" if on else "Client not visible")
        if on:
            self.assertEqual(got["colour"], TEAL, "teal when shown to the client")
        else:
            self.assertNotEqual(got["colour"], TEAL, "muted when not")

    def test_view_draws_the_line_read_only_teal_when_on(self):
        self.hide(OFF)
        for width in (1400, 900):
            for ref, on in ((ON, True), (OFF, False)):
                with self.subTest(width=width, ref=ref), chrome() as cdp:
                    sid = self.dashboard_in_view(cdp, width, self.store, self.code)
                    self.open_peek(cdp, sid, ref, "item")
                    got = self.line(cdp, sid)
                    self.look(got, on)
                    self.assertEqual(got["tag"], "SPAN", "text, not a control, in View")
                    self.assertGreaterEqual(got["w"], 100, "the line has room, one line high")
                    self.assertLess(got["h"], 40)

    def test_edit_button_has_the_same_look(self):
        self.hide(OFF)
        for width in (1400, 900):
            for ref, on in ((ON, True), (OFF, False)):
                with self.subTest(width=width, ref=ref), chrome() as cdp:
                    sid = self.dashboard_in_view(cdp, width, self.store, self.code)
                    self.to_edit(cdp, sid)
                    self.open_peek(cdp, sid, ref, "item")
                    got = self.line(cdp, sid)
                    self.look(got, on)
                    self.assertEqual(got["tag"], "BUTTON")
                    self.assertGreaterEqual(got["w"], 100)

    def test_the_eye_shape_differs_on_and_off_and_matches_edit(self):
        self.hide(OFF)
        shapes = {}
        for mode in ("view", "edit"):
            for ref, on in ((ON, True), (OFF, False)):
                with chrome() as cdp:
                    sid = self.dashboard_in_view(cdp, 1400, self.store, self.code)
                    if mode == "edit":
                        self.to_edit(cdp, sid)
                    self.open_peek(cdp, sid, ref, "item")
                    self.line(cdp, sid)
                    shapes[(mode, on)] = cdp.js(ICON, sid)
        self.assertIsNotNone(shapes[("view", True)])
        self.assertNotEqual(shapes[("view", True)], shapes[("view", False)], "eye and eyeoff differ")
        self.assertEqual(shapes[("view", True)], shapes[("edit", True)], "View eye is the Edit eye")
        self.assertEqual(shapes[("view", False)], shapes[("edit", False)])

    def test_the_view_line_is_inert_text(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.dashboard_in_view(cdp, width, self.store, self.code)
                self.open_peek(cdp, sid, ON, "item")
                self.line(cdp, sid)
                self.assertEqual(cdp.js(ROLE, sid), [None, None], "no role or tabindex on read-only text")

    def test_a_published_file_never_draws_the_line_or_its_eye(self):      # row 1466 (reverses row 1256 for the published file only)
        _plant, _pub, text = tp.made()
        folder = Path(tempfile.mkdtemp(prefix="clark-1256c-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(folder), ignore_errors=True))
        path = folder / "report.html"
        path.write_text(text, encoding="utf-8")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = tp.opened(cdp, path.as_uri() + "#work&p=PUB&item=PUB-A-001", width)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-fields dt')", sid)), "the published peek drew")
                self.assertIsNone(cdp.js(LINE, sid), "no Client visible line in a published file")
                self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-pk-client-row], #peek [data-pk-client-read], #peek .cv').length", sid), 0)
                self.assertNotRegex(cdp.js("document.querySelector('#peek').innerText", sid), r"(?i)client (not )?visible")


class Source(unittest.TestCase):
    def test_the_line_is_one_class_shared_by_the_button_and_the_text(self):
        body = (ROOT / "src/clark/page/src/components/PeekActionBody.jsx").read_text(encoding="utf-8")
        props = (ROOT / "src/clark/page/src/edit/PeekProps.jsx").read_text(encoding="utf-8")
        peek = (ROOT / "src/clark/page/src/components/Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("data-pk-client-read", body)
        self.assertIn("pk-client cv", props)
        self.assertIn("onFile={fromFile.value}", peek)


if __name__ == "__main__":
    unittest.main()
