"""A-D2: the bar above the page (the week the report covers, where it stands, and in Edit the notes), in a real browser.

Run: python3 dev/run_tests.py test_report_bar
The page is the committed one, served by a real server whose change and undo routes are the real clark.changes over a real store in
a temporary folder (fictional data). Laptop widths only: 1400 and 900 px, light and dark. The published file is read from its bytes.
"""
import json
import re
import unittest
from datetime import date, timedelta

from _demo import USER
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

    def coming_friday(self):
        d = date.today()
        return (d + timedelta(days=(4 - d.weekday()) % 7)).isoformat()

    def set_week(self, iso):
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"week_ending": iso})

    def test_view_and_edit_both_have_the_week_ending_date_field_and_the_chip(self):
        """Row 33 (prototype views.js:509): a date input in the bar, in View and in Edit."""
        self.set_week("2031-05-09")
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.show(cdp, w)
                self.assertEqual(p.js("document.querySelector('#week-ending').type"), "date")
                self.assertEqual(p.js("document.querySelector('#week-ending').value"), "2031-05-09")
                self.assertEqual(p.js("document.querySelector('#week-ending').labels[0].textContent.trim()"), "Week ending")
                self.assertEqual(p.js("document.querySelector('#report-state').textContent"), "Draft · not published yet")
                self.assertIsNone(p.js("document.querySelector('#report-hint')"))
                self.assertEqual(p.js("document.querySelectorAll('#report-bar input').length"), 1, "one field, in the bar only")
                p.edit()
                p.until("!!document.querySelector('#report-hint')", "Edit's notes")
                self.assertEqual(p.js("document.querySelector('#week-ending').type"), "date")
                self.assertEqual(p.js("document.querySelector('#week-ending').value"), "2031-05-09")
                self.assertEqual(p.js("document.querySelector('#report-state').textContent"), "Editing · each change saves on its own")
                self.assertEqual(p.js("document.querySelector('#report-hint').textContent"), "Drag to move, + to add a template")

    def test_with_no_week_kept_the_field_shows_the_coming_friday_and_saves_nothing(self):
        """Row 34 (prototype views.js:507, db.js:15): the coming Friday, today when it is a Friday; shown, not saved."""
        self.set_week(None)
        self.assertIsNone(self.week())
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelector('#week-ending').value"), self.coming_friday())
            p.edit()
            p.until("!!document.querySelector('#report-hint')", "Edit")
            self.assertEqual(p.js("document.querySelector('#week-ending').value"), self.coming_friday())
            self.assertIsNone(self.week(), "nothing was saved by looking")
            self.assertEqual([k for k, r in self.sent if r.get("kind") == "projects"], [], "and nothing was sent")

    def test_the_drag_hint_shows_once_not_on_every_entry_to_edit(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.until("!!document.querySelector('#report-hint')", "the hint the first time")
            p.js("document.querySelector('[data-mode=view]').click()")
            p.until("document.querySelector('#report').dataset.mode === 'view'", "View")
            p.edit()
            p.until("!!document.querySelector('#week-ending') && document.querySelector('#report').dataset.mode === 'edit'", "Edit again")
            self.assertIsNone(p.js("document.querySelector('#report-hint')"), "not shown again")

    def test_the_first_time_in_edit_the_first_grip_and_plus_pulse_once(self):
        """Row 35 (prototype views.js:530, app.css:1272): the first section's controls pulse once, and never again in this browser."""
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelectorAll('.sec-ctl.first').length"), 0, "not in View")
            p.edit()
            p.until("!!document.querySelector('.sec-ctl.first')", "the pulse")
            self.assertEqual(p.js("document.querySelectorAll('.sec-ctl.first').length"), 1, "one section's controls only")
            self.assertEqual(p.js("document.querySelector('.sec-ctl.first').closest('.sec') === document.querySelector('.sec')"), True, "the first section")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('.sec-ctl.first')).animationName"), "nudge")
            self.assertEqual(p.js("document.querySelectorAll('.sec-ctl.first .handle, .sec-ctl.first .plus').length"), 2, "the grip and the plus are in it")
            p.until("document.querySelectorAll('.sec-ctl.first').length === 0", "the pulse ends")
            p.js("document.querySelector('[data-mode=view]').click()")
            p.until("document.querySelector('#report').dataset.mode === 'view'", "View")
            p.edit()
            p.until("document.querySelectorAll('.sec-ctl').length > 0", "Edit again")
            self.assertEqual(p.js("document.querySelectorAll('.sec-ctl.first').length"), 0, "once")

    def test_the_pulse_is_left_out_when_the_person_asks_for_less_motion(self):
        with chrome() as cdp:
            p = self.show(cdp)
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
            p.edit()
            p.until("document.querySelectorAll('.sec-ctl').length > 0 && !!document.querySelector('#report-hint')", "Edit")
            self.assertEqual(p.js("document.querySelectorAll('.sec-ctl.first').length"), 0)

    def type_week(self, p, iso):
        p.js("(() => { const e = document.querySelector('#week-ending'); e.focus(); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(e, %s); e.dispatchEvent(new Event('change', { bubbles: true })); })()" % json.dumps(iso))

    def test_a_new_week_is_saved_and_undone_from_view_and_from_edit(self):
        for edit in (False, True):
            with self.subTest(edit=edit), chrome() as cdp:
                self.set_week("2031-05-02")
                p = self.show(cdp)
                if edit:
                    p.edit()
                    p.until("!!document.querySelector('#report-hint') || document.querySelector('#report').dataset.mode === 'edit'", "Edit")
                self.type_week(p, "2031-05-09")
                p.saved()
                self.assertEqual(self.week(), "2031-05-09")
                self.assertEqual(p.toast(), "Week ending changed to 09-05-2031.")
                self.assertEqual(p.js("document.querySelector('#week-ending').value"), "2031-05-09")
                p.js("document.querySelector('[data-undo]').click()")
                p.until("document.querySelector('#week-ending').value === '2031-05-02'", "the date came back")
                self.assertEqual(self.week(), "2031-05-02")

    def test_a_message_from_edit_does_not_follow_the_person_into_view(self):
        self.set_week("2031-05-02")
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.type_week(p, "2031-05-09")
            p.saved()
            p.js("document.querySelector('[data-mode=view]').click()")
            p.until("document.querySelector('#report').dataset.mode === 'view'", "View")
            self.assertEqual(p.js("document.querySelectorAll('.toast').length"), 0)
            self.assertEqual(p.js("document.querySelectorAll('[data-edit-only]').length"), 0, "View has no Edit part, the message included")

    def test_a_cleared_field_keeps_the_old_date(self):
        self.set_week("2031-05-02")
        with chrome() as cdp:
            p = self.show(cdp)
            self.type_week(p, "")
            p.until("document.querySelector('#week-ending').value === '2031-05-02'", "the old day came back")
            self.assertEqual(self.week(), "2031-05-02")
            self.assertEqual([k for k, r in self.sent if r.get("kind") == "projects"], [])

    def test_a_refused_week_puts_the_old_date_back_and_says_why(self):
        self.set_week("2031-05-02")
        self.failure = lambda req: (400, {"ok": False, "message": "The week ending date must be a real date. The old date was kept. Pick a date and try again."})
        with chrome() as cdp:
            p = self.show(cdp)
            self.type_week(p, "2031-05-09")
            p.until("/The old date was kept/.test(document.body.textContent)", "the plain words")
            self.assertEqual(p.js("document.querySelector('#week-ending').value"), "2031-05-02")
            self.assertEqual(self.week(), "2031-05-02")

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
                p.until("!!document.querySelector('#report-hint')", "the notes")
                for sel, r in p.js(script):
                    self.assertGreaterEqual(r, 4.5, sel)

    def test_the_published_file_has_no_bar(self):
        html = (PAGE / "page-view.html").read_text(encoding="utf-8")
        for name in ("report-bar", "week-ending", "rbar-state", "Draft · not published yet"):
            self.assertNotIn(name, html)
        self.assertIsNone(re.search(r"Editing · each change saves", html))


if __name__ == "__main__":
    unittest.main()
