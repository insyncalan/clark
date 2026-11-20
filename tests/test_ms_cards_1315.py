"""Row 1315: the Cards page is what main serves. The timeline, list and frame changes are Classic only (the Classic theme sets --tl-classic and carries every rule).

Run: python3 dev/run_tests.py test_ms_cards_1315
Proof, the same kind as the Work items rows: the md5 of every style block of the Cards page, and the md5 of the rendered Milestones page DOM
(Plan view with the timeline, the body after a milestone is opened, the Calendar view) at 1400 and 900 px. The values are those the build of main renders, with the time of day in the "last updated" line folded to HH:MM (it is shown in the local time zone of the machine, so it differs between a machine and the CI runner);
Row 1329 (ruling 20-11): the Plan | Movement switch, its hint and the forecast sentence left the DOM, so the DOM values changed once (the style md5 did not). If a Cards change is meant, the values change here and the owner ruling that allowed it is named in the commit.
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
CARDS_DOM_MD5 = {
    1400: {"plan": "e88326f760de32f80336e2c4136d549b", "open": "f416866be9c016dcb040044e755c91c4", "calendar": "114228c4a25dc8f9171e2953a5684a90"},
    900: {"plan": "e88326f760de32f80336e2c4136d549b", "open": "b01527fceaf7792441640f9d2b2f771d", "calendar": "114228c4a25dc8f9171e2953a5684a90"},
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
        return {k: hashlib.md5(re.sub(r"(last updated \d\d-\d\d-\d{4}) \d\d:\d\d", r"\1 HH:MM", v).encode("utf-8")).hexdigest() for k, v in out.items()}, out

    def test_the_rendered_milestones_dom_is_the_dom_main_renders_at_1400_and_900(self):
        got = {width: self.capture(width)[0] for width in (1400, 900)}
        self.assertEqual(got, CARDS_DOM_MD5)


if __name__ == "__main__":
    unittest.main()
