"""Row 1264 slice 4: killer tests for the mutation review (S4). Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_edit_1264_killers
"""
import json
import unittest

from test_report_editor import ALT, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_tpl_glance_edit_1264 import GlanceEdit


class Killers(GlanceEdit):
    def alt(self, p, key, arrow, vk):
        p.js(f"document.querySelector('{self.sel(f'[data-tile={key}] [data-tile-grip]')}').focus()")
        p.key(arrow, ALT, code=arrow, vk=vk)

    def order_is(self, p, want):
        p.until(f"JSON.stringify([...document.querySelectorAll('{self.sel('.glance > .tcell')}')].map(e => e.dataset.tile)) === JSON.stringify({json.dumps(want)})", "order")

    def test_K1_no_colour_is_stored_and_read_back_as_the_checked_item(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.menu(p, "risks")
            p.until("!!document.querySelector('.tilemenu')", "menu")
            p.js("document.querySelector('.tilemenu [data-outline=N]').click()")
            self.assertTrue(wait(lambda: self.body().get("builtin") == {"risks": {"outline": "N"}}, 10), f"stored: {self.body()}")
            p.until("!document.querySelector('.tilemenu:not(.leaving)')", "closed")
            self.menu(p, "risks")
            p.until("!!document.querySelector('.tilemenu')", "menu again")
            self.assertEqual(p.js("document.querySelector('.tilemenu [aria-checked=true]').dataset.outline"), "N")

    def test_K2_moving_the_second_last_tile_right_puts_it_last(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.alt(p, "risks", "ArrowRight", 39)
            self.assertTrue(wait(lambda: self.body().get("order") == ["health", "overdue", "decisions", "risks"], 10), f"stored: {self.body()}")
            self.order_is(p, ["health", "overdue", "decisions", "risks"])

    def test_K3_alt_down_and_alt_up_move_like_right_and_left(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.alt(p, "overdue", "ArrowDown", 40)
            self.assertTrue(wait(lambda: self.body().get("order") == ["health", "risks", "overdue", "decisions"], 10), f"stored: {self.body()}")
            self.order_is(p, ["health", "risks", "overdue", "decisions"])
            grip = self.sel("[data-tile=overdue] [data-tile-grip]")
            self.assertTrue(wait(lambda: p.js(f"document.activeElement === document.querySelector('{grip}')"), 5), "focus back on the grip")
            self.alt(p, "overdue", "ArrowUp", 38)
            self.assertTrue(wait(lambda: "order" not in self.body(), 10), f"stored: {self.body()}")
            self.order_is(p, ["health", "overdue", "risks", "decisions"])

    def test_K4_showing_a_hidden_tile_says_shown_and_focus_stays_on_the_eye(self):
        with chrome() as cdp:
            p = self.page(cdp)
            eye = self.sel("[data-tile=overdue] [data-tile-eye]")
            p.js(f"document.querySelector('{eye}').click()")
            self.assertTrue(wait(lambda: self.body().get("builtin") == {"overdue": {"hidden": True}}, 10))
            self.assertTrue(wait(lambda: p.js(f"document.activeElement === document.querySelector('{eye}')"), 5), "focus on the eye after hiding")
            p.js(f"document.querySelector('{eye}').click()")
            self.assertTrue(wait(lambda: not self.body().get("builtin"), 10), f"stored: {self.body()}")
            p.until("(document.querySelector('.toast-text') || {}).textContent === 'Overdue actions shown in the published report.'", "the shown words")
            self.assertTrue(wait(lambda: p.js(f"document.activeElement === document.querySelector('{eye}')"), 5), "focus on the eye after showing")

    def test_K5_automatic_after_a_colour_says_automatic_and_clears_it(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.menu(p, "risks")
            p.until("!!document.querySelector('.tilemenu')", "menu")
            p.js("document.querySelector('.tilemenu [data-outline=A]').click()")
            self.assertTrue(wait(lambda: self.body().get("builtin") == {"risks": {"outline": "A"}}, 10))
            p.until("!document.querySelector('.tilemenu:not(.leaving)')", "closed")
            self.menu(p, "risks")
            p.until("!!document.querySelector('.tilemenu')", "menu again")
            p.js("document.querySelector('.tilemenu [data-outline=auto]').click()")
            self.assertTrue(wait(lambda: not self.body().get("builtin"), 10), f"stored: {self.body()}")
            p.until("(document.querySelector('.toast-text') || {}).textContent === 'High risks and issues outline: automatic.'", "the automatic words")


if __name__ == "__main__":
    unittest.main()
