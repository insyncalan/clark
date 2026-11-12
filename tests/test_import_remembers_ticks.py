"""The "What to import" window opens with the sheets ticked at the last confirmed import."""
import json
import unittest

from test_server import chrome
from test_settings_data_page import Card, WIDTHS, workbook

KEY = "clark.importSheets"
TICKED = "[...document.querySelectorAll('#import-sheet-list li')].filter(li => li.querySelector('input').checked).map(li => li.innerText.split(' (')[0])"


class Remembered(Card):
    def listed(self, p, b64, w, stored=None, theme="light"):
        p.width(w)
        p.js("document.documentElement.dataset.theme = %s" % json.dumps(theme))
        if stored is not None:
            p.js("localStorage.setItem(%s, %s)" % (json.dumps(KEY), json.dumps(json.dumps(stored))))
        self.open_box(p)
        self.pick_file(p, b64)
        p.until("!!document.querySelector('#import-continue')", "the sheet list")
        return p.js(TICKED)

    def test_the_window_opens_with_the_sheets_ticked_last_time_and_ignores_missing_ones(self):
        b64, _, _ = workbook(self.rig, self.tmp.name, "Agree the cut-over plan, version two")
        every = ["Actions", "Risks & Issues", "Decisions", "Milestones", "Use cases"]
        for w in WIDTHS:
            for theme in ("light", "dark"):
                with self.subTest(width=w, theme=theme), chrome() as cdp:
                    p = self.page(cdp)
                    self.assertEqual(self.listed(p, b64, w, None, theme), every, "nothing remembered: today's default")
                with self.subTest(width=w, theme=theme, case="remembered"), chrome() as cdp:
                    p = self.page(cdp)
                    self.assertEqual(self.listed(p, b64, w, ["Decisions", "Milestones", "Gone"], theme), ["Decisions", "Milestones"])
                    self.assertNotIn("Gone", p.js("document.querySelector('#import-box').innerText"), "nothing says it was missing")
                with self.subTest(width=w, theme=theme, case="none here"), chrome() as cdp:
                    p = self.page(cdp)
                    self.assertEqual(self.listed(p, b64, w, ["Gone"], theme), every)

    def test_the_ticks_are_remembered_when_the_import_is_confirmed_and_not_before(self):
        b64, _, _ = workbook(self.rig, self.tmp.name, "Agree the cut-over plan, version two")
        with chrome() as cdp:
            p = self.page(cdp)
            self.listed(p, b64, 1400)
            p.js("document.querySelector('#import-clear').click()")
            p.js("document.querySelector('[data-sheet=actions]').click()")
            self.assertIsNone(p.js("localStorage.getItem(%s)" % json.dumps(KEY)), "ticking remembers nothing")
            p.js("document.querySelector('#import-continue').click()")
            p.until("!!document.querySelector('#import-go')", "the check")
            self.assertIsNone(p.js("localStorage.getItem(%s)" % json.dumps(KEY)), "the check remembers nothing")
            p.js("document.querySelector('#import-go').click()")
            p.until("!!document.querySelector('#import-result')", "the result")
            self.assertEqual(json.loads(p.js("localStorage.getItem(%s)" % json.dumps(KEY))), ["Actions"])
            p.js("document.querySelector('#import-close').click()")
            p.until("!document.querySelector('#import-box')", "closed")
            self.pick_file_again(p, b64)

    def pick_file_again(self, p, b64):
        self.open_box(p)
        self.pick_file(p, b64)
        p.until("!!document.querySelector('#import-continue')", "the sheet list")
        self.assertEqual(p.js(TICKED), ["Actions"])


if __name__ == "__main__":
    unittest.main()
