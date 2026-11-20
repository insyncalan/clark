"""Row 1251: an empty picture template starts with a sample picture in Edit (Classic only); View, the published file and Cards never have it.
Run: python3 dev/run_tests.py test_sample_slot_1251
Needs Chrome (the harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import unittest

from _classic_page import classic
from _demo import USER
from test_report_editor import Base
from test_server import chrome

KINDS = [("imagecap", "Fictional cap"), ("textimage", "Fictional ti"), ("gallery", "Fictional gal")]
COUNT = "(function(s){var r=document.querySelector(s);return r?[...r.querySelectorAll('[data-sample]')].filter(function(e){return e.getBoundingClientRect().height>40}).length:-1})"


def make(test, typ, title, body=None):
    with test.store.step("dashboard", USER) as st:
        row = {"project": "ABC", "type": typ, "title": title, "sort_order": 999 + len(title)}
        if body:
            row["body"] = body
        return st.create("report_sections", row)


def counts(test, refs):
    with chrome() as cdp:
        p = test.visit(cdp)
        out = {}
        for width in (1400, 900):
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            p.edit()
            for ref in refs:
                sel = f"[data-id={json.dumps(ref)}]"
                p.until(f"!!document.querySelector({json.dumps(sel)})", "the section is drawn")
                out[(ref, width)] = p.js(f"{COUNT}({json.dumps(sel)})")
            p.view()
            out[("view", width)] = p.js("document.querySelectorAll('[data-sample]').length")
        return out


class Classic(Base):
    def setUp(self):
        super().setUp()
        classic(self)

    def test_each_empty_picture_template_has_one_sample_in_edit_and_view_has_none(self):
        refs = [make(self, t, ti) for t, ti in KINDS]
        got = counts(self, refs)
        for ref in refs:
            for width in (1400, 900):
                self.assertEqual(got[(ref, width)], 1, f"{ref} at {width}")
        for width in (1400, 900):
            self.assertEqual(got[("view", width)], 0)

    def test_a_template_with_a_picture_has_no_sample(self):
        pic = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        ref = make(self, "imagecap", "Fictional full")
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", ref, {"body": json.dumps({"v": 1, "pictures": {"image": pic}})})
        got = counts(self, [ref])
        self.assertEqual(got[(ref, 1400)], 0)


class Cards(Base):
    def test_cards_has_no_sample(self):
        refs = [make(self, t, ti) for t, ti in KINDS]
        got = counts(self, refs)
        for ref in refs:
            self.assertEqual(got[(ref, 1400)], 0)


if __name__ == "__main__":
    unittest.main()
