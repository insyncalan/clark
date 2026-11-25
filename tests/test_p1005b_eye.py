"""Row 1005 by eye: the Movement Who agreed it / Reason / Source, on the one editor, in a real browser.

Run: python3 dev/run_tests.py test_p1005b_eye        (set CLARK_SHOTS_1005B=<folder> to save a screenshot of each state)
The RAID Own words tests are dropped: the editor is out of Edit (ticket 1270 line 26, approved 18-11 14:27).
Fictional data only.
"""
import base64
import json
import os
import sys
import time
import unittest
from pathlib import Path

from test_server import chrome
import test_movement_page as tmp

SHOTS = os.environ.get("CLARK_SHOTS_1005B", "")
TOO_LONG = "That is too long to save. Shorten it and try again."
LONG_NAME = "Pat Example-Longname " * 12
PARAS = "<p>First paragraph of the reason.</p><p>Second paragraph, agreed on a call.</p><p>Third.</p>"


def snap(p, name, at=None):
    """A screenshot at 1400 and 900, light and dark, when CLARK_SHOTS_1005B is set."""
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    for w in (1400, 900):
        p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        for scheme in ("light", "dark"):
            p.js(f"document.documentElement.dataset.theme = '{scheme}'")
            if at:
                p.js("(function(){var e = document.querySelector(%s); if (e) e.scrollIntoView({block: 'center'});})()" % json.dumps(at))
            time.sleep(0.3)
            data = p.cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]
            (Path(SHOTS) / f"{name}-{scheme}-{w}.png").write_bytes(base64.b64decode(data))
    p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
    p.js("document.documentElement.dataset.theme = 'light'")


def paste(p, box, html, text):
    p.js("(function(){var b = document.querySelector(%s); b.focus(); var d = new DataTransfer(); d.setData('text/html', %s); d.setData('text/plain', %s);"
         " b.dispatchEvent(new ClipboardEvent('paste', {clipboardData: d, bubbles: true, cancelable: true}));})()" % (json.dumps(box), json.dumps(html), json.dumps(text)))


class Movement(tmp.Base):
    def form(self, cdp, theme=None):
        p = self.visit(cdp)
        self.open_movement(p)
        p.js("document.querySelector('#mv-move').click()")
        p.until("!!document.querySelector('.mvm-form')", "the form opened")
        p.until("document.activeElement.id === 'mv-to'", "focus went to the first field")
        return p

    def box(self, k):
        return ".mvm-f[data-f=%s] .ProseMirror" % k

    def fill(self, p, ident, value):
        if ident == "mv-to":
            p.js("(function(){var e = document.getElementById(%s); e.value = %s; e.dispatchEvent(new Event('input', {bubbles: true}));})()" % (json.dumps(ident), json.dumps(value)))
            return
        box = self.box(ident[3:])
        p.js("document.getElementById(%s).click()" % json.dumps(ident))
        p.until("!!document.querySelector(%s)" % json.dumps(box), "the editor opened")
        p.js("(function(){var b = document.querySelector(%s); b.cxed.editor.commands.setContent('<p>' + %s + '</p>'); b.blur();})()" % (json.dumps(box), json.dumps(value)))
        # A slow runner can drop the first blur: re-issue it until the editor box is gone, for up to 15 s.
        gone = "!document.querySelector(%s)" % json.dumps(box)
        reblur = "(function(){var b = document.querySelector(%s); if (b) { b.focus(); b.blur(); } })()" % json.dumps(box)

        end = time.time() + 15
        while time.time() < end and not p.js(gone):
            p.js(reblur)
            time.sleep(0.2)
        self.assertTrue(p.js(gone), "the editor closed")

    def test_empty_fields_are_asked_for_and_look_right(self):
        with chrome() as cdp:
            p = self.form(cdp)
            snap(p, "move-empty")
            p.js("document.querySelector('#mv-go').click()")
            p.until("document.querySelectorAll('.mvm-problems p').length === 3", "three reasons")
            snap(p, "move-empty-refused", ".mvm-problems")

    def test_escape_in_a_field_closes_the_editor_not_the_form_and_keeps_the_old_words(self):
        with chrome() as cdp:
            p = self.form(cdp)
            self.fill(p, "mv-who", "Pat Example")
            p.js("document.getElementById('mv-who').click()")
            p.until("!!document.querySelector(%s)" % json.dumps(self.box("who")), "opened")
            p.js("document.querySelector(%s).cxed.editor.commands.setContent('<p>Changed</p>')" % json.dumps(self.box("who")))
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector(%s)" % json.dumps(self.box("who")), "the editor closed")
            self.assertTrue(p.js("!!document.querySelector('.mvm-form')"), "the form stays")
            self.assertIn("Pat Example", p.js("document.getElementById('mv-who').textContent"))
            self.assertNotIn("Changed", p.js("document.getElementById('mv-who').textContent"))
            p.until("document.activeElement.id === 'mv-who'", "the focus is on the field")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('.mvm-form')", "Escape on the field closes the form")

    def test_hostile_values_long_names_paragraphs_and_5000_characters(self):
        _, text = tmp.in_days(30)
        with chrome() as cdp:
            p = self.form(cdp)
            self.fill(p, "mv-to", text)
            self.fill(p, "mv-who", LONG_NAME)
            p.js("document.getElementById('mv-reason').click()")
            p.until("!!document.querySelector(%s)" % json.dumps(self.box("reason")), "opened")
            paste(p, self.box("reason"), PARAS, "x")
            snap(p, "move-paste")
            p.js("document.querySelector(%s).blur()" % json.dumps(self.box("reason")))
            p.until("!document.querySelector(%s)" % json.dumps(self.box("reason")), "closed")
            shown = p.js("document.getElementById('mv-reason').textContent")
            self.assertIn("First paragraph of the reason.", shown)
            self.fill(p, "mv-source", "s" * 400)
            snap(p, "move-long")
            for w in (1400, 900):
                p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                time.sleep(0.3)
                self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, w)
            p.js("document.querySelector('#mv-go').click()")
            p.until("!document.querySelector('.mvm-form') || !!document.querySelector('.mvm-problems p')", "it was sent or refused")
            req = self.sent[-1][1] if self.sent else {}
            if req.get("rebaseline"):
                for k in ("agreed_with", "reason", "source"):
                    self.assertNotIn("\n", req["rebaseline"][k])
                self.assertEqual(req["rebaseline"]["reason"], "First paragraph of the reason. Second paragraph, agreed on a call. Third.")

    def test_over_a_limit_the_server_says_so_in_the_form(self):
        _, text = tmp.in_days(30)
        with chrome() as cdp:
            p = self.form(cdp)
            for ident, value in (("mv-to", text), ("mv-who", "Pat Example"), ("mv-reason", "r" * 5000), ("mv-source", "s")):
                self.fill(p, ident, value)
            p.js("document.querySelector('#mv-go').click()")
            p.until("!!document.querySelector('.mvm-problems p')", "the refusal is shown")
            self.assertTrue(p.js("!!document.querySelector('.mvm-form')"), "the form stays")
            self.assertTrue(p.js("document.querySelector('.mvm-problems p').textContent.length > 5"))
            snap(p, "move-over-limit", ".mvm-problems")


if __name__ == "__main__":
    unittest.main()
