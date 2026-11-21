"""Row 1351 (mock-up A8): the order of the cards on the ask clark page and of its tabs, in a real browser at 1400 and 900.

Run: python3 dev/run_tests.py test_ask_order_1351
The project's tab: Asking in <project>; Used from All projects; Connectors in <project>; Source folders for <project>; Standing instructions.
The All projects tab: the model card, the other connectors, the standing instructions, then the source folders. The tabs: All projects first,
the open project second and shown. Chrome is required."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _editor_checks import for_project
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import page, theme

WIDTHS = (1400, 900)
HEADS = "[...document.querySelectorAll('#ask-tabs ~ section.frame.setting > h2')].map(h => h.textContent)"


class Order(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.s.httpd.app_settings = service(make_db(d))

    def test_the_cards_and_the_tabs_are_in_the_approved_order_at_both_widths(self):
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
            js = lambda e: cdp.js(e, sid)          # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20))
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                js("document.querySelector('[data-ask-tab=project]').click()")
                self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folders-card')"), 20), f"project tab at {w}")
                self.assertEqual(js("[...document.querySelectorAll('[data-ask-tab]')].map(b => b.innerText)"), ["All projects", "ABC"])
                self.assertEqual(js("[...document.querySelectorAll('[data-ask-tab]')].map(b => b.getAttribute('aria-current'))"), [None, "true"])
                got = js(HEADS)
                order = [got.index(h) for h in ("Asking in ABC", "Used from All projects", "Connectors in ABC", "Source folders for ABC", "Standing instructions")]
                self.assertEqual(order, sorted(order), f"project tab order at {w}: {got}")
                self.assertTrue(js("document.querySelector('#ask-used-all [data-ask-goall]').offsetHeight > 0"), "the Change link is on show")
                # Tab from the first card's switch walks forward through the cards in the page order
                js("document.querySelector('#ask-folders-card').scrollIntoView()")
                js("(document.querySelector('[data-ask-tab=project]')).focus()")
                seen = []
                for _ in range(40):
                    for kind in ("keyDown", "keyUp"):
                        cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9}, sid)
                    seen.append(js("(()=>{const s=document.activeElement && document.activeElement.closest('#ask-tabs ~ section.frame.setting'); const h=s && s.querySelector('h2'); return h ? h.textContent : null;})()"))
                heads_seen = []
                for h in seen:
                    if h and h in got and (not heads_seen or heads_seen[-1] != h):
                        if heads_seen and got.index(h) < got.index(heads_seen[-1]):
                            break          # focus left the last card and wrapped round the page
                        heads_seen.append(h)
                self.assertEqual(heads_seen, [x for x in got if x in heads_seen], f"Tab moves through the cards in page order at {w}: {heads_seen}")
                self.assertGreaterEqual(len(set(heads_seen)), 2, f"Tab reached more than one card at {w}: {heads_seen}")
                js("document.querySelector('[data-ask-tab=all]').click()")
                self.assertTrue(wait(lambda: js("!!document.querySelector('#ai-settings') && !!document.querySelector('#ask-all-folders')"), 20), f"all tab at {w}")
                got = js(HEADS)
                names = ["AI", "Other connectors found on this computer"]
                idx = [got.index(h) for h in names]
                self.assertEqual(idx, sorted(idx), f"all tab order at {w}: {got}")
                self.assertTrue(js("document.querySelector('#ai-settings').compareDocumentPosition(document.querySelector('#ask-connectors')) & 4"), "model card before connectors")
                self.assertTrue(js("document.querySelector('#ask-connectors').compareDocumentPosition(document.querySelector('#ask-instructions-all-card')) & 4"), "connectors before the standing instructions")
                self.assertTrue(js("document.querySelector('#ask-instructions-all-card').compareDocumentPosition(document.querySelector('#ask-all-folders')) & 4"), "instructions before the source folders")


BEFORE = "document.querySelector(%r).compareDocumentPosition(document.querySelector(%r)) & 4"


class ClassicOrder(unittest.TestCase):
    """Classic draws the Slash commands, Changes and safety and Usage cards; their order on both tabs, at both widths."""

    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code),
                         page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme.CLASSIC))
        self.addCleanup(self.s.close)
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.s.httpd.app_settings = service(make_db(d))

    def test_slash_folders_safety_usage_on_all_and_slash_after_standing_instructions_on_project(self):
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
            js = lambda e: cdp.js(e, sid)          # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20))
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                js("document.querySelector('[data-ask-tab=all]').click()")
                self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-usage-all') && !!document.querySelector('#ask-safety') && !!document.querySelector('#slash-all')"), 20), f"all tab at {w}")
                for a, b, what in (("#slash-all", "#ask-all-folders", "Slash commands before Source folders"),
                                   ("#ask-all-folders", "#ask-safety", "Source folders before Changes and safety"),
                                   ("#ask-safety", "#ask-usage-all", "Changes and safety before Usage")):
                    self.assertTrue(js(BEFORE % (a, b)), f"{what} at {w}: {js(HEADS)}")
                last = js("(()=>{const s=[...document.querySelectorAll('#ask-tabs ~ section.frame.setting')]; return s[s.length-1].id;})()")
                self.assertEqual(last, "ask-usage-all", f"Usage is last on the All tab at {w}")
                js("document.querySelector('[data-ask-tab=project]').click()")
                self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folders-card') && !!document.querySelector('#slash-project')"), 20), f"project tab at {w}")
                self.assertTrue(js(BEFORE % ("#ask-instructions-own-card", "#slash-project")), f"Standing instructions before Slash commands at {w}: {js(HEADS)}")


if __name__ == "__main__":
    unittest.main()
