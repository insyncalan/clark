"""Row 1005 by eye: the Movement Who agreed it / Reason / Source and the RAID Own words, on the one editor, in a real browser.

Run: python3 dev/run_tests.py test_p1005b_eye        (set CLARK_SHOTS_1005B=<folder> to save a screenshot of each state)
Own words is kept at 400 characters (OWN_MAX). Over it the editor stays open, and now says so in the editor's own words (the same words
as a field too long to save anywhere else). Empty, 400, over 400, a paste with paragraphs, Escape and the keyboard, at 1400 and 900, light and dark.
Fictional data only.
"""
import base64
import json
import os
import time
import unittest
from pathlib import Path

from _demo import USER
from test_report_editor import Base as PageBase
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


class Raid(PageBase):
    def seed(self, own):
        with self.store.step("dashboard", USER) as st:
            risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier may slip", "raised": "2026-10-01",
                                      "source": "demo", "client_message": "We are watching the supplier."})
            sec = st.create("report_sections", {"project": "ABC", "type": "raid3", "title": "Fictional cards", "sort_order": 999,
                                                "body": json.dumps({"v": 1, "cards": [{"id": risk, "source": "own", "own": own}]})})
        self.sec = sec
        return sec

    def stored(self):
        row = next(r for r in self.store.read("report_sections", "ABC") if r["id"] == self.sec)
        return json.loads(row["body"])["cards"][0].get("own", "")

    def wait_for(self, fn, seconds=10):
        end = time.time() + seconds
        while time.time() < end:
            if fn():
                return True
            time.sleep(0.1)
        return False

    def open_editor(self, cdp):
        p = self.visit(cdp)
        p.edit()
        view = f"[data-id={json.dumps(self.sec)}] .rce-f .rt-view"
        p.until(f"!!document.querySelector({json.dumps(view)})", "own words field")
        return p, view, f"[data-id={json.dumps(self.sec)}] .rce-f .ProseMirror"

    def typed(self, p, box, text):
        p.js("(function(){var b = document.querySelector(%s); b.focus(); b.cxed.editor.commands.setContent('<p>' + %s + '</p>');})()" % (json.dumps(box), json.dumps(text)))

    def test_empty_shows_the_quiet_line_and_saves_nothing_new(self):
        self.seed("")
        with chrome() as cdp:
            p, view, box = self.open_editor(cdp)
            self.assertIn("Click to write", p.js(f"document.querySelector({json.dumps(view)}).textContent"))
            snap(p, "raid-empty")
            p.js(f"document.querySelector({json.dumps(view)}).click()")
            p.until(f"!!document.querySelector({json.dumps(box)})", "opened")
            snap(p, "raid-empty-open", ".rce-own")
            n = len([s for s in self.sent if s[0] == "change"])
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            p.until(f"!document.querySelector({json.dumps(box)})", "closed with nothing typed")
            self.assertEqual(len([s for s in self.sent if s[0] == "change"]), n, "nothing typed, nothing saved")

    def test_exactly_400_saves_and_over_400_stays_open_and_says_so(self):
        self.seed("Old words")
        with chrome() as cdp:
            p, view, box = self.open_editor(cdp)
            p.js(f"document.querySelector({json.dumps(view)}).click()")
            p.until(f"!!document.querySelector({json.dumps(box)})", "opened")
            over = "w" * 401
            self.typed(p, box, over)
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            p.until(f"!!document.querySelector('[data-id={json.dumps(self.sec)}] .rt-problem')", "a message says it is too long")
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(self.sec)}] .rt-problem').textContent"), TOO_LONG)
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(self.sec)}] .rt-problem').getAttribute('role')"), "alert")
            self.assertTrue(p.js(f"!!document.querySelector({json.dumps(box)})"), "the editor stays open")
            self.assertEqual(self.stored(), "Old words", "nothing over the limit is stored")
            snap(p, "raid-over-400", ".rt-problem")
            self.typed(p, box, "w" * 399 + "x")                      # typing again clears the message
            p.until(f"!document.querySelector('[data-id={json.dumps(self.sec)}] .rt-problem')", "the message goes once the text changes")
            snap(p, "raid-400", ".rce-own")
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            self.assertTrue(self.wait_for(lambda: self.stored() == "w" * 399 + "x"), "400 characters save")
            p.until(f"!document.querySelector({json.dumps(box)})", "closed after the save")
            # long, unbroken text stays inside the card at both widths
            self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True)

    def test_the_open_editor_takes_its_own_row_and_the_card_selects_keep_their_height(self):
        """A tall editor in a narrow cell stretched the two selects beside it (a 700 px select); the words now span the card's row."""
        self.seed("Old words")
        with chrome() as cdp:
            p, view, box = self.open_editor(cdp)
            p.js(f"document.querySelector({json.dumps(view)}).click()")
            p.until(f"!!document.querySelector({json.dumps(box)})", "opened")
            self.typed(p, box, "w " * 150)
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                time.sleep(0.3)
                sel = f"[data-id={json.dumps(self.sec)}] .rce-f select"
                self.assertLess(p.js("Math.max.apply(null, [...document.querySelectorAll(%s)].map(function(e){return e.getBoundingClientRect().height}))" % json.dumps(sel)), 60, w)
                self.assertGreater(p.js("document.querySelector(%s).getBoundingClientRect().width" % json.dumps(f"[data-id={json.dumps(self.sec)}] .rce-own .rt")), 400, w)

    def test_a_paste_with_paragraphs_is_one_plain_line_and_escape_keeps_the_old_words(self):
        self.seed("Old words")
        with chrome() as cdp:
            p, view, box = self.open_editor(cdp)
            p.js(f"document.querySelector({json.dumps(view)}).click()")
            p.until(f"!!document.querySelector({json.dumps(box)})", "opened")
            p.js("document.querySelector(%s).cxed.editor.commands.setContent('')" % json.dumps(box))
            paste(p, box, PARAS, "First paragraph of the reason.\n\nSecond paragraph, agreed on a call.\n\nThird.")
            p.until(f"document.querySelector({json.dumps(box)}).querySelectorAll('p').length >= 2", "the paste kept its paragraphs in the editor")
            snap(p, "raid-paste", ".rce-own")
            p.key("Escape", code="Escape", vk=27)
            p.until(f"!document.querySelector({json.dumps(box)})", "Escape closed the editor")
            self.assertEqual(self.stored(), "Old words", "Escape saves nothing")
            p.until(f"document.activeElement === document.querySelector({json.dumps(view)})", "the focus is back on the field")
            # keyboard: Enter opens, type, Cmd+Enter saves, focus returns
            p.key("Enter", code="Enter", vk=13)
            p.until(f"!!document.querySelector({json.dumps(box)})", "Enter opened it")
            paste(p, box, PARAS, "x")
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            self.assertTrue(self.wait_for(lambda: "First paragraph of the reason. Second paragraph, agreed on a call. Third." in self.stored()), self.stored())
            self.assertNotIn("\n", self.stored())
            p.until(f"document.activeElement === document.querySelector({json.dumps(view)})", "the focus is back after the save")
            snap(p, "raid-saved")

    def test_forty_items_of_long_words_stay_inside_the_page(self):
        """A card row holds three cards at most, so the forty are the items the card's item list offers."""
        self.seed("x" * 400)
        with self.store.step("dashboard", USER) as st:
            for i in range(39):
                st.create("raid", {"project": "ABC", "type": "Risk", "description": "Item %d %s" % (i, "long " * 20), "raised": "2026-10-01", "source": "demo"})
        with chrome() as cdp:
            p, view, box = self.open_editor(cdp)
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                time.sleep(0.3)
                self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, w)
            self.assertGreaterEqual(p.js("document.querySelectorAll(%s).length" % json.dumps("[data-id=%s] select[aria-label='Card 1 item'] option" % json.dumps(self.sec))), 40)
            snap(p, "raid-forty")


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
        p.until("!document.querySelector(%s)" % json.dumps(box), "the editor closed")

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
