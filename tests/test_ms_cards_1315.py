"""Row 1315: the Cards page is what main serves. The timeline, list and frame changes are Classic only (the Classic theme sets --tl-classic and carries every rule).

Run: python3 dev/run_tests.py test_ms_cards_1315
Proof, the same kind as the Work items rows: the md5 of every style block of the Cards page, and the md5 of the rendered Milestones page DOM
(Plan view with the timeline, the body after a milestone is opened, the Calendar view, the Movement view) at 1400 and 900 px. The values are those the build of main renders, with the time of day in the "last updated" line folded to HH:MM (it is shown in the local time zone of the machine, so it differs between a machine and the CI runner);
if a Cards change is meant, the values change here and the owner ruling that allowed it is named in the commit.
"""
import hashlib
import re
import unittest

from _demo import USER
from clark import page
from test_milestones_page import BrowserBase, EMPTY_BRANDING
from test_server import Running, chrome, wait

HASH = "#milestones&p=TUL"
CARDS_STYLE_MD5 = {"blocks": ["7195b3107c3b5022f3b40ad1dfbbe484"]}
# row 1466 was reversed by the owner on PR 2255: the opened milestone peek says Client wording again, so the pinned "open" hashes are the old ones.
CARDS_DOM_MD5 = {
    1400: {"plan": "884d48fa51c42a792db825a88e2d5390", "open": "f880cee0281bb5a0f2ed6cbcb7c44e39", "calendar": "489268a179f71d1b61c6a35aa6444408", "move": "4e910e9f8f41236bc3810c2ae74045f3"},
    900: {"plan": "884d48fa51c42a792db825a88e2d5390", "open": "a47b575a7ad86e2e18674c92043a9ff6", "calendar": "489268a179f71d1b61c6a35aa6444408", "move": "4e910e9f8f41236bc3810c2ae74045f3"},
}


def style_md5s(html):
    return [hashlib.md5(b.encode("utf-8")).hexdigest() for b in re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)]


class CardsStyleBlocks(unittest.TestCase):
    def test_every_style_block_of_the_cards_page_has_the_md5_main_has(self):
        self.assertEqual(style_md5s(page.page_html(branding=page.NO_BRAND, theme=None)), CARDS_STYLE_MD5["blocks"])


class CardsDom(BrowserBase, unittest.TestCase):
    def serve(self):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects,
                    page_html=lambda: page.page_html(EMPTY_BRANDING, theme=None))
        self.addCleanup(s.close)
        return s.port

    def capture(self, width):
        out = {}
        with chrome() as cdp:
            sid = self.visit(cdp, width, HASH, self.serve())
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-lab').length > 0", sid)))
            grab = "document.querySelector('#milestones').outerHTML"
            out["plan"] = cdp.js(grab, sid)
            self.assertNotIn("data-look", out["plan"], "Cards carries no Classic look mark")
            cdp.js("document.querySelector('.mv-mk').click()", sid)
            out["open"] = cdp.js("(() => { const b = document.body.cloneNode(true); b.querySelectorAll('script, style').forEach((e) => e.remove()); return b.outerHTML; })()", sid)      # the whole body less its script and style text: an opened milestone may draw outside the page block
            cdp.js("document.querySelector('[data-msvb=cal]').click()", sid)
            wait(lambda: cdp.js("!!document.querySelector('.cal')", sid))
            out["calendar"] = cdp.js(grab, sid)
            cdp.js("document.querySelector('[data-msvb=tl]') && document.querySelector('[data-msvb=tl]').click()", sid)
            wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid))
            cdp.js("(() => { const f = window.fetch; window.fetch = (u, o) => /\\/api\\/movement/.test(String(u && u.url || u)) ? new Promise(() => {}) : f.call(window, u, o); })()", sid)      # this server has no movement route: left alone, Movement.jsx flips from "Loading Movement." (the pin) to "couldn't be loaded" while we hash; hold the read so the loading text stays
            cdp.js("document.querySelector('[data-mspv=move]') && document.querySelector('[data-mspv=move]').click()", sid)
            wait(lambda: cdp.js("!document.querySelector('.mv-wrap')", sid))
            out["move"] = cdp.js(grab, sid)
        return {k: hashlib.md5(re.sub(r"(last updated \d\d-\d\d-\d{4}) \d\d:\d\d", r"\1 HH:MM", v).encode("utf-8")).hexdigest() for k, v in out.items()}, out

    def test_the_rendered_milestones_dom_is_the_pinned_dom_at_1400_and_900(self):
        got = {width: self.capture(width)[0] for width in (1400, 900)}
        self.assertEqual(got, CARDS_DOM_MD5)


if __name__ == "__main__":
    unittest.main()
