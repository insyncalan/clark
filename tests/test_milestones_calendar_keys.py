"""#912: the Milestones page's Calendar day and chip key checks, the second half of what test_milestones_calendar.py holds.

Run: python3 dev/run_tests.py test_milestones_calendar_keys
The same tests as before, unchanged, on the real-browser helpers (BrowserBase in test_milestones_page.py).
"""
import time
import unittest

from test_milestones_page import BrowserBase
from test_server import chrome, wait


class CalendarDayKeys(BrowserBase, unittest.TestCase):
    def test_left_right_up_and_down_move_a_day_or_a_week_and_the_tab_stop_goes_with_the_focus(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            for scale in ("month", "week", "quarter"):
                self.scale(cdp, sid, scale)
                for name, want in (("ArrowRight", "2026-10-29"), ("ArrowLeft", "2026-10-27"), ("ArrowUp", "2026-10-21"), ("ArrowDown", "2026-11-04")):
                    cdp.js("document.querySelector('[data-cal=\"0\"]').click()", sid)      # Today: the period holding it is drawn again
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal-d.today')", sid)))
                    cdp.js("document.querySelector('.cal-d.today').focus()", sid)
                    self.assertEqual(self.where(cdp, sid), "2026-10-28")
                    self.press(cdp, sid, name)
                    self.assertTrue(wait(lambda: self.where(cdp, sid) == want), f"{scale}: {name} from today lands on {want}, got {self.where(cdp, sid)}")
                    self.assertEqual(self.stops(cdp, sid), [want], f"{scale}: {name} - the tab stop is the day that has focus")
    def test_an_arrow_that_leaves_the_period_goes_on_into_the_next_or_earlier_one(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            self.focus_day(cdp, sid, "2026-10-31")
            self.press(cdp, sid, "ArrowRight")
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "November 2026"), "Right past the month end shows the next month")
            self.assertTrue(wait(lambda: self.where(cdp, sid) == "2026-11-01"), self.where(cdp, sid))
            self.press(cdp, sid, "ArrowLeft")
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "October 2026"), "Left before the month start shows the month before")
            self.assertTrue(wait(lambda: self.where(cdp, sid) == "2026-10-31"), self.where(cdp, sid))
            self.scale(cdp, sid, "week")
            self.assertEqual(self.title(cdp, sid), "Week of 26-10-2026")
            self.focus_day(cdp, sid, "2026-11-01")
            self.press(cdp, sid, "ArrowRight")
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "Week of 02-11-2026"), "Right from a Sunday shows the next week")
            self.assertTrue(wait(lambda: self.where(cdp, sid) == "2026-11-02"), self.where(cdp, sid))
            self.press(cdp, sid, "ArrowUp")
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "Week of 26-10-2026"), "Up a week shows the week before")
            self.assertTrue(wait(lambda: self.where(cdp, sid) == "2026-10-26"), self.where(cdp, sid))
            self.scale(cdp, sid, "quarter")
            self.focus_day(cdp, sid, "2026-12-31")
            self.press(cdp, sid, "ArrowRight")
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "Q1 2027"), "Right past the quarter end shows the next quarter")
            self.assertTrue(wait(lambda: self.where(cdp, sid) == "2027-01-01"), self.where(cdp, sid))
    def test_arrows_on_a_button_a_chip_or_with_a_modifier_do_not_move_a_day_or_a_period(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            before = self.title(cdp, sid)
            self.press(cdp, sid, "ArrowRight", target="[data-cal=\"1\"]")
            self.press(cdp, sid, "ArrowRight", target="[data-scale-b=week]")
            self.press(cdp, sid, "ArrowDown", target=".cal-ms")
            cdp.js("document.querySelector('.cal-d.today').focus()", sid)
            self.press(cdp, sid, "ArrowRight", shift=True)
            time.sleep(0.2)
            self.assertEqual(self.title(cdp, sid), before)
            self.assertEqual(self.stops(cdp, sid), ["2026-10-28"], "none of those moved the tab stop")
            self.assertEqual(self.scale_now(cdp, sid), "month", "no key switches the scale; its three buttons do (the prototype has no such key)")
    def test_enter_on_a_day_with_milestones_goes_to_its_first_chip_and_on_an_empty_day_does_nothing(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            iso = self.day_with_a_chip(cdp, sid)
            self.assertTrue(iso, "the demo month holds a milestone")
            self.focus_day(cdp, sid, iso)
            self.press(cdp, sid, "Enter")
            self.assertEqual(cdp.js("(() => { const a = document.activeElement; return [a.tagName, a.classList.contains('cal-ms'), a === document.querySelector(`.cal-d[data-d='%s'] .cal-ms`)]; })()" % iso, sid),
                             ["BUTTON", True, True], "the first chip of that day has focus")
            empty = cdp.js("[...document.querySelectorAll('.cal-d[data-d]')].find(d => !d.querySelector('.cal-ms')).dataset.d", sid)
            self.focus_day(cdp, sid, empty)
            self.press(cdp, sid, "Enter")
            self.assertEqual(self.where(cdp, sid), empty, "Enter on an empty day leaves focus where it is")
    def test_enter_or_space_on_a_chip_opens_it_and_esc_closes_it(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            iso = self.day_with_a_chip(cdp, sid)
            for key, code, vk, text in (("Enter", "Enter", 13, "\r"), (" ", "Space", 32, " ")):
                cdp.js(f"document.querySelector('.cal-d[data-d=\"{iso}\"] button.cal-ms').focus()", sid)
                self.real_key(cdp, sid, key, code, vk, text)
                self.assertTrue(wait(lambda: cdp.js("!!document.getElementById('peek')", sid)), f"{code} on a chip opens its peek")
                self.real_key(cdp, sid, "Escape", "Escape", 27)
                self.assertTrue(wait(lambda: not cdp.js("!!document.getElementById('peek')", sid)), "Esc closes the peek")
    def test_shift_tab_or_esc_on_a_chip_goes_back_to_its_day_but_with_a_peek_open_esc_closes_the_peek(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            iso = self.day_with_a_chip(cdp, sid)
            chip = f"document.querySelector('.cal-d[data-d=\"{iso}\"] button.cal-ms')"
            cdp.js(f"{chip}.focus()", sid)
            self.press(cdp, sid, "Tab", shift=True)
            self.assertEqual(self.where(cdp, sid), iso, "Shift+Tab goes back to the day the chip sits in")
            self.assertEqual(self.stops(cdp, sid), [iso])
            cdp.js(f"{chip}.focus()", sid)
            self.press(cdp, sid, "Escape")
            self.assertEqual(self.where(cdp, sid), iso, "Esc, with no peek open, goes back to the day")
            self.assertFalse(cdp.js("!!document.getElementById('peek')", sid))
            cdp.js(f"{chip}.click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.getElementById('peek')", sid)))
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-close')", sid)), "the peek has taken focus, so its own keys are wired")
            stayed = cdp.js(f"""(() => {{ const c = {chip}; c.focus();
                c.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Escape', bubbles: true, cancelable: true}}));
                return document.activeElement === c; }})()""", sid)     # read in the same instant: the peek closes a moment later
            self.assertTrue(stayed, "with a peek open, Esc leaves the chip alone and does not jump to the day")
            self.assertTrue(wait(lambda: not cdp.js("!!document.getElementById('peek')", sid)), "with a peek open, Esc closes the peek")
    def test_the_days_keys_work_by_real_key_presses_with_a_visible_ring_at_1400_and_900_px_light_and_dark(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.view(cdp, width, theme)
                    cdp.js("document.querySelector('.cal').focus()", sid)
                    for _ in range(60):                       # a real Tab: the first day is the tab stop after the bar's buttons
                        if cdp.js("document.activeElement.classList.contains('cal-d')", sid):
                            break
                        self.real_key(cdp, sid, "Tab", "Tab", 9)
                    self.assertEqual(self.where(cdp, sid), "2026-10-28", "Tab reaches today, the one tab stop")
                    ring = cdp.js("""(() => { const s = getComputedStyle(document.activeElement);
                        return [document.activeElement.matches(':focus-visible'), s.outlineStyle, parseFloat(s.outlineWidth), s.outlineColor]; })()""", sid)
                    self.assertTrue(ring[0], "focus-visible matches")
                    self.assertEqual(ring[1], "solid")
                    self.assertGreaterEqual(ring[2], 2)
                    self.assertNotIn(ring[3], ("rgba(0, 0, 0, 0)", "transparent"))
                    for key, want in (("ArrowRight", "2026-10-29"), ("ArrowDown", "2026-11-05"), ("ArrowLeft", "2026-11-04"), ("ArrowUp", "2026-10-28")):
                        self.real_key(cdp, sid, key, key, {"ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40}[key])
                        self.assertTrue(wait(lambda: self.where(cdp, sid) == want), f"{key} gives {want}, got {self.where(cdp, sid)}")
    def test_a_slipped_milestone_also_shows_on_its_expected_day_in_the_calendar(self):
        slipped = [r for r in self.expected("MOSS") if r["marks"]["ghost"]]
        self.assertTrue(slipped)
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, "#milestones&p=MOSS")
            cdp.js("document.querySelector('[data-msvb=cal]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal')", sid)))
            for r in slipped:
                day = r["marks"]["ghost"]["date"]
                cdp.js("document.querySelector('[data-cal=\"0\"]').click()", sid)
                for _ in range(10):
                    if cdp.js(f"!!document.querySelector('[data-d=\"{day}\"]')", sid):
                        break
                    cdp.js("document.querySelector('[data-cal=\"1\"]').click()", sid)
                    time.sleep(0.2)
                got = cdp.js(f"[...document.querySelectorAll('[data-d=\"{day}\"] .cal-ms.ghost')].map(c => c.dataset.ms)", sid)
                self.assertIn(r["id"], got, f"{r['id']} on its expected day")

    def test_focus_stays_in_the_calendar_after_a_move_a_quarter_month_or_go_to_today(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.view(cdp, width, theme)
                    cdp.js("document.querySelector('.cal').focus()", sid)
                    for name in ("PageDown", "PageDown", "PageUp"):
                        self.key(cdp, sid, name)
                        time.sleep(0.15)
                        self.assertEqual(self.active(cdp, sid), "cal", f"{name} keeps focus on the calendar")
                    cdp.js("document.querySelector('[data-scale-b=quarter]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('.cal').dataset.scale", sid) == "quarter"))
                    cdp.js("document.querySelector('.cal-qm').focus()", sid)
                    cdp.js("document.querySelector('.cal-qm').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('.cal').dataset.scale", sid) == "month"))
                    time.sleep(0.2)
                    self.assertEqual(self.active(cdp, sid), "cal", "a Quarter month click keeps focus on the calendar")
                    self.keys(cdp, sid, "PageDown", 300)
                    cdp.js("document.querySelector('[data-scale-b=quarter]').click()", sid)
                    self.keys(cdp, sid, "PageDown", 300)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-cal-home]')", sid)))
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-cal-home], [data-cal-empty] button').length", sid), 1, "one Go to today button")
                    cdp.js("document.querySelector('[data-cal-home]').focus()", sid)
                    cdp.js("document.querySelector('[data-cal-home]').click()", sid)
                    self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[data-cal-far]')", sid)))
                    time.sleep(0.2)
                    self.assertEqual(self.active(cdp, sid), "cal", "Go to today keeps focus on the calendar")
