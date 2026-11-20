"""Row 1316 (review point): the published-page crumb (.ucf-crumb, shared with the editor page's .ucd-crumb in one Classic rule) is plain text in the Classic
Theme and keeps its own look under Cards, as Chrome computes it at 1400 and 900 px, light and dark. A synthetic <nav> carries the class, like the table test.

Run: python3 dev/run_tests.py test_theme_classic_ucf_crumb_1316
Fails, never skips, without Chrome."""
import tempfile
import time
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401
from test_server import chrome

from clark import page

NAME = "prototype-2.0"
SIZES = (1400, 900)
NAVS = '<nav id="f" class="ucf-crumb">Use cases</nav><nav id="d" class="ucd-crumb">Use cases</nav>'
PROBE = """(() => { const g = (s) => { const c = getComputedStyle(document.querySelector(s)); return [c.fontWeight, c.fontSize, c.textTransform, c.letterSpacing]; };
  const i = document.createElement('i'); i.style.fontSize = 'var(--size-caption)'; document.body.appendChild(i); const cap = getComputedStyle(i).fontSize; i.remove();
  return { f: g('#f'), d: g('#d'), caption: cap }; })()"""


class UcfCrumb(unittest.TestCase):
    def load(self, cdp, theme, width, scheme):
        path = Path(tempfile.mkdtemp(prefix="clark-test-")) / "p.html"
        path.write_text(page.page_html(branding=page.NO_BRAND, theme=theme), encoding="utf-8")
        self.addCleanup(lambda: (path.unlink(), path.parent.rmdir()))
        tid = cdp.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
        end = time.monotonic() + 20
        while cdp.js("document.readyState", sid) != "complete" and time.monotonic() < end:
            time.sleep(0.05)
        cdp.js("(() => { document.documentElement.setAttribute('data-theme', %r); const d = document.createElement('div'); d.innerHTML = %r; document.body.appendChild(d); })()" % (scheme, NAVS), sid)
        return cdp.js(PROBE, sid)

    def test_classic_crumb_is_plain_caption_text_on_both_pages(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    c = self.load(cdp, NAME, w, scheme)
                    tag = f"classic {scheme} {w}"
                    for which in ("f", "d"):
                        weight, size, case, track = c[which]
                        self.assertEqual((weight, size, case, track), ("400", c["caption"], "none", "normal"), f"{tag} {which}")

    def test_cards_keeps_its_own_crumb_look(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    c = self.load(cdp, None, w, scheme)
                    tag = f"cards {scheme} {w}"
                    self.assertNotEqual(c["f"], ["400", c["caption"], "none", "normal"], tag)
                    self.assertEqual(c["f"], c["d"], tag + ": the two crumbs look alike under Cards")


if __name__ == "__main__":
    unittest.main()
