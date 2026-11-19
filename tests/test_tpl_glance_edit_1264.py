"""Row 1264 slice 4: the Glance template's Edit part for the built-in tiles, in a real browser (T64-T71): one Undo step per change, a
change that changes nothing is no step, Alt and the arrows, the tab order, the outline menu's keys, the health eye. The words are the
At a glance words that exist; no placeholder text is shown by this slice. Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_edit_1264
"""
import json
import unittest

from _demo import USER
from test_glance_page import plant
from test_report_editor import ALT, Base, tearDownModule  # noqa: F401
from test_server import chrome, wait

PLACEHOLDER = "[words pending:"          # the marker no shown word may carry
TITLES = {"health": "Project health", "overdue": "Overdue actions", "risks": "High risks and issues", "decisions": "Decisions needed"}
DEFAULT = ["health", "overdue", "risks", "decisions"]


class GlanceEdit(Base):
    FRESH = False         # True: the section is never written, so Project health starts off (a new template); False: an existing page, health shown

    def setUp(self):
        super().setUp()
        plant(self)
        with self.store.step("dashboard", USER) as st:
            self.ref = st.create("report_sections", {"project": "ABC", "type": "glancetemplate", "title": "Fictional glance", "sort_order": 998})
        if not self.FRESH:
            self.store.con.execute("UPDATE report_sections SET body = ? WHERE id = ?", ('{"v":1}', self.ref))      # an existing page: no health field, health shown
            self.store.con.commit()

    def page(self, cdp, width=1400, dark=False):
        p = self.visit(cdp)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        p.edit()
        p.until(f"!!document.querySelector('{self.sel('[data-tile=decisions]')}')", "the tiles drew")
        return p

    def sel(self, rest=""):
        return f'[data-id="{self.ref}"] {rest}'.strip()

    def body(self):
        raw = self.store.read("report_sections", ref=self.ref)["body"]
        return json.loads(raw) if raw else {}

    def applies(self):
        return self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]

    def drawn(self, p):
        return p.js(f"[...document.querySelectorAll('{self.sel('.glance > .tcell')}')].map(e => e.dataset.tile)")

    def toast(self, p):
        return p.js("(document.querySelector('.toast-text') || {}).textContent || ''")

    def undo(self, p):
        p.js("document.querySelector('[data-undo]').click()")
        p.until("!document.querySelector('[data-undo]')", "undone")

    def menu(self, p, key):
        p.js(f"document.querySelector('{self.sel(f'[data-tile={key}]')}').dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")


class Steps(GlanceEdit):
    def test_T64_the_eye_hides_a_tile_in_one_step_and_one_undo_puts_it_back(self):
        with chrome() as cdp:
            p = self.page(cdp)
            before = self.applies()
            p.js(f"document.querySelector('{self.sel('[data-tile=overdue] [data-tile-eye]')}').click()")
            self.assertTrue(wait(lambda: self.body().get("builtin") == {"overdue": {"hidden": True}}, 10), f"stored: {self.body()}")
            self.assertEqual(self.applies(), before + 1, "one step")
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.assertEqual(self.toast(p), "Overdue actions hidden from the published report.")
            p.until(f"!document.querySelector('{self.sel('[data-tile=overdue]')}')", "the hidden tile left Edit (row 1303)")
            self.undo(p)
            self.assertTrue(wait(lambda: self.body() == {} or self.body() == {"v": 1}, 10), f"undone: {self.body()}")
            self.assertEqual(self.applies(), before + 2, "the undo is one step")
            p.until(f"!!document.querySelector('{self.sel('[data-tile=overdue]')}')", "shown again")

    def test_T64_an_outline_colour_is_one_step_and_one_undo(self):
        with chrome() as cdp:
            p = self.page(cdp)
            before = self.applies()
            self.menu(p, "risks")
            p.until("!!document.querySelector('.tilemenu')", "the colour menu")
            self.assertEqual(p.js("[...document.querySelectorAll('.tilemenu [role^=menuitem]')].map(b => b.textContent.replace('✓ ', ''))"),
                             ["Automatic", "Green", "Amber", "Red", "No colour"])
            p.js("document.querySelector('.tilemenu [data-outline=A]').click()")
            self.assertTrue(wait(lambda: self.body().get("builtin") == {"risks": {"outline": "A"}}, 10), f"stored: {self.body()}")
            self.assertEqual(self.applies(), before + 1)
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.assertEqual(self.toast(p), "High risks and issues outline: amber.")
            self.assertTrue(p.js(f"document.querySelector('{self.sel('[data-fig=risks]')}').classList.contains('rag-a')"))
            self.undo(p)
            self.assertTrue(wait(lambda: not self.body().get("builtin"), 10), f"undone: {self.body()}")

    def test_T65_a_change_that_changes_nothing_is_no_step(self):
        with chrome() as cdp:
            p = self.page(cdp)
            before = self.applies()
            p.js(f"document.querySelector('{self.sel('[data-tile=health] [data-tile-grip]')}').focus()")
            p.key("ArrowLeft", ALT, code="ArrowLeft", vk=37)           # already first
            p.until("!!document.querySelector('.toast-text')", "the note")
            self.assertEqual(self.toast(p), "Project health is already first.")
            p.js(f"document.querySelector('{self.sel('[data-tile=decisions] [data-tile-grip]')}').focus()")
            p.key("ArrowRight", ALT, code="ArrowRight", vk=39)         # already last
            self.menu(p, "overdue")                                    # Automatic on an automatic outline
            p.until("!!document.querySelector('.tilemenu')", "the colour menu")
            p.js("document.querySelector('.tilemenu [data-outline=auto]').click()")
            import time
            time.sleep(0.7)
            self.assertEqual(self.applies(), before, "no step for any of the three")
            self.assertEqual(self.body(), {"v": 1})      # as it was set up: nothing was written

    def test_T66_alt_and_the_arrows_move_a_tile_one_step_each_and_the_order_is_stored(self):
        with chrome() as cdp:
            p = self.page(cdp)
            before = self.applies()
            p.js(f"document.querySelector('{self.sel('[data-tile=overdue] [data-tile-grip]')}').focus()")
            p.key("ArrowRight", ALT, code="ArrowRight", vk=39)
            self.assertTrue(wait(lambda: self.body().get("order") == ["health", "risks", "overdue", "decisions"], 10), f"stored: {self.body()}")
            p.until(f"JSON.stringify([...document.querySelectorAll('{self.sel('.glance > .tcell')}')].map(e => e.dataset.tile)) === JSON.stringify(['health','risks','overdue','decisions'])", "moved")
            self.assertEqual(self.applies(), before + 1)
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.assertEqual(self.toast(p), "Overdue actions moved.")
            self.assertTrue(p.js(f"document.activeElement === document.querySelector('{self.sel('[data-tile=overdue] [data-tile-grip]')}')"), "focus stays on the grip")
            p.key("ArrowLeft", ALT, code="ArrowLeft", vk=37)           # and back: the default order is not stored
            self.assertTrue(wait(lambda: "order" not in self.body(), 10), f"stored: {self.body()}")
            p.until(f"JSON.stringify([...document.querySelectorAll('{self.sel('.glance > .tcell')}')].map(e => e.dataset.tile)) === JSON.stringify({json.dumps(DEFAULT)})", "back")
            self.assertEqual(self.applies(), before + 2)

    def test_T66_a_move_is_undone_in_one_step(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js(f"document.querySelector('{self.sel('[data-tile=health] [data-tile-grip]')}').focus()")
            p.key("ArrowRight", ALT, code="ArrowRight", vk=39)
            self.assertTrue(wait(lambda: self.body().get("order") == ["overdue", "health", "risks", "decisions"], 10), f"stored: {self.body()}")
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.undo(p)
            self.assertTrue(wait(lambda: "order" not in self.body(), 10))
            p.until(f"JSON.stringify([...document.querySelectorAll('{self.sel('.glance > .tcell')}')].map(e => e.dataset.tile)) === JSON.stringify({json.dumps(DEFAULT)})", "back")

    def test_T66_dragging_the_grip_moves_a_tile(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js(f"document.querySelector('{self.sel()}').scrollIntoView({{block: 'center'}})")
            gx, gy, _ = p.box(self.sel("[data-tile=risks] [data-tile-grip]"))
            tx, ty, _ = p.box(self.sel("[data-tile=health]"))
            p.mouse("mousePressed", gx, gy, 1)
            for step in range(1, 9):
                p.mouse("mouseMoved", gx + (tx - 120 - gx) * step / 8, gy + (ty - gy) * step / 8, 1)
            p.mouse("mouseReleased", tx - 120, ty, 0)
            self.assertTrue(wait(lambda: self.body().get("order") == ["risks", "health", "overdue", "decisions"], 10), f"stored: {self.body()}")


class Keys(GlanceEdit):
    def test_T67_the_tab_order_is_grip_then_eye_tile_after_tile(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js(f"document.querySelector('{self.sel()}').querySelector('[data-tile-grip]').focus()")
            seen = []
            for _ in range(24):
                got = p.js("(function(){var e = document.activeElement, t = e && e.closest('[data-tile]'); return [t && t.dataset.tile, e && e.hasAttribute('data-tile-grip') ? 'grip' : e && e.hasAttribute('data-tile-eye') ? 'eye' : '']; })()")
                if got[1] and (not seen or seen[-1] != tuple(got)):
                    seen.append(tuple(got))
                p.key("Tab", code="Tab", vk=9)
            self.assertEqual(seen[:8], [(k, w) for k in DEFAULT for w in ("grip", "eye")])

    def test_T68_the_outline_menu_opens_by_right_click_moves_by_the_arrows_and_escape_returns_to_the_grip(self):
        with chrome() as cdp:
            p = self.page(cdp)
            before = self.applies()
            self.menu(p, "overdue")
            p.until("!!document.querySelector('.tilemenu')", "the colour menu")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('.tilemenu:not(.leaving)')", "closed")
            self.assertTrue(p.js(f"document.activeElement === document.querySelector('{self.sel('[data-tile=overdue] [data-tile-grip]')}')"))
            self.assertEqual(self.applies(), before, "Escape is no step")
            self.menu(p, "overdue")
            p.until("!!document.querySelector('.tilemenu')", "the colour menu again")
            p.key("ArrowDown", code="ArrowDown", vk=40)
            p.key("ArrowDown", code="ArrowDown", vk=40)
            want = p.js("document.activeElement.dataset.outline")
            self.assertIn(want, ("G", "A", "R", "N", "auto"))
            if want == "auto":
                self.fail("two arrows must leave the first item")
            p.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"}, p.sid)
            p.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13}, p.sid)
            self.assertTrue(wait(lambda: self.body().get("builtin") == {"overdue": {"outline": want}}, 10), f"stored: {self.body()}")
            self.assertEqual(self.applies(), before + 1)


class FreshHealth(GlanceEdit):
    FRESH = True

    def test_T69a_a_new_template_starts_with_the_health_eye_off_and_the_button_turns_it_on(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertFalse(p.js(f"!!document.querySelector('{self.sel('[data-tile=health]')}')"), "never written: health starts off, so it is not drawn")
            self.assertTrue(p.js(f"!!document.querySelector('{self.sel('[data-gt-showhealth]')}')"), "the button that brings it back is drawn")
            p.js(f"document.querySelector('{self.sel('[data-gt-showhealth]')}').click()")
            self.assertTrue(wait(lambda: self.body() == {"v": 1}, 10), f"stored: {self.body()}")
            p.until(f"!!document.querySelector('{self.sel('[data-tile=health]')}')", "health drawn")
            self.assertFalse(p.js(f"document.querySelector('{self.sel('[data-tile=health]')}').classList.contains('is-hidden')"))


class Health(GlanceEdit):
    def test_T69_the_eye_on_project_health_hides_the_tile_only_and_undo_shows_it(self):
        self.store.con.execute("UPDATE report_sections SET body = ? WHERE id = ?", ('{"v":1}', self.ref))      # an existing page: no health field, health shown
        self.store.con.commit()
        with chrome() as cdp:
            p = self.page(cdp)
            project = self.store.read("projects", ref="ABC")["health"]
            before = self.applies()
            p.js(f"document.querySelector('{self.sel('[data-tile=health] [data-tile-eye]')}').click()")
            self.assertTrue(wait(lambda: self.body().get("health") == {"shown": False}, 10), f"stored: {self.body()}")
            self.assertEqual(self.applies(), before + 1)
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.assertEqual(self.toast(p), "Project health is hidden completely")      # row 1264 slice 9: the ruled words (group 10)
            self.assertFalse(p.js(f"!!document.querySelector('{self.sel('[data-tile=health]')}')"), "no tile, not even a dimmed one: the button that brings it back is drawn instead")
            self.assertEqual(self.store.read("projects", ref="ABC")["health"], project, "the project's own health is not touched")
            self.undo(p)
            self.assertTrue(wait(lambda: "health" not in self.body(), 10), f"undone: {self.body()}")
            p.until(f"!!document.querySelector('{self.sel('[data-tile=health] .pillbtn')}')", "the pill is back to change")

    def test_T70_project_health_has_no_outline_menu_and_its_grip_does_not_offer_one(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.menu(p, "health")
            import time
            time.sleep(0.4)
            self.assertEqual(p.js("document.querySelectorAll('.tilemenu').length"), 0)
            self.assertNotIn("Right-click", p.js(f"document.querySelector('{self.sel('[data-tile=health] [data-tile-grip]')}').getAttribute('aria-label')"))
            self.assertIn("Right-click for its outline colour.", p.js(f"document.querySelector('{self.sel('[data-tile=risks] [data-tile-grip]')}').getAttribute('aria-label')"))

    def test_T71_the_words_are_the_existing_ones_and_the_edit_counts_the_rows(self):
        with chrome() as cdp:
            p = self.page(cdp)
            text = p.js(f"document.querySelector('{self.sel()}').textContent")
            self.assertNotIn(PLACEHOLDER, text)
            self.assertEqual(p.js(f"[...document.querySelectorAll('{self.sel('[data-tile]')}')].map(e => (e.querySelector('.k') || {{}}).textContent.replace(/\\s+/g, ' ').trim())"),
                             [TITLES[k] for k in DEFAULT])
            self.assertEqual(p.js(f"document.querySelector('{self.sel('[data-fig=overdue] .v')}').textContent"), "3")
            self.assertEqual(p.js(f"document.querySelector('{self.sel('[data-fig=risks] .v')}').textContent"), "1")
            self.assertEqual(p.js(f"document.querySelector('{self.sel('[data-fig=decisions] .v')}').textContent"), "1")
            self.assertIn("Hold Alt and press an arrow key".lower(), p.js(f"document.querySelector('{self.sel('[data-glance-hint]')}').textContent").lower().replace("or hold", "hold"))

    def test_T71_it_fits_at_1400_and_900_in_light_and_dark(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.page(cdp, width, dark)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"))
                    self.assertEqual(self.drawn(p), DEFAULT)


if __name__ == "__main__":
    unittest.main()
