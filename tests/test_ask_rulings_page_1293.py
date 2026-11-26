"""Row 1293, the rulings on the page, in the Classic theme (prototype 2.0): the duplicate warning above Apply, the second change refused
in place of its Apply, and the Docker line where the box would be and in Settings. The Cards theme keeps what it had. A real browser,
the real page, the real change routes and store; the answer comes from a STUB provider (nothing calls a model). Fictional data only.

Run: python3 dev/run_tests.py test_ask_rulings_page_1293
"""
import json
import unittest
from unittest import mock

import _testpage as testpage
from _real_server import real_server
from test_ask_change_page import Card
from test_server import chrome
from clark import ask, ask_words, page, platform, theme as themes

TITLE = "Draft the cut-over plan"
STALE = "This one was not saved: status changed when the first change was saved. Ask again to change it."
DUPLICATE = f'There is already an action called "{TITLE.lower()}". Apply to add another.'


class Themed(Card):
    THEME = "prototype-2.0"

    def setUp(self):
        super().setUp()
        self.s.close()
        css = themes.css(self.THEME) if self.THEME else None
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css) if css else testpage.html(), seam=self.seam)
        self.addCleanup(self.s.close)
        self.s.httpd.ask = self.service

    def change(self, **more):
        return "CHANGE: " + json.dumps({"op": "change", "id": self.action, "current_title": TITLE, **more})

    def new(self, title):
        return "CHANGE: " + json.dumps({"op": "new", "kind": "action", "title": title})

    def lines(self, p):
        return p.js("Array.from(document.querySelectorAll('[data-ask-change]')).map(c => ({apply: !!c.querySelector('[data-ask-apply]'), "
                    "dup: (c.querySelector('[data-ask-duplicate]') || {}).textContent || '', line: (c.querySelector('[data-ask-line]') || {}).textContent || ''}))")


class ClassicCards(Themed):
    def test_a_duplicate_new_item_is_warned_above_apply_and_apply_stays(self):
        self.says(self.new(TITLE.lower()), self.new("A title nobody has used"))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "both cards")
            self.assertEqual(self.lines(p), [{"apply": True, "dup": DUPLICATE, "line": ""}, {"apply": True, "dup": "", "line": ""}])
            self.assertTrue(p.js("(() => { const c = document.querySelector('[data-ask-change]'); const d = c.querySelector('[data-ask-duplicate]');"
                                 " return !!(d.compareDocumentPosition(c.querySelector('[data-ask-apply]')) & Node.DOCUMENT_POSITION_FOLLOWING); })()"), "above Apply")
            p.js("document.querySelector('[data-ask-confirm]').click()")      # row 1416: a new item needs the extra tick before Apply
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "added anyway")
            self.assertEqual(len([r for r in self.store.read("actions", "ABC") if r["description"] == TITLE.lower()]), 1)
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-duplicate]').length"), 0, "the warning goes once the card is used")

    def test_the_duplicate_note_keeps_its_amber_bar_light_and_dark_at_1400_and_900(self):
        self.says(self.new(TITLE.lower()))
        probe = ("(() => { const d = document.querySelector('[data-ask-duplicate]'); const c = getComputedStyle(d); const r = getComputedStyle(document.documentElement);"
                 " const t = document.createElement('i'); t.style.color = 'var(--status-amber)'; document.body.appendChild(t); const amber = getComputedStyle(t).color; t.remove();"
                 " return {w: c.borderLeftWidth, s: c.borderLeftStyle, col: c.borderLeftColor, amber: amber}; })()")
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            p.until("!!document.querySelector('[data-ask-duplicate]')", "the note")
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for scheme in ("light", "dark"):
                    p.js("document.documentElement.setAttribute('data-theme', %r)" % scheme)
                    got = p.js(probe)
                    tag = f"{scheme} {width}"
                    self.assertEqual((got["w"], got["s"]), ("3px", "solid"), tag)
                    self.assertEqual(got["col"], got["amber"], tag)
                    self.assertNotIn(got["amber"], ("", "rgba(0, 0, 0, 0)"), tag)

    def test_after_the_first_change_is_applied_the_second_shows_the_line_and_no_apply(self):
        self.says(self.change(status="Closed"), self.change(priority="High"))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "both cards")
            self.assertEqual([c["apply"] for c in self.lines(p)], [True, True])
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("!!document.querySelectorAll('[data-ask-change]')[1].querySelector('[data-ask-line]')", "the second card has its line")
            got = self.lines(p)
            self.assertEqual(got[1], {"apply": False, "dup": "", "line": STALE})
            self.assertTrue(got[0]["line"].startswith("Done."))
            self.assertEqual(self.status(), "Closed", "the first stays saved and nothing was written for the second")
            self.assertNotEqual(self.store.read("actions", ref=self.action)["priority"], "High", "nothing was written for the second")

    def test_the_change_limit_line_at_1400_and_900(self):
        lines = [self.new(f"Task number {i}") for i in range(ask.MAX_CHANGES + 1)]
        self.says(*lines)
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            p.until(f"document.querySelectorAll('[data-ask-change]').length === {ask.MAX_CHANGES}", "only the first five cards")
            for width, theme in ((1400, "light"), (1400, "dark"), (900, "light"), (900, "dark")):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.js(f"document.documentElement.dataset.theme = '{theme}'")
                where = f"{width} {theme}"
                text = p.js("document.querySelector('#ask-panel').innerText")
                self.assertIn(ask.CHANGE_LIMIT, text.replace("\n", " "), f"{where}: the change-limit line is on the page")
                self.assertEqual(p.js("document.querySelectorAll('[data-ask-change]').length"), ask.MAX_CHANGES, where)

    def test_a_card_for_another_item_is_not_marked(self):
        other = self.demo.action(owner="Kit Moss", description="Order the lanyards")
        self.says(self.change(status="Closed"), "CHANGE: " + json.dumps({"op": "change", "id": other, "current_title": "Order the lanyards", "status": "Closed"}))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "both cards")
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "Done.")
            self.assertEqual([c["apply"] for c in self.lines(p)], [False, True])

    def test_docker_says_it_where_the_box_would_be(self):
        with mock.patch.object(platform, "container_mode", return_value=True), chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-docker')", "the Docker line")
            self.assertEqual(p.js("document.querySelector('#ask-docker').textContent"), "Ask clark is not available in the Docker version of clark.")
            self.assertEqual(p.js("document.querySelectorAll('#ask-box, #ask-signed-out').length"), 0, "no box and no sign-in line")

    def test_docker_says_it_in_settings_on_the_ask_clark_page(self):
        with mock.patch.object(platform, "container_mode", return_value=True), chrome() as cdp:
            p = self.visit(cdp)
            p.js("location.hash = '#settings&p=ABC&s=claude'")
            p.until("!!document.querySelector('#ask-settings #ask-docker')", "the Docker line in Settings")
            self.assertEqual(p.js("document.querySelector('#ask-settings #ask-docker').textContent"), ask_words.DOCKER)

    def test_outside_docker_neither_place_says_it(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("location.hash = '#settings&p=ABC&s=claude'")
            p.until("!!document.querySelector('#ask-settings') && !document.querySelector('[data-ask-switch]').disabled", "Settings is ready")
            self.assertEqual(p.js("document.querySelectorAll('#ask-docker').length"), 0)


if __name__ == "__main__":
    unittest.main()
