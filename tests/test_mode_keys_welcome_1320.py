"""Row 1320: the first-run Welcome card is a non-modal note, so it must not hide the View | Edit pill or leave V and E dead.
Before the fix the card (a role=dialog) hid #mode-pill by the page's dialog rule and keys.js ignored V and E while it was in the page; when the
profile read was slow, E switched to Edit, the card then arrived and took the focus, and the pill vanished and V no longer returned to View.

Run: python3 dev/run_tests.py test_mode_keys_welcome_1320
"""
import unittest

from test_publish_dialog import Base, Pg
from test_server import chrome

CARD = "document.querySelector('[data-welcome]')"
PILL = "getComputedStyle(document.querySelector('#mode-pill')).display"
MODE = "document.querySelector('#report').dataset.mode"
SLOW = ("window.__clarkWelcome = true; const f = window.fetch; "
        "window.fetch = (...a) => (String(a[0]).includes('profile') ? new Promise((ok) => setTimeout(ok, 3000)) : Promise.resolve()).then(() => f(...a));")


class Row1320(Base):
    def show_page(self, cdp, script, width):
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": script}, sid)
        p = Pg(self, cdp, sid)
        p.width(width)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.rig.httpd.server_port}/#dashboard&p=PUB"}, sid)
        p.until("!!document.querySelector('#mode-pill')", "the pill drew", 30)
        return p

    def test_the_card_arriving_after_E_leaves_the_pill_and_V_working(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show_page(cdp, SLOW, width)
                self.assertFalse(p.js(f"!!{CARD}"), "the card is not there yet")
                p.key("e", code="KeyE", vk=69)
                p.until(f"{MODE} === 'edit'", "E switched to Edit")
                p.until(f"!!{CARD}", "the card arrived", 30)
                self.assertEqual(p.js(PILL), "flex", "the card does not hide the pill")
                self.assertNotEqual(p.js("document.activeElement.id"), "welcome-name", "the card did not take the focus after E")
                p.key("v", code="KeyV", vk=86)
                p.until(f"{MODE} === 'view'", "V returned to View")

    def test_the_card_already_up_leaves_the_pill_clickable(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show_page(cdp, "window.__clarkWelcome = true;", width)
                p.until(f"!!{CARD}", "the card is shown", 30)
                self.assertEqual(p.js(PILL), "flex", "the pill is on show beside the card")
                p.js("document.querySelector('#mode-pill [data-mode=\"edit\"]').click()")
                p.until(f"{MODE} === 'edit'", "the pill's Edit works")
                p.js("document.querySelector('#mode-pill [data-mode=\"view\"]').click()")
                p.until(f"{MODE} === 'view'", "the pill's View works")

    def test_a_shut_dialog_with_the_hidden_attribute_leaves_the_pill_and_the_keys_working(self):
        """The row 1320 report (1.3.1, a Dashboard with a Work items list): its Configure panel kept role=dialog while shut, with hidden."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show_page(cdp, "window.__clarkWelcome = false;", width)
                p.js("var d = document.createElement('div'); d.setAttribute('role', 'dialog'); d.hidden = true; d.id = 'shut'; document.body.appendChild(d);"
                     "var m = document.createElement('div'); m.setAttribute('role', 'menu'); m.hidden = true; m.id = 'shutmenu'; document.body.appendChild(m);"
                     "var a = document.createElement('div'); a.setAttribute('role', 'alertdialog'); a.hidden = true; a.id = 'shutalert'; document.body.appendChild(a);")
                self.assertEqual(p.js(PILL), "flex")
                p.key("e", code="KeyE", vk=69)
                p.until(f"{MODE} === 'edit'", "E switched to Edit")
                self.assertEqual(p.js(PILL), "flex", "the pill is still there in Edit")
                p.key("v", code="KeyV", vk=86)
                p.until(f"{MODE} === 'view'", "V returned to View")

    def test_a_real_dialog_still_hides_the_pill(self):
        with chrome() as cdp:
            p = self.show_page(cdp, "window.__clarkWelcome = false;", 1400)
            p.js("var d = document.createElement('div'); d.setAttribute('role', 'dialog'); d.id = 'fake'; document.body.appendChild(d);")
            self.assertEqual(p.js(PILL), "none")
            p.key("e", code="KeyE", vk=69)
            self.assertEqual(p.js(MODE), "view", "E is left alone while a dialog is open")


if __name__ == "__main__":
    unittest.main()
