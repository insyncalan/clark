"""Row 1264 slice 4: killer tests for the mutation review (S4). Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_edit_1264_killers
"""
import json
import unittest

from test_report_editor import ALT, tearDownModule  # noqa: F401
from test_changes import KIND
from test_server import chrome, wait
from test_tpl_glance_edit_1264 import DEFAULT, GlanceEdit


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

    def test_K6_the_eye_says_pressed_only_while_the_tile_is_hidden(self):
        with chrome() as cdp:
            p = self.page(cdp)
            eye = self.sel("[data-tile=overdue] [data-tile-eye]")
            self.assertEqual(p.js(f"document.querySelector('{eye}').getAttribute('aria-pressed')"), "false")
            p.js(f"document.querySelector('{eye}').click()")
            self.assertTrue(wait(lambda: self.body().get("builtin") == {"overdue": {"hidden": True}}, 10))
            p.until(f"document.querySelector('{eye}').getAttribute('aria-pressed') === 'true'", "pressed while hidden")
            self.assertIn("Show Overdue actions", p.js(f"document.querySelector('{eye}').getAttribute('aria-label')"))

    def test_K7_a_change_keeps_the_bespoke_tiles_and_the_own_row_flag(self):
        bespoke = [{"id": "b1", "label": "Fictional green", "figure": "7", "tag": "Fine", "note": "Fictional note", "tone": "green"}]
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": self.ref,
                                        "changes": {"body": json.dumps({"v": 1, "bespoke": bespoke, "health": {"own_row": True}})}})
        self.assertEqual(status, 200, got)
        with chrome() as cdp:
            p = self.page(cdp)
            p.js(f"document.querySelector('{self.sel('[data-tile=overdue] [data-tile-eye]')}').click()")
            self.assertTrue(wait(lambda: self.body().get("builtin") == {"overdue": {"hidden": True}}, 10), f"stored: {self.body()}")
            self.assertEqual(self.body().get("bespoke"), bespoke)
            self.assertEqual(self.body().get("health"), {"own_row": True})
            self.assertEqual(self.body().get("v"), 1)

    def test_K8_dropping_a_dragged_tile_on_the_right_half_of_the_last_tile_puts_it_last(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js(f"document.querySelector('{self.sel()}').scrollIntoView({{block: 'center'}})")
            gx, gy, _ = p.box(self.sel("[data-tile=health] [data-tile-grip]"))
            r = p.js(f"(function(){{var r=document.querySelector('{self.sel('[data-tile=decisions]')}').getBoundingClientRect();return [r.left + r.width * 0.8, r.top + r.height / 2];}})()")
            p.mouse("mousePressed", gx, gy, 1)
            for step in range(1, 9):
                p.mouse("mouseMoved", gx + (r[0] - gx) * step / 8, gy + (r[1] - gy) * step / 8, 1)
            p.mouse("mouseReleased", r[0], r[1], 0)
            self.assertTrue(wait(lambda: self.body().get("order") == ["overdue", "risks", "decisions", "health"], 10), f"stored: {self.body()}")

    def test_K9_escape_during_a_drag_cancels_it_and_no_step_is_made(self):
        with chrome() as cdp:
            p = self.page(cdp)
            before = self.applies()
            p.js(f"document.querySelector('{self.sel()}').scrollIntoView({{block: 'center'}})")
            gx, gy, _ = p.box(self.sel("[data-tile=risks] [data-tile-grip]"))
            tx, ty, _ = p.box(self.sel("[data-tile=health]"))
            p.mouse("mousePressed", gx, gy, 1)
            for step in range(1, 9):
                p.mouse("mouseMoved", gx + (tx - 120 - gx) * step / 8, gy + (ty - gy) * step / 8, 1)
            p.key("Escape", code="Escape", vk=27)
            p.mouse("mouseReleased", tx - 120, ty, 0)
            import time
            time.sleep(0.8)
            self.assertEqual(self.body(), {})
            self.assertEqual(self.applies(), before, "a cancelled drag is no step")
            self.assertEqual(self.drawn(p), DEFAULT)


if __name__ == "__main__":
    unittest.main()
