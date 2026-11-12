"""Row 1023: the brand's page background picture, on every page of the app AND of the published file. In a real browser.

Run: python3 dev/run_tests.py test_brand_backdrop        (Chrome required: these fail, never skip, without it)
The prototype's body::before (system/prototype/app.css:634) is a fixed picture behind every page, below the top bar, over the right 60%
and fading in from the left; the ask panel keeps its head strip and gets the faint wash at its foot (app.css:555, :583). Owner ruling
(08-11-2026, over the first one): the published file gets it too, from the --image-cover it already carries for the report band (no
second copy of the picture), and a brand with no picture leaves the page byte for byte what it was. Text over the picture keeps 4.5:1
in light and dark, measured from the drawn pixels, in the app (900, 1400) and in a published file (900, 1400). Print and PDF: none;
reduced motion: no fade-in. The brand here is a temporary folder; no real brand is read.
"""
import base64
import json
import re
import tempfile
import time
import unittest
from pathlib import Path

import _backdrop_pics as pics
import _testpage as testpage
from _paths import SRC
from _publish import PublishedFile
from test_glance_page import plant
from test_report_editor import Base, Pg
from test_server import chrome, wait

import shutil

from _demo import USER, DemoStore
from clark import page, publish as pm

TOKENS = ':root { --image-cover: url("assets/cover.png"); }'
PAGES = (("Dashboard", "#dashboard&p=ABC", ".glance"), ("Work items", "#work&p=ABC", "#work"), ("Milestones", "#milestones&p=ABC", ".msv"),
         ("Settings", "#settings&p=ABC", ".set-head"))
MARKERS = ("body::before", "bg-in")          # what the new rules are made of: a file with no brand picture holds none of it

BACKDROP = """(() => { const s = getComputedStyle(document.body, '::before'), r = document.body.getBoundingClientRect();
  return {image: s.backgroundImage, position: s.position, top: parseFloat(s.top), left: s.left, z: s.zIndex, events: s.pointerEvents, size: s.backgroundSize,
          repeat: s.backgroundRepeat, anim: s.animationName, display: s.display, content: s.content, opacity: s.opacity, w: document.documentElement.clientWidth, h: innerHeight,
          bar: parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--topbar')) || 0,
          sh: document.documentElement.scrollHeight, sw: document.documentElement.scrollWidth, mask: s.maskImage || s.webkitMaskImage}; })()"""
REQUESTS = "performance.getEntriesByType('resource').filter(e => /assets\\/cover/.test(e.name)).length"
def sheet(css, name):
    """JS that adds a constructed style sheet (the page's policy blocks a <style> element but not this) and remembers it as window[name]."""
    return ("(function(){var s=new CSSStyleSheet();s.replaceSync(%s);window[%s]=s;document.adoptedStyleSheets=[...document.adoptedStyleSheets,s];})()"
            % (json.dumps(css), json.dumps(name)))


PLAIN = sheet("body::before{content:none!important}", "__plain")
HIDE = sheet("body *, body *::placeholder {color:transparent!important;-webkit-text-fill-color:transparent!important;text-shadow:none!important;"
             "text-decoration-color:transparent!important;caret-color:transparent!important}", "__hide")
UNHIDE = "document.adoptedStyleSheets = document.adoptedStyleSheets.filter(s => s !== window.__hide)"
TEXTS = """(() => {
  const bar = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--topbar')) || 0, out = [];
  const a = (c) => { const m = c.match(/[\\d.]+/g).map(Number); return m.length > 3 ? m[3] : 1; };
  const w = document.createTreeWalker(document.querySelector('main') || document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) {
    if (!n.textContent.trim()) continue;
    const el = n.parentElement, cs = getComputedStyle(el);
    if (cs.visibility !== 'visible' || cs.display === 'none' || a(cs.color) === 0) continue;
    let covered = false;
    for (let e = el; e && e !== document.body && e !== document.documentElement; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (a(s.backgroundColor) > 0.05 || s.backgroundImage !== 'none') { covered = true; break; }
    }
    if (covered) continue;
    const range = document.createRange(); range.selectNodeContents(n);
    for (const r of range.getClientRects()) {
      if (r.width < 2 || r.height < 2 || r.top < bar || r.bottom > innerHeight || r.left < 0 || r.right > innerWidth) continue;
      out.push({t: n.textContent.trim().slice(0, 40), x: r.left, y: r.top, w: r.width, h: r.height, fg: cs.color});
    }
  }
  return out; })()"""


def lum(rgb):
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2])


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def branded(root):
    """The test page (with its hook) with the brand layered in as the served page does."""
    return page.layer_brand(testpage.html(), page.local_tokens(root))


class Rig(Base):
    """The served page with a brand folder that is ours to change; hits counts the requests the server got for a brand picture."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "assets").mkdir()
        self.hits = []
        self.s.httpd.page_html = lambda: branded(self.root)

        def picture(name):
            self.hits.append(name)
            return page.brand_picture(name, self.root)
        self.s.httpd.brand_picture = picture

    def brand(self, data=None):
        (self.root / "tokens.css").write_text(TOKENS, encoding="utf-8")
        (self.root / "assets" / "cover.png").write_bytes(data or pics.swirl())

    def unbrand(self):
        (self.root / "tokens.css").unlink()

    def load_app(self, cdp, hash_="#dashboard&p=ABC", ready=".glance", width=1400, scheme="light"):
        p = Pg.at(self, cdp, self.s.port, hash_)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
        p.until(f"!!document.querySelector({json.dumps(ready)})", f"{hash_} drew")
        p.js(f"document.documentElement.dataset.theme = {json.dumps(scheme)}")
        if (self.root / "tokens.css").exists():
            p.until(REQUESTS + " > 0", "the picture was asked for")
        return p


def steady(p):
    """Wait until the page stops growing (a page that fills in late is not the backdrop's doing)."""
    last, n = None, 0
    for _ in range(60):
        now = p.js("document.documentElement.scrollHeight")
        n = n + 1 if now == last else 0
        if n >= 4:
            return
        last = now
        time.sleep(0.25)


class Backdrop(Rig):
    def test_every_app_page_has_the_brand_picture_fixed_behind_it(self):
        self.brand()
        for name, hash_, ready in PAGES:
            for width in (1400, 900):
                with self.subTest(page=name, width=width), chrome() as cdp:
                    p = self.load_app(cdp, hash_, ready, width)
                    p.until(REQUESTS + " > 0", "the picture was asked for")
                    got = p.js(BACKDROP)
                    self.assertIn("assets/cover.png", got["image"])
                    self.assertEqual((got["position"], got["z"], got["events"], got["size"], got["repeat"]),
                                     ("fixed", "-1", "none", "cover", "no-repeat"))
                    self.assertAlmostEqual(got["top"], got["bar"], delta=1, msg="it starts under the top bar")
                    self.assertAlmostEqual(float(got["left"][:-2]), got["w"] * 0.4, delta=8, msg="over the right 60%")
                    self.assertTrue(got["mask"] and got["mask"] != "none", "it fades in from the left")

    def test_help_has_it_too(self):
        self.brand()
        from test_help_panel import full_help_from_menu
        with chrome() as cdp:
            p = self.load_app(cdp)
            full_help_from_menu(p)
            self.assertIn("assets/cover.png", p.js(BACKDROP)["image"])

    def test_it_costs_no_layout(self):
        self.brand()
        for name, hash_, ready in PAGES:
            with self.subTest(page=name), chrome() as cdp:
                p = self.load_app(cdp, hash_, ready)
                p.until(REQUESTS + " > 0", "the picture was asked for")
                steady(p)
                with_it = p.js(BACKDROP)
                p.js(PLAIN)
                without = p.js(BACKDROP)
                self.assertEqual((with_it["sh"], with_it["sw"]), (without["sh"], without["sw"]), "the page is as long and wide as without it")

    def test_the_ask_panel_gets_the_wash_at_its_foot_and_keeps_the_head_strip(self):
        self.brand()
        with chrome() as cdp:
            p = self.load_app(cdp)
            p.js("document.querySelector('#ask-btn').click()")
            p.until("!!document.querySelector('#ask-panel')", "the panel opened")
            got = p.js("""(() => { const h = getComputedStyle(document.querySelector('.ask-head'), '::before'),
              f = getComputedStyle(document.querySelector('.ask-form'), '::before');
              return {head: h.backgroundImage, wash: f.backgroundImage, opacity: f.opacity, pos: f.position, height: f.height, z: f.zIndex, events: f.pointerEvents,
                      mask: f.maskImage || f.webkitMaskImage}; })()""")
            self.assertIn("assets/cover.png", got["head"], "the head strip (already there)")
            self.assertIn("assets/cover.png", got["wash"], "the wash at the foot")
            self.assertEqual((got["pos"], got["height"], got["events"]), ("absolute", "340px", "none"))
            self.assertAlmostEqual(float(got["opacity"]), 0.2, delta=0.01)
            self.assertEqual(got["z"], "-1")


class Generic(Rig):
    """Ruling 3 and the guards: no own look, nothing drawn, nothing asked for; Brands remove returns the plain page."""

    def test_without_a_picture_nothing_is_drawn_and_nothing_is_asked_for(self):
        for name, hash_, ready in PAGES:
            with self.subTest(page=name), chrome() as cdp:
                p = self.load_app(cdp, hash_, ready)
                got = p.js(BACKDROP)
                self.assertEqual(got["image"], "none", "no background image on the pseudo-element")
                self.assertEqual(p.js("performance.getEntriesByType('resource').filter(e => /\\.(png|jpe?g|webp|svg)|assets\\//.test(e.name) || e.initiatorType === 'img').length"), 0,
                                 "no request for an image")
                p.js("document.querySelector('#ask-btn').click()")
                p.until("!!document.querySelector('#ask-panel')", "the panel opened")
                self.assertEqual(p.js("getComputedStyle(document.querySelector('.ask-form'), '::before').backgroundImage"), "none")
        self.assertEqual(self.hits, [], "the server was never asked for a brand picture")

    def test_no_brand_is_a_pixel_identical_page(self):
        with chrome() as cdp:
            p = self.load_app(cdp)
            p.until("document.getAnimations().every(a => a.playState === 'finished')", "settled")
            shot = lambda: cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]       # noqa: E731
            before = shot()
            p.js(PLAIN)
            self.assertEqual(shot(), before, "the rules draw nothing: the screenshot is the same with them switched off")

    def test_removing_the_brand_returns_the_plain_page(self):
        self.brand()
        with chrome() as cdp:
            p = self.load_app(cdp)
            self.assertIn("assets/cover.png", p.js(BACKDROP)["image"])
        self.unbrand()
        self.hits.clear()
        with chrome() as cdp:
            p = self.load_app(cdp)
            self.assertEqual(p.js(BACKDROP)["image"], "none")
        self.assertEqual(self.hits, [])


class Guards(Rig):
    def test_reduced_motion_has_no_fade_in_animation(self):
        self.brand()
        with chrome() as cdp:
            p = self.load_app(cdp)
            self.assertEqual(p.js(BACKDROP)["anim"], "bg-in", "motion allowed: the picture fades in once")
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
            p.until(BACKDROP + '.anim === "none"', "reduced motion reached the backdrop")
            self.assertEqual(p.js(BACKDROP)["anim"], "none")
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]}, p.sid)
            p.js("document.documentElement.dataset.motion = 'reduce'")
            p.until(BACKDROP + '.anim === "none"', "the page's own reduce setting reached the backdrop")
            self.assertEqual(p.js(BACKDROP)["anim"], "none", "the page's own reduce-motion setting too")

    def test_print_and_pdf_have_no_backdrop(self):
        self.brand()
        with chrome() as cdp:
            p = self.load_app(cdp)
            self.assertNotEqual(p.js(BACKDROP)["display"], "none")
            cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, p.sid)
            self.assertEqual(p.js(BACKDROP)["display"], "none")





class Measure:
    """Text that sits straight on the page (not on a card) over the picture keeps 4.5:1, measured from the drawn pixels: the page is drawn
    once with its text made clear, and each text's rectangle is compared with the text's own colour, worst pixel."""

    def worst(self, cdp, p, what, need=True):
        p.until("document.getAnimations().every(a => a.playState === 'finished')", "settled")
        items = p.js(TEXTS)
        if need:
            self.assertGreater(len(items), 0, f"{what}: some text sits on the page")
        p.js(HIDE)
        w, h, rows = pics.decode(base64.b64decode(cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]))
        p.js(PLAIN)             # the same page without the picture: a pixel the picture did not change is the page's own (a chip, a rule) and not the picture's to answer for
        _, _, bare = pics.decode(base64.b64decode(cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]))
        p.js("document.adoptedStyleSheets = document.adoptedStyleSheets.filter(s => s !== window.__plain)")
        p.js(UNHIDE)
        low = (99.0, None)
        for it in items:
            fg = [float(v) for v in re.findall(r"[\d.]+", it["fg"])][:3]
            for y in range(int(it["y"]), min(h, int(it["y"] + it["h"]) + 1), 2):
                for x in range(int(it["x"]), min(w, int(it["x"] + it["w"]) + 1), 2):
                    if rows[y][x] == bare[y][x]:
                        continue
                    r = ratio(fg, rows[y][x])
                    if r < 4.5 and r >= 0.95 * ratio(fg, bare[y][x]):
                        r = 4.5       # the page's own pair is as low without the picture (a chip's own colours): not the picture's doing
                    if r < low[0]:
                        low = (r, it["t"] + f" fg={it['fg']} px={rows[y][x]} at {int(it['x'])},{int(it['y'])}")
        return low, [i["t"] for i in items]

    def verdict(self, cdp, p, what, need=True):
        (r, t), texts = self.worst(cdp, p, what, need)
        print(f"contrast {what}: {r:.2f}:1 ({t!r}, {len(texts)} texts)")
        self.assertGreaterEqual(r, 4.5, f"{what}: {t!r} is {r:.2f}:1 over the picture")
        return r, texts


WORST = {"light": (0, 0, 0), "dark": (255, 255, 255)}        # the picture that hurts most: black behind dark text, white behind light text


class AppContrast(Measure, Rig):
    def test_page_text_keeps_4_5_to_1_over_the_picture_in_the_app(self):
        for scheme in ("light", "dark"):
            for pic_name, data in (("swirl", pics.swirl()), ("worst", pics.solid(WORST[scheme]))):
                self.brand(data)
                for width in (1400, 900):
                    for name, hash_, ready in PAGES:
                        with self.subTest(page=name, scheme=scheme, width=width, picture=pic_name), chrome() as cdp:
                            p = self.load_app(cdp, hash_, ready, width, scheme)
                            self.verdict(cdp, p, f"app {name} {scheme} {width} {pic_name}")

    def test_work_items_links_discard_changes_and_save_as_a_new_view(self):
        for scheme in ("light", "dark"):
            self.brand(pics.solid(WORST[scheme]))
            for width in (1400, 900):
                for _ in range(3):
                    self.demo.action(owner="Sam Lee", client_visible=1)
                with self.subTest(scheme=scheme, width=width), chrome() as cdp:
                    p = self.load_app(cdp, "#work&p=ABC", "#fline-input", width, scheme)
                    p.js("document.querySelector('#fline-input').focus()")
                    cdp.call("Input.insertText", {"text": "status is Open"}, p.sid)
                    p.until("[...document.querySelectorAll('main button, main a')].some(e => /Discard changes/.test(e.textContent))", "Discard changes shows")
                    r, texts = self.verdict(cdp, p, f"app Work items links {scheme} {width}")
                    self.assertTrue(any("Discard changes" in t for t in texts), texts)
                    self.assertTrue(width < 1000 or any("+ New view" in t for t in texts), "the bare link that saves a new view is measured: " + str(texts))
                    p.js("document.querySelector('#viewTabMenu').click()")
                    p.until("!!document.querySelector('#viewTabMenuList')", "the tab menu opened")
                    got = p.js("""(() => { const m = document.querySelector('#viewTabMenuList'), i = [...m.querySelectorAll('[role=menuitem]')].find(e => /Save as a new view/.test(e.textContent));
                      const c = getComputedStyle(m).backgroundColor.match(/[\\d.]+/g).map(Number); return {item: !!i, alpha: c.length > 3 ? c[3] : 1}; })()""")
                    self.assertTrue(got["item"], "Save as a new view is in the tab's menu")
                    self.assertEqual(got["alpha"], 1, "and the menu is an opaque card: that text is not over the picture")


def data_tokens(png):
    """The brand's tokens with its picture embedded as data, the form a published file can carry."""
    return ':root { --image-cover: url("data:image/png;base64,%s"); }' % base64.b64encode(png).decode()


class Pub(PublishedFile, unittest.TestCase):
    """A real file published from a real store, with a brand folder that is ours to change, opened from file://."""

    def setUp(self):
        # a store and the rows, nothing more: the file is opened from file:// and no test here asks a server for anything, so none is
        # started (one that stalls on starting or on closing took a test that never touches it past 700 s)
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        plant(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.brand_dir = Path(tmp.name)

    def publish_with(self, tokens):
        if tokens is not None:
            (self.brand_dir / "tokens.css").write_text(tokens, encoding="utf-8")
        elif (self.brand_dir / "tokens.css").exists():
            (self.brand_dir / "tokens.css").unlink()
        self.out = tempfile.mkdtemp(prefix="clark-1023-")
        self.addCleanup(shutil.rmtree, self.out, ignore_errors=True)
        done = pm.publish(self.store, "ABC", self.out, by_user=USER, now="2026-10-28", branding=self.brand_dir)
        return Path(done["path"])

    def draw_as(self, cdp, path, width, scheme, hash_="#dashboard&p=ABC"):
        p = self.draw(cdp, path, width, scheme == "dark")
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
        if hash_ != "#dashboard&p=ABC":
            p.js(f"location.hash = {json.dumps(hash_)}")
            time.sleep(0.8)
        p.js(f"document.documentElement.dataset.theme = {json.dumps(scheme)}")
        return p


PUBLISHED_PAGES = (("Dashboard", "#dashboard&p=ABC"), ("Work items", "#work&p=ABC"), ("Milestones", "#milestones&p=ABC"), ("Use cases", "#usecases&p=ABC"))


class Published(Measure, Pub):
    """Owner ruling 08-11-2026: the published file has the backdrop on all its pages, from the picture it already carries."""

    def test_every_published_page_has_the_picture_fixed_behind_it(self):
        path = self.publish_with(data_tokens(pics.swirl()))
        for name, hash_ in PUBLISHED_PAGES:
            for width in (1400, 900):
                with self.subTest(page=name, width=width), chrome() as cdp:
                    p = self.draw_as(cdp, path, width, "light", hash_)
                    got = p.js(BACKDROP)
                    self.assertIn("data:image/png", got["image"])
                    self.assertEqual((got["position"], got["z"], got["events"], got["size"], got["repeat"]),
                                     ("fixed", "-1", "none", "cover", "no-repeat"))
                    self.assertAlmostEqual(got["top"], got["bar"], delta=1)
                    self.assertAlmostEqual(float(got["left"][:-2]), got["w"] * 0.4, delta=8)
                    self.assertTrue(got["mask"] and got["mask"] != "none")

    def test_the_picture_is_in_the_file_once_and_the_file_grows_by_the_rules_only(self):
        png = pics.swirl()
        b64 = base64.b64encode(png).decode()
        with_pic = self.publish_with(data_tokens(png)).read_text(encoding="utf-8")
        plain = self.publish_with(":root { --image-cover: none; --note: 1; }").read_text(encoding="utf-8")
        self.assertEqual(with_pic.count(b64), 1, "one copy of the picture: the band and the backdrop both use var(--image-cover)")
        self.assertLessEqual(len(with_pic) - len(plain), len(b64) + len(page.BACKDROP_CSS) + 200, "no second copy: it grows by the picture once and the rules")

    def test_a_brand_with_no_picture_leaves_the_file_as_it_was(self):
        for tokens in (None, ":root { --image-cover: none; --brand-navy: #123456; }"):
            text = self.publish_with(tokens).read_text(encoding="utf-8")
            for m in MARKERS:
                self.assertNotIn(m, text, f"{tokens!r}: {m}")
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        self.assertEqual(page.layer_brand(view, None), view)
        css = ":root { --image-cover: none; --brand-navy: #123456; }"
        self.assertEqual(page.layer_brand(view, css), page.layer_brand(view, css).replace(page.BACKDROP_CSS, ""), "no rule added")
        i = page.after_demo_block(view)
        self.assertEqual(page.layer_brand(view, css), view[:i] + f'\n<style id="brand-local">\n{page.CLIENT_BRAND}{css}\n</style>' + view[i:],
                         "exactly the block it was before this row")

    def test_nothing_is_drawn_without_a_picture(self):
        path = self.publish_with(None)
        with chrome() as cdp:
            p = self.draw_as(cdp, path, 1400, "light")
            self.assertEqual(p.js(BACKDROP)["image"], "none")
            self.assertEqual(p.js("performance.getEntriesByType('resource').length"), 0, "no request")

    def test_reduced_motion_and_print(self):
        path = self.publish_with(data_tokens(pics.swirl()))
        with chrome() as cdp:
            p = self.draw_as(cdp, path, 1400, "light")
            self.assertEqual(p.js(BACKDROP)["anim"], "bg-in")
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
            p.until(BACKDROP + '.anim === "none"', "reduced motion reached the backdrop")
            self.assertEqual(p.js(BACKDROP)["anim"], "none")
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]}, p.sid)
            p.until(BACKDROP + '.display !== "none"', "motion allowed again, the backdrop is drawn")
            self.assertNotEqual(p.js(BACKDROP)["display"], "none")
            cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, p.sid)
            p.until(BACKDROP + '.display === "none"', "print reached the backdrop")
            self.assertEqual(p.js(BACKDROP)["display"], "none", "paper and PDF: no backdrop")

    def test_published_text_keeps_4_5_to_1_over_the_picture(self):
        for scheme in ("light", "dark"):
            for pic_name, png in (("swirl", pics.swirl()), ("worst", pics.solid(WORST[scheme]))):
                path = self.publish_with(data_tokens(png))
                for width in (1400, 900):
                    for name, hash_ in PUBLISHED_PAGES:
                        with self.subTest(page=name, scheme=scheme, width=width, picture=pic_name), chrome() as cdp:
                            p = self.draw_as(cdp, path, width, scheme, hash_)
                            self.verdict(cdp, p, f"published {name} {scheme} {width} {pic_name}", need=False)      # the published page seats its text on its own cards: what sits bare on the page is checked, and may be nothing


class Packaging(unittest.TestCase):
    def test_the_rules_ride_with_the_brand_block_only_when_the_brand_has_a_picture(self):
        view = testpage.html()
        for css, has in ((None, False), (":root { --image-cover: none; }", False), (":root{--image-cover:NONE}", False),
                         (":root{--image-cover:inherit}", False), (":root{--image-cover: Unset}", False), (":root{--image-cover:initial}", False),
                         (":root{--image-cover:revert}", False), (":root{--image-cover:revert-layer}", False), (":root { --a: 1; }", False),
                         (':root { --image-cover: url("data:image/png;base64,AAAA"); }', True), (':root{--image-cover:url(assets/cover.png)}', True)):
            with self.subTest(css=css):
                out = page.layer_brand(view, css)
                self.assertEqual(page.BACKDROP_CSS in out, has)
        self.assertNotIn("opacity: .14; }\n:root[data-theme=dark]", page.BACKDROP_CSS, "no dark-mode rule that repeats the base opacity")
        self.assertEqual(page.BACKDROP_CSS.count("opacity: .14"), 1, "the one opacity is the base rule: a dark rule with the same value does nothing")
        self.assertNotIn("body::before", (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8").replace(".cover::before", ""),
                         "not in shell.css: the rules are added only with a picture, or a brand without one would change the file")


if __name__ == "__main__":
    unittest.main()
