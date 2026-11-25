"""Row 1270 slice 2: the editor of the RAID cards card. The choice of three or four across saves as body version 2; old version 1 bodies stay until touched.

Run: python3 dev/run_tests.py test_raid_cards_edit_1270
Fictional rows.
"""
import json
import unittest

from _demo import USER
import test_tpl_raid3 as three
from test_report_editor import Base as PageBase
from test_server import chrome


class Edit(PageBase):
    arr = three.PageSide.arr
    set_select = three.PageSide.set_select
    wait_for = three.PageSide.wait_for

    def seed(self):
        self.demo.plant_builtin_sections()      # the cards are drawn beside the built-in sections (row 1193)
        with self.store.step("dashboard", USER) as st:
            made = [st.create("raid", {"project": "ABC", "type": "Risk", "description": f"Fictional risk {i}", "raised": "2026-10-01", "source": "demo"}) for i in range(9)]
            ref = st.create("report_sections", {"project": "ABC", "type": "raid4", "title": "Fictional cards", "sort_order": 999,
                                                "body": json.dumps({"v": 1, "cards": [{"id": made[0], "source": "client"}]})})
        return ref, made

    def stored(self, sec):
        return json.loads(next(r for r in self.store.read("report_sections", "ABC") if r["id"] == sec)["body"])

    def test_the_choice_saves_as_version_two_and_old_bodies_stay_until_touched(self):
        sec, made = self.seed()
        q = f"[data-id={json.dumps(sec)}]"
        with chrome() as cdp:
            cdp.FOCUS_EMULATION = False
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{q} select[aria-label=\"Cards across\"]')", "the choice is there")
            self.assertEqual(self.arr(p, f"[...document.querySelectorAll('{q} select[aria-label=\"Cards across\"] option')].map(o => o.textContent)"), ["3", "4"])
            self.assertEqual(p.js(f"document.querySelector('{q} select[aria-label=\"Cards across\"]').value"), "4", "an old four across body reads as four")
            self.assertEqual(self.stored(sec)["v"], 1, "opening Edit changes nothing")
            self.set_select(p, f"{q} select[aria-label='Card 2 item']", made[1])
            self.assertTrue(self.wait_for(lambda: len(self.stored(sec)["cards"]) == 2), "the second card is saved")
            self.assertEqual(self.stored(sec)["v"], 1, "a card on a four across body keeps the old shape")
            self.set_select(p, f"{q} select[aria-label='Cards across']", "3")
            self.assertTrue(self.wait_for(lambda: self.stored(sec).get("across") == 3))
            self.assertEqual([c["id"] for c in self.stored(sec)["cards"]], made[:2])
            for i in range(3, 9):
                self.assertTrue(self.wait_for(lambda: len(self.stored(sec)["cards"]) == i - 1))
                p.until(f"!!document.querySelector('{q} select[aria-label=\"Card {i} item\"]')", f"slot {i}")
                self.set_select(p, f"{q} select[aria-label='Card {i} item']", made[i - 1])
            p.until(f"!!document.querySelector('{q} select[aria-label=\"Card 8 item\"]')", "an eighth card")
            self.assertTrue(self.wait_for(lambda: len(self.stored(sec)["cards"]) == 8), "eight cards are saved")
            self.assertFalse(p.js(f"!!document.querySelector('{q} select[aria-label=\"Card 9 item\"]')"), "no ninth slot")

    def test_the_also_show_boxes_are_drawn_for_the_cards_card_only_not_for_an_old_three_across_section(self):
        sec, made = self.seed()
        with self.store.step("dashboard", USER) as st:
            old = st.create("report_sections", {"project": "ABC", "type": "raid3", "title": "Fictional old cards", "sort_order": 1000,
                                                "body": json.dumps({"v": 1, "cards": [{"id": made[0], "source": "client"}]})})
        with chrome() as cdp:
            cdp.FOCUS_EMULATION = False
            p = self.visit(cdp)
            p.edit()
            for ref in (sec, old):
                p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] select[aria-label=\"Card 1 item\"]')", "the card row is there")
            self.assertTrue(p.js(f"!!document.querySelector('[data-id={json.dumps(sec)}] .rce-show')"), "the cards card draws the boxes")
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(old)}] .rce-show')"), "an old three across section does not: it saves no show")


    def test_the_edit_fields_use_the_control_edge_colour_at_both_widths_light_and_dark(self):
        """Row 1270 (PM ruling, point 9): the Edit fields of a card (.rce-f select and input) have the control-edge colour as their border, as the other
        controls do, at 1400 and 900, light and dark. Measured as the computed colour against a probe that takes var(--control-edge).
        The card's own edge and the disabled hint are waived (PM ruling): not checked here."""
        sec, made = self.seed()
        q = f"[data-id={json.dumps(sec)}]"
        probe = ("(() => { const d = document.createElement('i'); d.style.cssText = 'border:1px solid var(--control-edge)'; document.body.appendChild(d);"
                 " const c = getComputedStyle(d).borderTopColor; d.remove(); return c; })()")
        fields = (f"(() => [...document.querySelectorAll('{q} .rce-f select, {q} .rce-f input')].map(e => getComputedStyle(e).borderTopColor))()")
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{q} .rce-f select')", "the fields are there")
            for w, dark in ((1400, False), (900, False), (1400, True), (900, True)):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.js("document.documentElement.dataset.theme = %s" % json.dumps("dark" if dark else "light"))
                edge = p.js(probe)
                got = self.arr(p, fields)
                self.assertTrue(len(got) >= 2, f"the card has fields at {w} dark={dark}: {got}")
                self.assertEqual(set(got), {edge}, f"every Edit field has the control-edge colour {edge} at {w} dark={dark}: {got}")


if __name__ == "__main__":
    unittest.main()
