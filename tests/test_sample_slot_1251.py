"""Row 1251: an empty picture template starts with a sample picture in Edit (Classic only); View, the published file and Cards never have it.
Run: python3 dev/run_tests.py test_sample_slot_1251
Needs Chrome (the harness): the page tests fail, never skip, without it. Fictional data only.
"""
import base64
import json
import unittest

from _classic_page import classic
from _demo import USER
from test_report_editor import Base
from test_server import chrome
from _publish import PublishedFile
from _paths import ROOT

SAMPLES = ROOT / "src" / "clark" / "page" / "sample-pictures"
Pub = PublishedFile

KINDS = [("imagecap", "Fictional cap"), ("textimage", "Fictional ti"), ("gallery", "Fictional gal"), ("imagecap", "Fictional full", json.dumps({"v": 2}))]
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
        refs = [make(self, *k) for k in KINDS]
        got = counts(self, refs)
        for ref, want in zip(refs, (1, 1, 6, 1)):      # the gallery shows its six
            for width in (1400, 900):
                self.assertEqual(got[(ref, width)], want, f"{ref} at {width}")
        for width in (1400, 900):
            self.assertEqual(got[("view", width)], 0)

    def test_a_template_with_a_picture_has_no_sample(self):
        pic = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        ref = make(self, "imagecap", "Fictional full")
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", ref, {"body": json.dumps({"v": 1, "pictures": {"image": pic}})})
        got = counts(self, [ref])
        self.assertEqual(got[(ref, 1400)], 0)


    def test_the_gallery_samples_are_six_different_pictures_that_loaded_and_the_published_file_has_none(self):
        ref = make(self, "gallery", "Fictional six")
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sel = json.dumps(f"[data-id={json.dumps(ref)}]")
            p.until(f"!!document.querySelector({sel})", "the section is drawn")
            got = p.js("(function(s){return [...document.querySelector(s).querySelectorAll('img[data-sample]')].map(function(i){return [i.src.length,i.naturalWidth,i.getBoundingClientRect().width]})})(" + sel + ")")
        self.assertEqual(len(got), 6)
        self.assertEqual(len({g[0] for g in got}), 6)
        self.assertTrue(all(g[1] == 640 and g[2] > 40 for g in got), got)

    def test_the_sample_fills_its_slot_in_the_16_by_9_shape_at_both_widths(self):
        ref = make(self, "imagecap", "Fictional frame")
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.edit()
                sel = json.dumps(f"[data-id={json.dumps(ref)}] img[data-sample]")
                p.until(f"!!document.querySelector({sel})", "the sample is drawn")
                w, h, pw, edge, rad = p.js("(function(i){var r=i.getBoundingClientRect(),k=getComputedStyle(i);return [r.width,r.height,(function(c){return i.parentNode.clientWidth-parseFloat(c.paddingLeft)-parseFloat(c.paddingRight)})(getComputedStyle(i.parentNode)),k.borderTopWidth,k.borderTopLeftRadius]})(document.querySelector(" + sel + "))")
                self.assertAlmostEqual(w, pw, delta=2, msg=f"{width} {w} {h} {pw}")
                self.assertAlmostEqual(w / h, 16 / 9, delta=0.03, msg=f"{width} {w} {h} {pw}")
                self.assertEqual(edge, "1px", width)      # the Classic rule: a thin edge and rounded corners
                self.assertNotEqual(rad, "0px", width)

    def test_the_published_file_holds_no_sample_even_when_the_template_is_empty(self):
        make(self, "gallery", "Fictional pub")
        make(self, "imagecap", "Fictional pub full", json.dumps({"v": 2}))
        path = Pub.publish(self)
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("data-sample", text)
        for i in range(1, 7):
            self.assertNotIn(base64.b64encode((SAMPLES / f"sample-{i}.png").read_bytes()).decode("ascii"), text)


class Cards(Base):
    def test_cards_has_no_sample(self):
        refs = [make(self, *k) for k in KINDS]
        got = counts(self, refs)
        for ref in refs:
            self.assertEqual(got[(ref, 1400)], 0)


if __name__ == "__main__":
    unittest.main()
