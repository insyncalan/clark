"""Row 1233 (gal 2), Image gallery: the Classic Edit part of a gallery with an image, in a real browser on a bare page with a stand-in for clark's routes
(tests/fixtures/gallery_edit_demo.jsx) that logs every call. What the page SENDS and DRAWS at 1400 and 900 px, by the acceptance points of #1233: AP1 the
grid, AP2 two across at half width and at 900, AP3 the tile and the select frame, AP5 the add tile, AP12 the toolbar, AP13 the fields and the count note,
AP16 the seventh image. The server's own checks are test_gallery_v2_server.py's. Gal 3 adds AP8 (the bin on a tile) and Remove by the toolbar bin and the Delete key. Not in this slice (later ones): drag by the dots, the
focus dot, Crop, Reset, the red mark, the columns and shape controls, the empty gallery's large area. Fictional data only.

Run: python3 dev/run_tests.py test_tpl_gallery_edit
Needs Chrome (the #33 harness): fails, never skips, without it.
"""
import contextlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC
from test_server import Running, chrome, wait
from test_tpl_gallery_view import pictures

PAGE = SRC / "clark" / "page"
DEMO = ROOT / "tests" / "fixtures" / "gallery_edit_demo.jsx"
THEME = SRC / "clark" / "themes" / "prototype-2.0"
_BUNDLE = {}

HELPERS = """
window.mkfiles = async (n, w, h, size) => { const out = []; for (let i = 0; i < n; i++) { const c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d'); g.fillStyle = 'rgb(' + (40 + i * 30) + ',160,60)'; g.fillRect(0, 0, w, h);
  const blob = await new Promise(r => c.toBlob(r, 'image/png')); out.push(size ? new File([new Uint8Array(size)], 'fictional' + i + '.png', { type: 'image/png' }) : new File([blob], 'fictional' + i + '.png', { type: 'image/png' })); }
  return out; };
window.pick = async (n, w, h, size) => { const dt = new DataTransfer(); (await window.mkfiles(n, w || 400, h || 300, size)).forEach(f => dt.items.add(f));
  const i = document.querySelector('input[type=file]'); i.files = dt.files; i.dispatchEvent(new Event('change', { bubbles: true })); return true; };
window.dropOn = async (n) => { const dt = new DataTransfer(); (await window.mkfiles(n, 400, 300)).forEach(f => dt.items.add(f));
  const t = document.querySelector('.gal-classic'); t.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true })); return true; };
"""


def bundle():
    if "js" not in _BUNDLE:
        sys.path.insert(0, str(ROOT / "dev" / "tools"))
        import build_page
        import esbuild
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE / 'src'}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["js"] = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
    return _BUNDLE["js"]


def html(classic):
    css = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "clark" / "brand" / "tokens.css", PAGE / "shell.css", PAGE / "src" / "edit" / "edit.css"))
    layer = f'<style id="theme">{"".join((THEME / n).read_text(encoding="utf-8") for n in ("rules.css", "rules-2.css"))}</style>' if classic else ""
    return ('<!doctype html>\n<html lang="en-GB" data-theme="light"><head><meta charset="utf-8"><title>t</title>'
            f'<style>{css}</style>{layer}</head>\n<body><script id="clark-boot" type="application/json">{{"token":"t"}}</script>'
            f'<div id="root"></div>\n<script>{bundle()}</script>\n</body></html>\n')


def body_of(n, alts=(), caps=(), extra=None):
    pics = pictures(n)
    b = {"v": 2, "pictures": {str(i + 1): p["image"] for i, p in enumerate(pics)}}
    items = {}
    for i in range(n):
        one = {}
        if i in alts:
            one["alt"] = f"Fictional description {i + 1}"
        if i in caps:
            one["caption"] = f"Fictional caption {i + 1}"
        if one:
            items[str(i + 1)] = one
    if items:
        b["items"] = items
    b.update(extra or {})
    return b


class Base(unittest.TestCase):
    classic = True

    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=lambda: html(cls.classic))
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!window.G", cls.sid)), "the test bundle ran"
        cls.cdp.js(HELPERS, cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def val(self, expr, promise=False):
        if promise:
            self.cdp.js(f"window.__got = undefined; Promise.resolve({expr}).then(v => window.__got = JSON.stringify(v === undefined ? null : v), e => window.__got = 'ERROR ' + e.message)", self.sid)
            self.assertTrue(wait(lambda: self.cdp.js("window.__got !== undefined", self.sid), 30), expr)
            got = self.cdp.js("window.__got", self.sid)
        else:
            got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertFalse(str(got).startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got) if got and got != "undefined" else None

    def until(self, expr, what, seconds=20):
        self.assertTrue(wait(lambda: self.cdp.js(f"!!({expr})", self.sid), seconds), f"{what}; page: {self.val('document.body.innerText.slice(-300)')}")

    def mount(self, body=None, page=1400, width=1300):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": page, "height": 1400, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        text = json.dumps(json.dumps(body)) if body else '""'
        self.val(f"G.mount({{id: 'ABC-S-1', body: {text}}}, {width})")
        self.until("document.querySelector('#root').children.length", "drawn")

    def calls(self):
        return self.val("G.server.calls")

    def body(self):
        return self.val("G.body('ABC-S-1')")

    def tiles(self):
        return self.val("document.querySelectorAll('.gal-tile').length")

    def settled(self, n):
        self.until(f"G.server.calls.length >= {n}", f"{n} calls, got {[(c.get('slot'), c.get('op')) for c in self.calls()]}")
        self.until("!document.querySelector('.fi-btn:disabled[data-act=add]') || document.querySelectorAll('.gal-tile').length >= 6", "no longer busy")

    def toast(self):
        return self.val("(G.toast.value || {}).text || ''")



ACROSS = "getComputedStyle(document.querySelector('[data-gal-grid]')).gridTemplateColumns.split(' ').length"


class Classic(Base):
    def test_gallery_edit_grid_ap1_three_across_gap_12_equal_columns_at_1400(self):
        self.mount(body_of(6, alts=range(6)), 1400, 1300)
        self.assertEqual(self.val(ACROSS), 3)
        self.assertEqual(self.val("getComputedStyle(document.querySelector('[data-gal-grid]')).columnGap"), "12px")
        self.assertEqual(self.val("getComputedStyle(document.querySelector('[data-gal-grid]')).rowGap"), "12px")
        widths = self.val("Array.from(document.querySelectorAll('.gal-tile')).map(t => Math.round(t.getBoundingClientRect().width))")
        self.assertEqual(len(set(widths)), 1, widths)

    def test_ap2_two_across_in_a_half_width_section_and_at_900_whatever_columns_says(self):
        for page, width, want in ((1400, 1300, 3), (1400, 641, 3), (1400, 640, 2), (1400, 500, 2), (900, 800, 2)):
            for extra in ({"columns": 3}, {}):
                with self.subTest(page=page, width=width, extra=extra):
                    self.mount(body_of(6, alts=range(6), extra=extra), page, width)
                    self.assertEqual(self.val(ACROSS), want)
                    self.assertLessEqual(self.val("document.documentElement.scrollWidth"), page, "no sideways scroll")
        self.mount(body_of(6, alts=range(6), extra={"columns": 2}), 1400, 1300)
        self.assertEqual(self.val(ACROSS), 2, "a stored two across is drawn two across")

    def test_ap3_tile_radius_12_with_a_2px_border_and_the_selected_one_has_the_accent_frame_ap4_frame_radius_9(self):
        for page in (1400, 900):
            with self.subTest(page=page):
                self.mount(body_of(3, alts=(0, 1, 2)), page, page - 100)
                css = "(function(i){ const s = getComputedStyle(document.querySelectorAll('.gal-tile')[i]); return [s.borderTopWidth, s.borderTopLeftRadius, s.borderTopColor]; })"
                self.assertEqual(self.val(f"{css}(1)")[:2], ["2px", "12px"])
                self.assertEqual(self.val(f"{css}(1)")[2], "rgba(0, 0, 0, 0)", "not selected: a transparent border")
                self.assertEqual(self.val("document.querySelectorAll('.gal-tile.sel').length"), 1)
                self.assertEqual(self.val("document.querySelector('.gal-tile.sel').dataset.slot"), "1", "the first is selected to begin with")
                self.val("document.querySelectorAll('.gal-tile')[1].click()")
                self.until("document.querySelectorAll('.gal-tile')[1].classList.contains('sel')", "the second is selected")
                self.assertEqual(self.val("document.querySelectorAll('.gal-tile.sel').length"), 1)
                self.assertEqual(self.val(f"{css}(1)")[2], self.val("(function(){ const d = document.createElement('i'); d.style.color = 'var(--brand-blue)'; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; })()"), "the accent")
                self.assertEqual(self.val("(function(){ const s = getComputedStyle(document.querySelector('.gal-frame')); return [s.borderTopLeftRadius, s.overflow, s.backgroundColor]; })()"),
                                 ["9px", "hidden", "rgb(232, 237, 248)"])
                self.assertEqual(self.val("getComputedStyle(document.querySelector('.gal-frame img')).objectFit"), "cover")

    def test_ap5_add_tile_is_dashed_2px_radius_12_at_least_120_tall_after_the_last_image_and_gone_at_six(self):
        for page in (1400, 900):
            with self.subTest(page=page):
                self.mount(body_of(3, alts=(0, 1, 2)), page, page - 100)
                self.assertEqual(self.val("(function(){ const s = getComputedStyle(document.querySelector('.gal-addtile')); return [s.borderTopStyle, s.borderTopWidth, s.borderTopColor, s.borderTopLeftRadius, s.color, parseFloat(s.minHeight)]; })()"),
                                 ["dashed", "2px", "rgb(184, 193, 220)", "12px", "rgb(106, 117, 146)", 120])
                self.assertEqual(self.val("document.querySelector('.gal-addtile').innerText.replace('+', '').trim()"), "Add an image")
                self.assertEqual(self.val("(function(){ const k = Array.from(document.querySelector('[data-gal-grid]').children); return [k.length, k[3].classList.contains('gal-addtile')]; })()"), [4, True])
        self.mount(body_of(6, alts=range(6)))
        self.assertEqual(self.val("document.querySelectorAll('.gal-addtile').length"), 0)
        self.assertTrue(self.val("document.querySelector('[data-act=add]').disabled"), "the plus is out at six")
        self.assertEqual(self.val("document.querySelector('[data-act=add]').getAttribute('aria-label')"), "Six is the most")

    def test_choosing_images_sends_the_new_kind_once_then_each_image_to_its_own_slot_and_selects_the_last(self):
        self.mount(body_of(1, alts=(0,), extra={"v": 1}))
        self.val("pick(2)", True)
        self.until("G.server.calls.length >= 3 && document.querySelectorAll('.gal-tile').length === 3", "three tiles")
        calls = self.calls()
        self.assertEqual([c.get("op") or c.get("slot") for c in calls], ["update", "2", "3"])
        self.assertEqual(json.loads(calls[0]["changes"]["body"]), {"v": 2, "items": {"1": {"alt": "Fictional description 1"}}}, "the old kind becomes the new by its words alone")
        self.assertEqual(self.val("document.querySelector('.gal-tile.sel').dataset.slot"), "3")
        self.val("document.querySelector('[data-act=add]').click()")      # the plus opens the file window: it is the same input
        self.assertEqual(self.val("document.querySelectorAll('input[type=file]').length"), 1)

    def test_dropping_files_on_the_section_adds_them_up_to_six_and_five_on_four_free_says_the_ruled_line(self):
        self.mount(body_of(2, alts=(0, 1)))
        self.val("dropOn(5)", True)
        self.until("document.querySelectorAll('.gal-tile').length === 6", "six tiles")
        self.until("(G.toast.value || {}).kind === 'problem'", "the line is said")
        self.assertEqual(self.toast(), "Added 4 of the 5 files. A gallery holds up to six images.")
        self.assertEqual(sorted(self.body()["pictures"]), ["1", "2", "3", "4", "5", "6"])

    def test_ap16_a_seventh_image_is_refused_in_the_ruled_words_and_nothing_is_sent(self):
        for page in (1400, 900):
            with self.subTest(page=page):
                self.mount(body_of(6, alts=range(6)), page, page - 100)
                self.val("dropOn(1)", True)
                self.until("(G.toast.value || {}).kind === 'problem'", "said")
                self.assertEqual(self.toast(), "A gallery holds up to six images. Remove one to add another.")
                self.assertEqual(self.calls(), [])

    def test_a_file_over_the_limit_is_refused_before_it_is_sent(self):
        self.mount(body_of(1, alts=(0,)))
        self.val("pick(1, 400, 300, 10 * 1024 * 1024 + 1)", True)
        self.until("(G.toast.value || {}).kind === 'problem'", "said")
        self.assertEqual(self.toast(), "That file is too big. Choose one under 10 MB.")
        self.assertEqual(self.calls(), [])

    def test_ap13_the_selected_image_has_its_description_and_caption_under_the_toolbar_and_the_note_counts(self):
        self.mount(body_of(3, alts=(0, 2), caps=(1,)))
        self.assertEqual(self.val("document.querySelector('[data-gal-note]').innerText"),
                         "3 of 6 images. Each is made smaller to keep the file light (up to 1,600 px wide). The published page carries only the part you see in each tile.")
        self.val("document.querySelectorAll('.gal-tile')[1].click()")
        self.until("document.querySelector('label[for$=alt-2]')", "its fields")
        label = self.val("document.querySelector('label[for$=alt-2]').innerText")
        self.assertIn("Selected image 2: describe it", label)
        self.assertIn("for people who cannot see it", label)
        self.assertEqual(self.val("document.querySelector('[data-alt-note]').innerText"), "No description yet.")
        self.assertTrue(self.val("document.querySelector('.fi-bar').compareDocumentPosition(document.querySelector('input[id$=alt-2]')) & Node.DOCUMENT_POSITION_FOLLOWING"), "under the toolbar")

    def test_ap12_the_toolbar_is_one_tab_stop_with_names_and_the_page_does_not_scroll_sideways(self):
        for page in (1400, 900):
            with self.subTest(page=page):
                self.mount(body_of(3, alts=(0, 1, 2)), page, page - 100)
                self.assertEqual(self.val("document.querySelector('[role=toolbar]').getAttribute('aria-label')"), "Gallery tools")
                self.assertEqual(self.val("Array.from(document.querySelectorAll('.fi-bar button')).filter(b => b.tabIndex === 0).length"), 1)
                self.assertEqual(self.val("Array.from(document.querySelectorAll('.fi-bar button')).map(b => b.getAttribute('aria-label'))"), ["Replace the selected image", "Remove the selected image", "Add an image"])
                self.assertLessEqual(self.val("document.documentElement.scrollWidth"), page)

    # ---- gal 3: Remove (AP8, AP12 toolbar bin, the Delete key, Undo is the toast's apply_id) ----
    def test_ap8_the_bin_on_a_tile_is_26_square_radius_7_6px_from_top_and_right_named_and_shown_on_the_selected_tile(self):
        for page in (1400, 900):
            with self.subTest(page=page):
                self.mount(body_of(3, alts=(0, 1, 2)), page, page - 100)
                bin = "document.querySelectorAll('.gal-tile')[%d].querySelector('.gal-bin')"
                self.assertEqual(self.val(f"{bin % 0}.getAttribute('aria-label')"), "Remove image 1")
                self.assertEqual(self.val(f"{bin % 2}.getAttribute('aria-label')"), "Remove image 3")
                self.assertEqual(self.val(f"{bin % 0}.title"), "Remove this image")
                self.assertEqual(self.val(f"getComputedStyle({bin % 1}).display"), "none", "not shown on a tile that is neither hovered nor selected")
                self.assertEqual(self.val(f"(function(){{ const s = getComputedStyle({bin % 0}), t = document.querySelector('.gal-tile').getBoundingClientRect(), b = {bin % 0}.getBoundingClientRect();"
                                          " return [s.width, s.height, s.borderTopLeftRadius, s.backgroundColor, s.color, Math.round(b.top - t.top), Math.round(t.right - b.right)]; })()"),
                                 ["26px", "26px", "7px", "rgba(6, 47, 58, 0.78)", "rgb(255, 255, 255)", 8, 8], "6px in from the 2px tile border")
                self.assertEqual(self.val(f"getComputedStyle({bin % 0}.querySelector('svg')).width"), "15px")

    def test_the_bin_on_a_tile_takes_that_image_out_in_one_send_says_the_ruled_words_and_selects_the_next(self):
        self.mount(body_of(3, alts=(0, 1, 2)))
        self.val("document.querySelectorAll('.gal-tile')[1].querySelector('.gal-bin').click()")
        self.until("G.server.calls.length >= 1 && document.querySelectorAll('.gal-tile').length === 2", "two tiles")
        calls = self.calls()
        self.assertEqual([(c["slot"], c["image"]) for c in calls], [("2", None)], "one send: slot 2, no image")
        self.assertEqual(sorted(self.body()["pictures"]), ["1", "3"])
        self.assertNotIn("2", self.body().get("items", {}), "its words went with it")
        self.until("(G.toast.value || {}).text === 'Image removed.'", "the toast")
        self.assertRegex(self.val("(G.toast.value || {}).undo"), r"^A\d+$", "the toast carries the step to undo")
        self.assertEqual(self.val("document.querySelector('.gal-tile.sel').dataset.slot"), "3", "the next one is selected")

    def test_the_toolbar_bin_takes_out_the_selected_image_and_the_last_one_selects_the_one_before(self):
        self.mount(body_of(3, alts=(0, 1, 2)))
        self.assertEqual(self.val("Array.from(document.querySelectorAll('.fi-bar button')).map(b => b.getAttribute('aria-label'))"),
                         ["Replace the selected image", "Remove the selected image", "Add an image"])
        self.val("document.querySelectorAll('.gal-tile')[2].click()")
        self.until("document.querySelectorAll('.gal-tile')[2].classList.contains('sel')", "third selected")
        self.val("document.querySelector('[data-act=remove]').click()")
        self.until("G.server.calls.length >= 1 && document.querySelectorAll('.gal-tile').length === 2", "two tiles")
        self.assertEqual([(c["slot"], c["image"]) for c in self.calls()], [("3", None)])
        self.assertEqual(self.val("document.querySelector('.gal-tile.sel').dataset.slot"), "2")

    def test_the_delete_key_takes_out_the_selected_image_but_not_while_typing_in_a_box(self):
        self.mount(body_of(3, alts=(0, 1, 2)))
        key = "new KeyboardEvent('keydown', { key: 'Delete', bubbles: true, cancelable: true })"
        self.val(f"document.querySelector('input[id$=alt-1]').dispatchEvent({key})")
        self.assertEqual(self.calls(), [], "typing in the description box: nothing is removed")
        self.assertEqual(self.tiles(), 3)
        self.val("document.querySelectorAll('.gal-tile')[1].click()")
        self.until("document.querySelectorAll('.gal-tile')[1].classList.contains('sel')", "second selected")
        self.val(f"document.querySelectorAll('.gal-tile')[1].dispatchEvent({key})")
        self.until("G.server.calls.length >= 1 && document.querySelectorAll('.gal-tile').length === 2", "two tiles")
        self.assertEqual([(c["slot"], c["image"]) for c in self.calls()], [("2", None)])

    def test_removing_the_only_image_sends_the_slot_and_leaves_the_section_in_place(self):
        self.mount(body_of(1, alts=(0,)))
        self.val("document.querySelector('.gal-bin').click()")
        self.until("G.server.calls.length >= 1", "sent")
        self.assertEqual([(c["slot"], c["image"]) for c in self.calls()], [("1", None)])
        self.assertNotIn("pictures", self.body())


class Kept(Base):
    def test_an_empty_gallery_keeps_the_edit_part_it_had_in_the_classic_look(self):
        self.mount(None)
        self.assertEqual(self.val("document.querySelectorAll('.gal-classic, .fi-bar').length"), 0)
        self.assertGreater(self.val("document.querySelectorAll('.tpl-gal-one').length"), 0)


class Cards(Base):
    classic = False

    def test_the_cards_look_keeps_the_old_edit_part(self):
        self.mount(body_of(2, alts=(0, 1)))
        self.assertEqual(self.val("document.querySelectorAll('.gal-classic, .gal-tile, .fi-bar').length"), 0)
        self.assertGreater(self.val("document.querySelectorAll('.tpl-gal-one').length"), 0)


class Sources(unittest.TestCase):
    def test_the_words_and_limits_the_page_shows_are_the_servers(self):
        from clark import server
        from clark.section_kinds import gallery
        js = (PAGE / "src" / "logic" / "galleryEditWords.js").read_text(encoding="utf-8")
        num = lambda name: eval(re.search(rf"export const {name} = ([^;]+);", js).group(1).split("//")[0].strip())
        self.assertEqual(num("PRINT_WIDE"), gallery.WIDTH_MAX)
        self.assertEqual(num("FILE_MB") * 1024 * 1024, gallery.PICTURE_MAX)
        self.assertEqual(num("FILE_MB"), server.IMAGE_FILE_MB)
        self.assertEqual(num("MOST_BYTES"), gallery.ORIGINAL_MAX)
        self.assertEqual(num("MOST"), len(gallery.SLOTS))
        self.assertEqual(re.search(r"export const SHAPES = (\[[^\]]*\])", js).group(1).replace('"', "'"), str(list(gallery.SHAPES)))
        self.assertEqual(re.search(r"export const COLUMNS = (\[[^\]]*\])", js).group(1), str(list(gallery.COLUMNS)))
        self.assertNotIn("300 dpi", js)
        self.assertNotIn("for print", js)

    def test_the_gallery_rules_are_in_the_second_rules_file_and_the_first_stays_under_its_size_pin(self):
        css = (THEME / "rules-2.css").read_text(encoding="utf-8")
        self.assertIn("/* Row 1233 (gal 2", css)
        self.assertNotIn(".gal-classic", (THEME / "rules.css").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
