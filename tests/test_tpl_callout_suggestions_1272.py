"""Row 1272 AP4: each of the three suggestion buttons in the Callout Edit toolbar sets word, colour and icon in one step, at 1400 and 900 px.
Information = Violet and the info icon; Decision needed = Amber and Two ways; Warning = Red and Warning triangle. Classic only (the Shared base), no Cards look.
The older test_edit_each_suggestion_sets_its_own_colour_and_icon pins two of the three at the default width; this one pins all three at both widths.
Run: TZ=Asia/Dubai python3 dev/run_tests.py test_tpl_callout_suggestions_1272   (needs Chrome)
Fictional data only.
"""
import json
import unittest

from _demo import USER
from test_server import chrome, wait
from test_theme_callout_1272 import Shared

CASES = (("Use Information", ("Information", "violet", "info", "info")),
         ("Use Decision needed", ("Decision needed", "amber", "fork", "decision")),
         ("Use Warning", ("Warning", "red", "warning", "warning")))


class Suggestions(Shared):
    def make(self, tone):
        body = {"v": 1, "tone": tone, "title": "Fictional callout", "paras": ["Fictional words."], "category": "Other", "colour": "grey", "icon": "none"}
        with self.store.step("dashboard", USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": "callout", "title": "Fictional callout", "sort_order": 998, "beside": 0, "body": json.dumps(body)})

    def test_each_suggestion_sets_word_colour_and_icon_at_1400_and_900(self):
        for width in (1400, 900):
            for label, want in CASES:
                ref = self.make("info")
                with self.subTest(width=width, label=label), chrome() as cdp:
                    p = self.visit(cdp)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.edit()
                    sel = "[data-id=%s] [aria-label=\"%s\"]" % (json.dumps(ref), label)
                    p.until(f"!!document.querySelector('{sel}')", "the toolbar")
                    p.js(f"document.querySelector('{sel}').click()")
                    self.assertTrue(wait(lambda: json.loads(self.store.read("report_sections", ref=ref)["body"]).get("colour") == want[1], 10), label)
                    got = json.loads(self.store.read("report_sections", ref=ref)["body"])
                    self.assertEqual((got["category"], got["colour"], got["icon"], got["tone"]), want)


if __name__ == "__main__":
    unittest.main()
