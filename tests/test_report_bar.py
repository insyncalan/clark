"""A-D2: the bar above the page (the week the report covers, where it stands, and in Edit the notes), in a real browser.

Run: python3 dev/run_tests.py test_report_bar
The page is the committed one, served by a real server whose change and undo routes are the real clark.changes over a real store in
a temporary folder (fictional data). Laptop widths only: 1400 and 900 px, light and dark. The published file is read from its bytes.
"""
import json
import re
import unittest

from _paths import SRC
from test_report_editor import Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome

from clark import changes

PAGE = SRC / "clark" / "page"


class Bar(Base):
    def show(self, cdp, width=1400, dark=False):
        p = Pg.at(self, cdp, self.s.port, "#dashboard&p=ABC")
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        p.ready()
        p.until("!!document.querySelector('#report-bar')", "the bar drew")
        return p

    def week(self):
        return self.store.read("projects", ref="ABC")["week_ending"]

    def test_view_has_the_week_as_text_and_a_draft_chip_and_no_field(self):
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.show(cdp, w)
                self.assertRegex(p.js("document.querySelector('#week-ending-text').textContent"), r"^(Week ending \d\d-\d\d-\d{4}|No week ending date yet)$")
                self.assertEqual(p.js("document.querySelector('#report-state').textContent"), "Draft · not published yet")
                self.assertEqual(p.js("document.querySelectorAll('#report input, .rbar input').length"), 0, "View has no field")
                self.assertIsNone(p.js("document.querySelector('#report-hint')"))

    def test_edit_has_the_field_and_the_two_notes(self):
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.show(cdp, w)
                p.edit()
                p.until("!!document.querySelector('#week-ending')", "the date field")
                self.assertEqual(p.js("document.querySelector('#report-state').textContent"), "Editing · each change saves on its own")
                self.assertEqual(p.js("document.querySelector('#report-hint').textContent"), "Drag to move, + to add a template")
                self.assertEqual(p.js("document.querySelector('#week-ending').type"), "text")
                self.assertEqual(p.js("document.querySelector('#week-ending').labels.length"), 1, "the field has its label")

    def test_a_new_week_is_saved_and_undone(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            before = self.week()
            self.type_week(p, "09-05-2031")
            p.saved()
            self.assertEqual(self.week(), "2031-05-09")
            self.assertEqual(p.toast(), "Week ending changed to 09-05-2031.")
            self.assertEqual(p.js("document.querySelector('#week-ending').value"), "09-05-2031")
            p.js("document.querySelector('[data-undo]').click()")
            p.until("document.querySelector('#week-ending').value === %r" % ("-".join(reversed(before.split("-"))) if before else ""), "the date came back")
            self.assertEqual(self.week(), before)

    def type_week(self, p, text):
        p.js("(() => { const e = document.querySelector('#week-ending'); e.focus(); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, %s); e.blur(); })()" % json.dumps(text))

    def test_a_typed_entry_that_is_not_a_day_keeps_the_old_date_and_says_so(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            before = self.week()
            shown = "-".join(reversed(before.split("-"))) if before else ""
            for bad in ("31-02-2031", "tomorrow", "2031/5"):
                with self.subTest(bad=bad):
                    self.type_week(p, bad)
                    p.until("/clark can read/.test(document.body.textContent)", "the plain words")
                    self.assertIn("The old week ending date was kept.", p.js("document.body.textContent"))
                    self.assertEqual(p.js("document.querySelector('#week-ending').value"), shown)
                    self.assertEqual(self.week(), before)

    def test_the_route_refuses_a_date_that_is_not_one(self):
        for bad in ("2031-02-30", "tomorrow", "09-05-2031", 20310509, None):
            with self.subTest(bad=bad):
                req = {"project": "ABC", "kind": "projects", "op": "update", "changes": {"week_ending": bad}}
                status, _, raw = self.s.api("POST", "/api/change", json.dumps(req).encode("utf-8"))
                self.assertEqual(status, 400)
                self.assertIn("real date", json.loads(raw).get("message", ""))
        self.assertIn("week_ending", changes.CHANGE_KINDS["projects"]["update"])

    def test_the_text_has_contrast_of_4_5_to_1_in_light_and_dark(self):
        script = """(() => {
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
          const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
          return ['.rbar-week', '#report-state', '#report-hint', '#week-ending'].map((sel) => {
            const el = document.querySelector(sel); let bg = el, back = 'rgba(0, 0, 0, 0)';
            while (bg && /rgba\\(.*, 0\\)|transparent/.test(back)) { back = getComputedStyle(bg).backgroundColor; bg = bg.parentElement; }
            return [sel, ratio(getComputedStyle(el).color, back)]; });
        })()"""
        for dark in (False, True):
            with self.subTest(dark=dark), chrome() as cdp:
                p = self.show(cdp, 1400, dark)
                p.edit()
                p.until("!!document.querySelector('#week-ending')", "the field")
                for sel, r in p.js(script):
                    self.assertGreaterEqual(r, 4.5, sel)

    def test_the_published_file_has_no_bar(self):
        html = (PAGE / "page-view.html").read_text(encoding="utf-8")
        for name in ("report-bar", "week-ending", "rbar-state", "Draft · not published yet"):
            self.assertNotIn(name, html)
        self.assertIsNone(re.search(r"Editing · each change saves", html))


if __name__ == "__main__":
    unittest.main()
