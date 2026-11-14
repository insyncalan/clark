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
        return (d + timedelta(days=(4 - d.weekday()) % 7)).strftime("%d-%m-%Y")

    def set_week(self, iso):
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"week_ending": iso})

    def test_view_and_edit_both_have_the_week_ending_date_button_and_no_chip(self):
        """Row 33, changed by item 1177: the week ending is the header's date button (never a box, never the browser's calendar), in View and in Edit; the bar keeps
        View | Edit and, in Edit, the drag hint; the Draft and Editing words are in the profile menu now (test_publish_dialog)."""
        self.set_week("2031-05-09")
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.show(cdp, w)
                self.assertEqual(p.js("document.querySelector('.hdr-date').tagName"), "BUTTON", "a button, never a native date input")
                self.assertEqual(p.js("document.querySelector('.hdr-date').textContent"), "Week ending 09-05-2031")
                self.assertEqual(p.js("document.querySelectorAll('#report-state, .rbar-state').length"), 0, "the chip left the bar")
                self.assertIsNone(p.js("document.querySelector('#report-hint')"))
                self.assertEqual(p.js("document.querySelectorAll('#report-bar input').length"), 0, "no field in the bar")
                p.edit()
                p.until("!!document.querySelector('#report-hint')", "Edit's notes")
                self.assertEqual(p.js("document.querySelector('.hdr-date').textContent"), "Week ending 09-05-2031")
                self.assertEqual(p.js("document.querySelectorAll('#report-state, .rbar-state').length"), 0)
                self.assertEqual(p.js("document.querySelector('#report-hint').textContent"), "Drag to move, + to add a template")

    def test_with_no_week_kept_the_field_shows_the_coming_friday_and_saves_nothing(self):
        """Row 34 (prototype views.js:507, db.js:15): the coming Friday, today when it is a Friday; shown, not saved."""
        self.set_week(None)
        self.assertIsNone(self.week())
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelector('.hdr-date').textContent"), "Week ending " + self.coming_friday())
            p.edit()
            p.until("!!document.querySelector('#report-hint')", "Edit")
            self.assertEqual(p.js("document.querySelector('.hdr-date').textContent"), "Week ending " + self.coming_friday())
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
            p.until("!!document.querySelector('.hdr-date') && document.querySelector('#report').dataset.mode === 'edit'", "Edit again")
            self.assertIsNone(p.js("document.querySelector('#report-hint')"), "not shown again")

    def type_week(self, p, text):
        """Item 1177: the week is picked from the header date's calendar (a DD-MM-YYYY day in the month it opens on), as a person does; it saves like a typed day did."""
        d, m, y = text.split("-")
        p.js("document.querySelector('#week-ending-pick').click()")
        p.until("!!document.querySelector('.cpop.cdate')", "the calendar opened")
        p.js("document.querySelector('.cpop [data-day=\"%s-%s-%s\"]').click()" % (y, m, d))

    def test_a_new_week_is_saved_and_undone_from_view_and_from_edit(self):
        for edit in (False, True):
            with self.subTest(edit=edit), chrome() as cdp:
                self.set_week("2031-05-02")
                p = self.show(cdp)
                if edit:
                    p.edit()
                    p.until("!!document.querySelector('#report-hint') || document.querySelector('#report').dataset.mode === 'edit'", "Edit")
                self.type_week(p, "09-05-2031")
                p.saved()
                self.assertEqual(self.week(), "2031-05-09")
                self.assertEqual(p.toast(), "Week ending changed to 09-05-2031.")
                self.assertEqual(p.js("document.querySelector('.hdr-date').textContent"), "Week ending 09-05-2031")
                p.js("document.querySelector('[data-undo]').click()")
                p.until("document.querySelector('.hdr-date').textContent === 'Week ending 02-05-2031'", "the date came back")
                self.assertEqual(self.week(), "2031-05-02")

    def test_a_message_from_edit_does_not_follow_the_person_into_view(self):
        self.set_week("2031-05-02")
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.type_week(p, "09-05-2031")
            p.saved()
            p.js("document.querySelector('[data-mode=view]').click()")
            p.until("document.querySelector('#report').dataset.mode === 'view'", "View")
            self.assertEqual(p.js("document.querySelectorAll('.toast').length"), 0)
            self.assertEqual(p.js("document.querySelectorAll('[data-edit-only]').length"), 0, "View has no Edit part, the message included")

    def test_a_message_from_the_bar_shows_in_view_with_its_undo(self):
        self.set_week("2031-05-02")
        with chrome() as cdp:
            p = self.show(cdp)
            self.type_week(p, "09-05-2031")
            p.until("!!document.querySelector('.toast [data-undo]')", "the message and its Undo in View")
            self.assertEqual(p.js("document.querySelectorAll('.toasts').length"), 1, "one live region")
            self.assertEqual(p.js("document.querySelector('.toast-text').textContent"), "Week ending changed to 09-05-2031.")
            self.assertEqual(p.js("document.querySelector('.toasts').getAttribute('role')"), "status")

    def test_the_undo_of_a_change_made_in_edit_is_still_there_after_a_trip_to_view(self):
        """Edit, View, Edit: a message from Edit is not drawn in View, and is back with its Undo when Edit is entered again."""
        self.set_week("2031-05-02")
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.type_week(p, "09-05-2031")
            p.saved()
            p.js("document.querySelector('[data-mode=view]').click()")
            p.until("document.querySelector('#report').dataset.mode === 'view'", "View")
            self.assertEqual(p.js("document.querySelectorAll('.toast').length"), 0)
            p.edit()
            p.until("!!document.querySelector('.toast [data-undo]')", "the Undo is back")
            p.js("document.querySelector('[data-undo]').click()")
            p.until("document.querySelector('.hdr-date').textContent === 'Week ending 02-05-2031'", "the date came back")
            self.assertEqual(self.week(), "2031-05-02")

    def test_a_typed_entry_that_is_not_a_day_keeps_the_old_date_and_says_so(self):
        """Item 1177: nothing is typed any more, so a bad entry cannot be made: the header date is a button, the calendar offers only real days, nothing is sent."""
        self.set_week("2031-05-02")
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelectorAll('.top input, #report-bar input').length"), 0, "no box to type in")
            p.js("document.querySelector('#week-ending-pick').click()")
            p.until("!!document.querySelector('.cpop.cdate')", "the calendar opened")
            self.assertEqual(p.js("document.querySelectorAll('.cpop [data-day=\"2031-02-30\"]').length"), 0, "no day that is not one")
            self.assertEqual(self.week(), "2031-05-02")
            self.assertEqual([k for k, r in self.sent if r.get("kind") == "projects"], [])

    def test_enter_on_the_friday_shown_saves_it_and_leaving_the_box_does_not(self):
        """Item 1177: with no week kept, the Friday is shown and not saved; choosing the calendar's Friday choice saves it."""
        self.set_week(None)
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertIsNone(self.week(), "looking saves nothing")
            p.js("document.querySelector('#week-ending-pick').click()")
            p.until("!!document.querySelector('.cpop.cdate')", "the calendar opened")
            p.js("document.querySelector('.cpop [data-quick]').click()")
            p.saved()
            self.assertEqual(self.week(), (date.today() + timedelta(days=(4 - date.today().weekday()) % 7)).isoformat())
            self.assertEqual(p.toast(), "Week ending changed to %s." % self.coming_friday())

    def test_a_cleared_field_keeps_the_old_date(self):
        """Item 1177: the week cannot be cleared: the calendar's one quick choice is Friday, there is no No date."""
        self.set_week("2031-05-02")
        with chrome() as cdp:
            p = self.show(cdp)
            p.js("document.querySelector('#week-ending-pick').click()")
            p.until("!!document.querySelector('.cpop.cdate')", "the calendar opened")
            self.assertEqual(p.js("[...document.querySelectorAll('.cpop [data-quick]')].map((e) => e.dataset.quick === '')"), [False], "no choice without a day")
            self.assertEqual(self.week(), "2031-05-02")
            self.assertEqual([k for k, r in self.sent if r.get("kind") == "projects"], [])

    def test_a_refused_week_puts_the_old_date_back_and_says_why(self):
        self.set_week("2031-05-02")
        self.failure = lambda req: (400, {"ok": False, "message": "The week ending date must be a real date. The old date was kept. Pick a date and try again."})
        with chrome() as cdp:
            p = self.show(cdp)
            self.type_week(p, "09-05-2031")
            p.until("/so the old week ending date was kept/.test((document.querySelector('.toast-text') || {}).textContent || '')", "the plain words")
            self.assertNotIn("Pick a date and try again", p.js("document.querySelector('.toast-text').textContent"), "the server's own words are never shown")
            self.assertEqual(p.js("document.querySelector('.hdr-date').textContent"), "Week ending 02-05-2031")
            self.assertEqual(self.week(), "2031-05-02")

    def test_a_typed_weekend_day_names_the_coming_friday_like_the_boards_this_week(self):
        # #570: a Saturday or Sunday rolls forward (fridayOnOrAfter). 10-05-2031 is a Saturday: the Friday offered is 16-05-2031.
        for bad, friday in (("10-05-2031", "16-05-2031"), ("11-05-2031", "16-05-2031")):
            with self.subTest(bad=bad), chrome() as cdp:
                self.set_week("2031-05-02")
                p = self.show(cdp)
                p.edit()
                self.type_week(p, bad)
                p.until("/Pick Friday %s/.test(document.body.textContent)" % friday, "the coming Friday")

    def test_the_bar_takes_its_friday_from_the_boards_helper(self):
        src = (PAGE / "src" / "edit" / "ReportBar.jsx").read_text(encoding="utf-8")
        self.assertIn("weekEndOf", src)
        self.assertNotIn("getUTCDay() || 7", src)

    def test_a_typed_day_that_is_not_a_friday_keeps_the_old_date_and_names_the_friday(self):
        # #570: Friday is the week end everywhere. 05-05-2031 is a Monday; the Friday of its week is 09-05-2031.
        with chrome() as cdp:
            self.set_week("2031-05-02")
            p = self.show(cdp)
            p.edit()
            before = self.week()
            shown = "Week ending " + "-".join(reversed(before.split("-")))
            self.type_week(p, "05-05-2031")
            p.until("/Pick Friday 09-05-2031/.test(document.body.textContent)", "the plain words")
            self.assertIn("The old week ending date was kept.", p.js("document.body.textContent"))
            self.assertEqual(p.js("document.querySelector('.hdr-date').textContent"), shown)
            self.assertEqual(self.week(), before)

    def test_the_route_refuses_a_real_day_that_is_not_a_friday(self):
        req = {"project": "ABC", "kind": "projects", "op": "update", "changes": {"week_ending": "2031-05-05"}}
        status, _, raw = self.s.api("POST", "/api/change", json.dumps(req).encode("utf-8"))
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(raw).get("message"), "Week ending is a Friday. Pick Friday 09-05-2031.")

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
          return ['.hdr-date', '.hdr-project', '#report-hint'].map((sel) => {
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


class HookOrder(unittest.TestCase):
    """#534: the bar returns null while the project has not loaded, so a hook after that return would be called on some renders and not
    others (rules of hooks). Every hook sits above the first return, so the loading render and the loaded render call the same ones."""

    def test_no_hook_comes_after_the_early_return_null(self):
        src = (PAGE / "src" / "edit" / "ReportBar.jsx").read_text(encoding="utf-8")
        body = src[src.index("export function ReportBar()"):]
        early = body.index("return null")
        self.assertGreater(early, 0)
        hooks = list(re.finditer(r"\buse[A-Z]\w*\(", body))
        self.assertTrue(hooks, "the bar still has its effects")
        for h in hooks:
            self.assertLess(h.start(), early, f"{h.group()} is called after the early return null")


if __name__ == "__main__":
    unittest.main()
