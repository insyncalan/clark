"""Row 1416 (AP5), the panel: a change to an item that is on the client report shows the extra tick (the box's own words, no new line),
Apply waits for it, at 1400 and 900 in light and dark; an item that is off the report, or a field the ruling leaves out, shows none.

Run: python3 dev/run_tests.py test_ask_client_tick_page_1416
"""
import json

import test_server  # noqa: F401  (the runner tells a browser file by this import)
from test_ask_change_page import Card, WORDS, chrome


class ClientTickPage(Card):
    def change(self, visible, **fields):
        ref = self.demo.action(owner="Kim Roe", description="Order the badges", client_visible=visible)
        self.says("CHANGE: " + json.dumps({"op": "change", "id": ref, "current_title": "Order the badges", **fields}))
        return ref


    def test_a_client_visible_status_change_shows_the_box_alone_and_apply_waits_for_it(self):
        ref = self.change(1, status="Closed")
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("!!document.querySelector('[data-ask-confirm]')", "the tick")
            box = "document.querySelector('.ask-confirm label')"
            self.assertIn(p.js(f"{box}.textContent.trim()"), WORDS, "the box words are the existing ones")
            self.assertEqual(p.js(f"{box}.textContent.trim()"), "I have checked this change and want to save it")
            self.assertEqual(p.js("document.querySelectorAll('.ask-confirm-line').length"), 0, "no line about files above a tick that is not about files")
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for theme in ("light", "dark"):
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    self.assertTrue(p.js("(function(){var c=document.querySelector('[data-ask-change]'),b=document.querySelector('.ask-confirm label').getBoundingClientRect(),"
                                         "q=document.querySelector('#ask-panel').getBoundingClientRect();return c.scrollWidth<=c.clientWidth+1 && b.left>=q.left && b.right<=q.right})()"),
                                    f"{width} {theme}: the tick fits in the panel")
            self.assertTrue(p.js("document.querySelector('[data-ask-apply]').disabled"), "Apply waits for the tick")
            self.assertEqual(self.store.read("actions", ref=ref)["status"], "Open")
            p.js("document.querySelector('[data-ask-confirm]').click()")
            p.until("!document.querySelector('[data-ask-apply]').disabled", "Apply is ready once ticked")
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "Done.")
            self.assertEqual(self.store.read("actions", ref=ref)["status"], "Closed")

    def test_an_item_off_the_report_shows_no_tick(self):
        self.change(0, status="Closed")
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-confirm]').length"), 0)
            self.assertFalse(p.js("document.querySelector('[data-ask-apply]').disabled"))

    def test_a_field_the_ruling_leaves_out_shows_no_tick_on_a_client_visible_item(self):
        self.change(1, priority="High")
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-confirm]').length"), 0)

    def test_a_new_item_shows_the_tick(self):
        self.says("CHANGE: " + json.dumps({"op": "new", "kind": "action", "title": "Book the room", "owner": "Sam Lee"}))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-confirm]').length"), 1)
            self.assertTrue(p.js("document.querySelector('[data-ask-apply]').disabled"))


if __name__ == "__main__":
    import unittest
    unittest.main()
