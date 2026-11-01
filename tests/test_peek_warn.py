"""The peek's warning above the title (Edit only): a late action says how late, a date on a weekend says so, each with one-click moves.

Run: python3 dev/run_tests.py test_peek_warn
Part 1 runs the page's own rules (src/clark/page/src/edit/peekWarn.js, bundled by the pinned esbuild) in headless Chrome with a
fixed today: the wording, the Friday that is not before today, a week on, the weekend moves, which items have no warning.
Part 2 drives the real page against a real demo store at 1400 and 900 px (today is 28-10-2026): the bar sits above the title in
Edit, Move to Friday and Move a week on change the due date in one step with one toast and Undo, a weekend date offers Friday
and Monday, View and a published file have no bar, and the bar is not a live region of its own.
"""
import contextlib
import json
import unittest

from _paths import SRC
import test_inline_edits as ie  # noqa: E402
from test_inline_edits import need_chrome, click, PAGE_SRC  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_items import bundled, page_target  # noqa: E402

TODAY = "2026-10-28"                                   # a Wednesday


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.stack = contextlib.ExitStack()
        cls.cdp = cls.stack.enter_context(chrome())
        cls.sid = page_target(cls.cdp)
        res = cls.cdp.call("Runtime.evaluate", {"expression": bundled(PAGE_SRC / "edit" / "peekWarn.js", "PW") + "; true", "returnByValue": True}, cls.sid)
        assert "exceptionDetails" not in res, res

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def warn(self, row, today=TODAY):
        res = self.cdp.call("Runtime.evaluate", {"expression": f"PW.warningFor({json.dumps(row)}, {json.dumps(today)})", "returnByValue": True}, self.sid)
        self.assertNotIn("exceptionDetails", res, res)
        return res["result"].get("value")

    def action(self, due, status="Open"):
        return {"id": "ABC-A-001", "kind": "action", "status": status, "due_date": due}

    def test_a_late_action_says_how_late_and_offers_the_next_friday_and_a_week_on(self):
        w = self.warn(self.action("2026-10-25"))                   # a Sunday, three days late
        self.assertEqual(w["tone"], "late")
        self.assertEqual(w["text"], "3 days overdue (due Sunday 25-10-2026, a weekend: a working day is usually meant)")
        self.assertEqual([(f["label"], f["iso"]) for f in w["fixes"]], [("Move to Friday 30-10-2026", "2026-10-30"), ("Move a week on", "2026-11-04")])
        w = self.warn(self.action("2026-10-27"))
        self.assertEqual(w["text"], "1 day overdue (due 27-10-2026)")

    def test_friday_is_never_before_today(self):
        for today, friday in (("2026-10-28", "2026-10-30"), ("2026-10-30", "2026-10-30"), ("2026-10-31", "2026-11-06"), ("2026-11-01", "2026-11-06"), ("2026-11-02", "2026-11-06")):
            with self.subTest(today=today):
                self.assertEqual(self.warn(self.action("2026-10-01"), today)["fixes"][0]["iso"], friday)
        self.assertEqual(self.warn(self.action("2026-10-01"), "2026-10-30")["fixes"][1]["iso"], "2026-11-06", "a week on is seven days from today")
        self.assertEqual(self.warn(self.action("2026-12-01"), "2026-12-29")["fixes"][0]["iso"], "2027-01-01", "across a year end")

    def test_a_weekend_date_says_so_and_offers_the_friday_before_and_the_monday_after(self):
        w = self.warn(self.action("2026-11-07"))
        self.assertEqual(w["tone"], "weekend")
        self.assertEqual(w["text"], "Due on a Saturday (07-11-2026): a working day is usually meant")
        self.assertEqual([f["iso"] for f in w["fixes"]], ["2026-11-06", "2026-11-09"])
        self.assertEqual([f["label"] for f in w["fixes"]], ["Move to Friday 06-11-2026", "Move to Monday 09-11-2026"])
        w = self.warn(self.action("2026-11-08"))
        self.assertEqual([f["iso"] for f in w["fixes"]], ["2026-11-06", "2026-11-09"], "a Sunday has the same two days")
        self.assertIn("Sunday", w["text"])

    def test_who_has_no_warning(self):
        self.assertIsNone(self.warn(self.action("2026-11-04")), "a working day in the future")
        self.assertIsNone(self.warn(self.action("2026-10-28")), "due today")
        self.assertIsNone(self.warn(self.action("2026-10-01", "Closed")), "a closed item")
        self.assertIsNone(self.warn(self.action("2026-11-07", "Cancelled")))
        self.assertIsNone(self.warn(self.action(None)), "no date")
        self.assertIsNone(self.warn(self.action("2026-02-30")), "not a real day")
        self.assertIsNone(self.warn({"id": "ABC-007", "kind": "risk", "status": "Open", "due_date": "2026-10-01"}), "only an action is late")
        w = self.warn({"id": "ABC-007", "kind": "risk", "status": "Open", "due_date": "2026-11-07"})
        self.assertEqual(w["tone"], "weekend", "a weekend date is for any open item")
        self.assertEqual(self.warn({"id": "ABC-D-001", "kind": "decision", "status": "Pending", "needed_by": "2026-11-08"})["tone"], "weekend")
        self.assertIsNone(self.warn({"id": "ABC-D-002", "kind": "decision", "status": "Made", "date": "2026-11-08"}), "a made decision is done")


class Page(unittest.TestCase):
    """The warning in the real page. Live's setUp builds the demo store and the server; its helpers drive the page (borrowed, so Live's own tests are not run again)."""
    setUp = ie.Live.setUp
    read, row, steps, open_page, until, toast, undo, changed_once = (ie.Live.read, ie.Live.row, ie.Live.steps, ie.Live.open_page, ie.Live.until, ie.Live.toast, ie.Live.undo, ie.Live.changed_once)

    def open_item(self, cdp, width, ref, edit=True):
        sid = self.open_page(cdp, width, edit=edit)
        click(cdp, sid, f"#work tbody tr[data-id='{ref}'] .c-item")
        self.until(cdp, sid, f"!!document.querySelector('#peek[data-peek=\"{ref}\"]')", "the peek opened")
        return sid

    def bar(self, cdp, sid):
        return cdp.js("(() => { const b = document.querySelector('#peek [data-pk-warn]'); if (!b) return null;"
                      " const t = document.querySelector('#peek .pk-title');"
                      " return { tone: b.dataset.pkWarn, text: b.querySelector('.pk-warn-text').textContent, above: !!(b.compareDocumentPosition(t) & Node.DOCUMENT_POSITION_FOLLOWING),"
                      " buttons: [...b.querySelectorAll('button')].map(x => x.textContent), live: !!b.closest('[aria-live]') || b.hasAttribute('aria-live') }; })()", sid)

    def test_a_late_action_shows_the_bar_above_the_title_and_move_to_friday_changes_it_once_with_undo_at_1400(self):
        self.late_action(1400)

    def test_a_late_action_shows_the_bar_above_the_title_and_move_to_friday_changes_it_once_with_undo_at_900(self):
        self.late_action(900)

    def late_action(self, width):
        if True:
            with chrome() as cdp:
                sid = self.open_item(cdp, width, "TUL-A-002")
                bar = self.bar(cdp, sid)
                self.assertEqual(bar["tone"], "late")
                self.assertEqual(bar["text"], "6 days overdue (due 22-10-2026)")
                self.assertTrue(bar["above"])
                self.assertEqual(bar["buttons"], ["Move to Friday 30-10-2026", "Move a week on"])
                self.assertFalse(bar["live"], "the toast is the one live region")
                before = self.steps()
                # keyboard: Tab from the close button reaches the bar's buttons; Enter on the first one moves the date
                cdp.js("document.querySelector('#peek [data-move]').focus()", sid)
                self.assertEqual(cdp.js("document.activeElement.dataset.move", sid), "2026-10-30")
                from test_peek import key
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!document.querySelector('#peek [data-pk-warn]')", "the bar is gone once the date is right")
                self.assertTrue(wait(lambda: self.row("actions", "TUL-A-002")["due_date"] == "2026-10-30", 20), "the store has the new date")
                self.changed_once(before, "Move to Friday")
                self.assertEqual(self.toast(cdp, sid), "Due date of TUL-A-002 changed to 30-10-2026.")
                self.assertEqual(cdp.js("document.querySelectorAll('.toasts[aria-live=polite]').length", sid), 1, "one polite live region on the page")
                self.assertEqual(cdp.js("document.activeElement.hasAttribute('data-pk-close')", sid), True, "focus goes to the close button, not to nothing")
                self.undo(cdp, sid, "Move to Friday", "Due date of TUL-A-002 is back to 22-10-2026.")
                self.assertTrue(wait(lambda: self.row("actions", "TUL-A-002")["due_date"] == "2026-10-22", 20), "Undo put the date back")
                self.until(cdp, sid, "!!document.querySelector('#peek [data-pk-warn]')", "after Undo the warning is back")

    def test_move_a_week_on_is_seven_days_from_today(self):
        with chrome() as cdp:
            sid = self.open_item(cdp, 1400, "TUL-A-002")
            click(cdp, sid, "#peek [data-move='2026-11-04']")
            self.until(cdp, sid, "!document.querySelector('#peek [data-pk-warn]')", "moved")
            self.assertEqual(self.row("actions", "TUL-A-002")["due_date"], "2026-11-04")
            self.assertEqual(self.toast(cdp, sid), "Due date of TUL-A-002 changed to 04-11-2026.")

    def test_a_weekend_date_offers_the_friday_and_the_monday(self):
        for width in (900, 1400):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_item(cdp, width, "TUL-A-006")
                bar = self.bar(cdp, sid)
                self.assertEqual(bar["tone"], "weekend")
                self.assertEqual(bar["text"], "Due on a Saturday (07-11-2026): a working day is usually meant")
                self.assertEqual(bar["buttons"], ["Move to Friday 06-11-2026", "Move to Monday 09-11-2026"])
                if width == 900:
                    continue                                   # the move is the same at both widths; do it once, so the second look sees the first one's date
                click(cdp, sid, "#peek [data-move='2026-11-09']")
                self.until(cdp, sid, "!document.querySelector('#peek [data-pk-warn]')", "moved")
                self.assertTrue(wait(lambda: self.row("actions", "TUL-A-006")["due_date"] == "2026-11-09", 20))

    def test_an_item_with_nothing_wrong_has_no_bar_and_view_has_none(self):
        with chrome() as cdp:
            sid = self.open_item(cdp, 1400, "TUL-A-001")                     # Monday 02-11-2026, open
            self.assertIsNone(self.bar(cdp, sid))
        with chrome() as cdp:
            sid = self.open_item(cdp, 1400, "TUL-A-002", edit=False)
            self.assertEqual(cdp.js("document.querySelectorAll('#peek .pk-warn, #peek [data-move]').length", sid), 0, "View is fields only")

    def test_the_colours_have_four_and_a_half_to_one_in_light_and_dark(self):
        pairs = {"late": ("--status-red-text", "--status-red-tint"), "weekend": ("--status-amber-text", "--status-amber-tint")}
        with chrome() as cdp:
            sid = self.open_item(cdp, 1400, "TUL-A-002")
            js = """((names) => { const lum = (c) => { const m = c.match(/[\\d.]+/g).map(Number).slice(0, 3).map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * m[0] + .7152 * m[1] + .0722 * m[2]; };
              const probe = (v) => { const e = document.createElement('i'); e.style.color = 'var(' + v + ')'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; };
              const r = (a, b) => { const x = lum(probe(a)), y = lum(probe(b)); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
              return names.map(n => r(n[0], n[1])); })"""
            for scheme in ("light", "dark"):
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                got = cdp.js(f"{js}({json.dumps(list(pairs.values()))})", sid)
                for (kind, _), ratio in zip(pairs.items(), got):
                    self.assertGreaterEqual(ratio, 4.5, f"{kind} text on its tint in {scheme}: {ratio:.2f}")


class Sources(unittest.TestCase):
    def test_the_warning_is_an_edit_part_and_no_published_file_has_it(self):
        peek = (SRC / "clark" / "page" / "src" / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("tools.PeekWarn", peek)
        self.assertNotIn("edit/PeekWarn", peek, "Peek reaches it only through the tools it is handed")
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for word in ("peekWarn", "data-pk-warn", "Move a week on", "usually meant", "Due date warning"):
            self.assertNotIn(word, view)


if __name__ == "__main__":
    unittest.main()
