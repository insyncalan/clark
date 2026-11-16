"""Row 1234 piece 4B: the Status tracker control in the Configure panel (Top, Bottom, Off), saved into the section body, at 1400 and 900 px.
Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_tracker_control_1234
"""
import json
import time
import unittest

from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

from _uc_view import put_view

CFG = "document.querySelector('[data-uc-configure]')"


class TrackerControl(Setup):
    def stored(self):
        row = next(r for r in self.store.read("report_sections", "ABC") if r["type"] == "usecases")
        return json.loads(row["body"]) if row["body"] else None

    def wait_tracker(self, want):
        for _ in range(100):
            v = self.stored()
            if v and v.get("tracker") == want:
                return v
            time.sleep(0.1)
        self.fail(f"tracker {want} not saved")

    def open_panel(self, p):
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('#ucAdd')", "Edit")
        p.js(f"{CFG}.click()")
        p.until("!!document.querySelector('[data-uc-tracker]')", "tracker control")

    def pressed(self, p):
        return p.js("[...document.querySelectorAll('[data-uc-tracker] button')].filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.dataset.tracker).join(',')")

    def test_words_and_default(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, None)
                p = self.show(cdp, width)
                self.open_panel(p)
                self.assertEqual(p.js("document.querySelector('#ucCfgT').textContent"), "Status tracker")
                self.assertEqual(p.js("document.querySelector('[data-uc-tracker]').getAttribute('aria-labelledby')"), "ucCfgT", "the group is named by the visible words")
                self.assertFalse(p.js("document.querySelector('[data-uc-tracker]').hasAttribute('aria-label')"), "one name, not two")
                self.assertEqual(p.js("[...document.querySelectorAll('[data-uc-tracker] button')].map(b => b.textContent).join('|')"), "Top|Bottom|Off")
                self.assertEqual(self.pressed(p), "top", "top is the default")
                self.assertTrue(p.js("(r => r.left >= 0 && r.right <= innerWidth)(document.querySelector('#ucCfg').getBoundingClientRect())"), "fits the width")

    def test_each_choice_is_saved_with_the_other_settings_kept(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, {"n": 3, "scroll": True, "tracker": "top"})
                p = self.show(cdp, width)
                self.open_panel(p)
                for pos in ("bottom", "off", "top"):
                    p.js(f"document.querySelector('[data-tracker={pos}]').click()")
                    v = self.wait_tracker(pos)
                    self.assertEqual(v, {"n": 3, "scroll": True, "tracker": pos}, "n and scroll kept, nothing else added")
                    p.until(f"document.querySelector('[data-tracker={pos}]').getAttribute('aria-pressed') === 'true'", "pressed")
                    self.assertEqual(self.pressed(p), pos, "exactly one is pressed")

    def test_a_later_scroll_change_keeps_the_tracker_choice(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, {"n": 3, "scroll": False, "tracker": "bottom"})
                p = self.show(cdp, width)
                self.open_panel(p)
                p.js("document.querySelector('#ucCfgS').click()")
                for _ in range(100):
                    v = self.stored()
                    if v and v.get("scroll") is True:
                        break
                    time.sleep(0.1)
                self.assertEqual(v, {"n": 3, "scroll": True, "tracker": "bottom"}, "the tracker kept when the switch is changed")

    def test_off_is_saved_drawn_and_read_back(self):
        put_view(self, None)
        with chrome() as cdp:
            p = self.show(cdp)
            self.open_panel(p)
            p.js("document.querySelector('[data-tracker=off]').click()")
            self.wait_tracker("off")
            p.reload()
            self.open_panel(p)
            self.assertEqual(self.pressed(p), "off", "read back from the body after a reload")

    def test_a_tracker_save_is_recorded_as_made_in_the_table(self):
        from clark import history
        put_view(self, None)
        with chrome() as cdp:
            p = self.show(cdp)
            self.open_panel(p)
            p.js("document.querySelector('[data-tracker=bottom]').click()")
            self.wait_tracker("bottom")
            ref = next(r["id"] for r in self.store.read("report_sections", "ABC") if r["type"] == "usecases")
            rows = self.store.con.execute("SELECT place FROM item_events WHERE item_id = ? ORDER BY event_id DESC", (ref,)).fetchall()
            self.assertTrue(rows, "the save is in the history")
            self.assertEqual(rows[0][0], "cell")
            self.assertEqual(history.how_text("page", rows[0][0], None), history.HOW_TABLE)

    def test_an_unknown_stored_value_shows_the_default_pressed(self):
        put_view(self, {"n": 5, "scroll": False, "tracker": "sideways"})
        with chrome() as cdp:
            p = self.show(cdp)
            self.open_panel(p)
            self.assertEqual(self.pressed(p), "top")


if __name__ == "__main__":
    unittest.main()
