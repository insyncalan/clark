"""Row 1333 probe (reads only, always passes): prints what the browser on this runner reports, so the macOS nightly failures can be told apart.
Run: python3 dev/run_tests.py test_probe_macos_1333
Lines start with PROBE: the reduced-motion media value, the 900 px header height, the Classic radius of '#md'::before, the settings menu hover fill, and which element has focus after the feedback tag opens.
Four more probes, each run through the setup of the test it mirrors and each caught so that it always passes:
  PROBE: radius   the computed border radius of '#md'::before and of the segments, as test_theme_global_1319 reads them (that test wants 8px)
  PROBE: hover    the settings menu row fill before and after the pointer moves, as test_settings_menu_1280 measures it
  PROBE: focus    document.activeElement after the feedback tag opens, as test_feedback_tag_browser_1298 reads it (that test wants fbt-message)
  PROBE: bar      the height of header.top in the published file, as test_published_one_bar measures it (that test wants 85 at 1400 and 125 at 900)
"""
import json
import time
import traceback
import unittest

import test_feedback_tag_browser_1298 as ft  # noqa: E402
import test_peek as tp  # noqa: E402
import test_published_one_bar as pob  # noqa: E402
import test_settings_menu_1280 as sm  # noqa: E402
import test_theme_global_1319 as tg  # noqa: E402
from clark import page  # noqa: E402
from test_server import chrome  # noqa: E402


def tearDownModule():
    for mod in (ft, pob):
        try:
            mod.tearDownModule()
        except Exception:  # noqa: BLE001
            pass


def only_mine(cls):
    """A subclass of a real test class keeps its setup and helpers but none of its tests."""
    for name in dir(cls):
        if name.startswith("test") and name not in cls.__dict__:
            setattr(cls, name, None)
    return cls


def say(kind, **fields):
    print("PROBE:", kind, json.dumps(fields, default=str), flush=True)


def guarded(kind):
    """The probe never fails the run: a problem is printed as a PROBE: line."""
    def wrap(fn):
        def run(self):
            try:
                fn(self)
            except Exception as exc:  # noqa: BLE001
                say(kind, error=repr(exc), where=traceback.format_exc().strip().splitlines()[-3:])
        run.__name__ = fn.__name__
        return run
    return wrap


class Probe(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page

    def test_probe(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                out = cdp.js("""(() => ({
                  reduce: matchMedia('(prefers-reduced-motion: reduce)').matches,
                  noPref: matchMedia('(prefers-reduced-motion: no-preference)').matches,
                  dpr: devicePixelRatio, ua: navigator.userAgent,
                  header: (document.querySelector('header, #top, .topbar') || {getBoundingClientRect: () => ({height: null})}).getBoundingClientRect().height,
                  mdRadius: (document.querySelector('#md') ? getComputedStyle(document.querySelector('#md'), '::before').borderRadius : 'no #md'),
                  font: getComputedStyle(document.body).fontFamily, fontSize: getComputedStyle(document.body).fontSize,
                  active: document.activeElement ? document.activeElement.tagName + '#' + document.activeElement.id : null }))()""", sid)
                print("PROBE:", width, json.dumps(out), flush=True)


@only_mine
class ProbeRadius(tg.Computed):
    @guarded("radius")
    def test_probe_radius(self):
        html = page.page_html(branding=page.NO_BRAND, theme=tg.NAME)
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for width in tg.SIZES:
                    sid = self.load(cdp, width, scheme, html)
                    out = cdp.js("""(() => { const g = (s, pe) => { const e = document.querySelector(s); return e ? getComputedStyle(e, pe || null).borderRadius : 'none'; };
                      return {mdBefore: g('#md', '::before'), md: g('#md'), sg: g('#sg'), sc: g('#sc'), cs: g('#cs'), b1: g('#b1'),
                        theme: document.documentElement.getAttribute('data-theme'), dpr: devicePixelRatio, ua: navigator.userAgent}; })()""", sid)
                    say("radius", width=width, scheme=scheme, **out)


@only_mine
class ProbeHover(sm.SettingsMenu1280):
    @guarded("hover")
    def test_probe_hover(self):
        for width in sm.WIDTHS:
            for mode in sm.MODES:
                with chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, width, mode)
                    row = "document.querySelector('.set-chip:not([aria-current])')"
                    before = p.js(f"getComputedStyle({row}).backgroundColor")
                    fills = []
                    for n in range(10):
                        r = p.js(f"(function(){{ const c = {row}; c.scrollIntoView({{block: 'nearest'}}); const b = c.getBoundingClientRect(); return [b.left + b.width - 3, b.top + b.height / 2]; }})()")
                        self.hover(p, r[0] - n % 2, r[1])
                        time.sleep(0.15)
                        fills.append(p.js(f"getComputedStyle({row}).backgroundColor"))
                    say("hover", width=width, mode=mode, before=before, fills=fills, last=fills[-1])


@only_mine
class ProbeFocus(ft.FeedbackTagBrowser):
    @guarded("focus")
    def test_probe_focus(self):
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js(f"{ft.BAR}.click()", sid)
            seen = []
            for _ in range(10):
                time.sleep(0.2)
                seen.append(cdp.js("(document.activeElement ? document.activeElement.tagName + '#' + document.activeElement.id : null)", sid))
            say("focus", where=where, dialog=cdp.js(f"!!{ft.DLG}", sid), active=seen, last=seen[-1], expanded=cdp.js(f"{ft.BAR}.getAttribute('aria-expanded')", sid))


@only_mine
class ProbeBar(pob.InTheFile):
    @guarded("bar")
    def test_probe_bar(self):
        for width, dark in pob.CASES:
            cdp, p = self.bar(width, dark)
            b = p.js(pob.BAR)
            say("bar", width=width, dark=dark, height=b["bar"]["h"], rect=b["bar"], topbarVar=b["topbarVar"], pos=b["pos"], tabs=b["tabs"], name=b["name"], line=b["line"], logoBox=b["logoBox"])
        self.close()


if __name__ == "__main__":
    unittest.main()
