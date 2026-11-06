"""#96 Text and image (store type 'textimage'), and R1, the picture route every picture template uses.

- The shared picture rules (section_kinds/textimage.py picture): PNG, JPEG and WebP data only, strict base64, the first bytes of
  the type named, the size, and no camera details (a JPEG with Exif or XMP, a WebP with EXIF or XMP, a PNG with eXIf).
- The template's checker and what it publishes (empty stays out; a caption only with its picture).
- R1: POST /api/section-image sets one slot as one step with one Undo; its own body limit; the words saved through /api/change keep
  the stored pictures and may not carry one; every refusal writes nothing.
- The published file and the served View: a hidden or empty section is in neither; the page's view parts pick what publish picks.
- In the page: View draws the words and the picture; Edit fills them in place (one change each), shrinks a picture on a canvas,
  and shows the running total of the pictures; at 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_tpl_textimage
Needs Chrome (the #33 harness) for the page tests: they fail, never skip, without it. Fictional data only.
"""
import base64
import json
import sqlite3
import struct
import unittest

from _demo import USER
from _pictures import BAD, CAMERA, EXIF, GOOD, GOOD_JPEG, GOOD_WEBP, PictureSteps, check, data, jpeg, published
from _pictures_page import BarePage
from clark import changes, publish, server as sv
from clark import store as store_module
from clark.section_kinds import base, textimage
from test_changes import Api
from test_report_editor import Base as PageBase
from test_server import Running, chrome, wait

KIND = "textimage"
WORDS = ["Fictional site visit on Tuesday.", "The new hall is ready for the pilot."]


def refused(test, kind, value, words=None):
    with test.assertRaises(store_module.Invalid) as e:
        check(kind, value)
    if words:
        test.assertEqual(str(e.exception), words)
    return str(e.exception)


class PictureRules(unittest.TestCase):
    def test_png_jpeg_and_webp_are_taken_as_they_are(self):
        for good in (GOOD, GOOD_JPEG, GOOD_WEBP):
            self.assertEqual(textimage.picture(good), good)

    def test_anything_else_is_refused_in_plain_words_that_never_quote_it(self):
        for bad in BAD:
            with self.subTest(bad=str(bad)[:60]):
                with self.assertRaises(base.Bad) as e:
                    textimage.picture(bad)
                self.assertEqual(str(e.exception), textimage.NOT_A_PICTURE)

    def test_camera_details_are_refused(self):
        for bad in CAMERA:
            with self.assertRaises(base.Bad) as e:
                textimage.picture(bad)
            self.assertEqual(str(e.exception), textimage.CAMERA_DETAILS)
        self.assertEqual(textimage.picture(data(jpeg(pad=100), "jpeg")), data(jpeg(pad=100), "jpeg"), "an APP1 after the picture data is not read")

    def test_size_is_checked_before_and_after_decoding(self):
        big = data(jpeg(pad=4000), "jpeg")
        with self.assertRaises(base.Bad) as e:
            textimage.picture(big, most=2000)
        self.assertEqual(str(e.exception), textimage.BIG_PICTURE)
        self.assertEqual(textimage.picture(big, most=10000), big)
        with self.assertRaises(base.Bad):
            textimage.picture("data:image/png;base64," + "A" * (textimage.PICTURE_MAX * 2))

    def test_the_store_meets_every_body_with_the_picture_rules(self):
        """The checker runs on every write (an Undo too) and at publish: a bad picture in a body never checks."""
        refused(self, KIND, {"v": 1, "pictures": {"image": EXIF}}, textimage.CAMERA_DETAILS)
        refused(self, KIND, {"v": 1, "pictures": {"other": GOOD}}, textimage.BAD_SLOT)
        refused(self, KIND, {"v": 1, "pictures": {"image": "https://example.org/a.png"}}, textimage.NOT_A_PICTURE)
        refused(self, KIND, {"v": 1, "pictures": ["x"]}, textimage.NOT_CONTENT)


class Checker(unittest.TestCase):
    def test_a_body_is_rebuilt_field_by_field_and_stored_one_way(self):
        got = check(KIND, {"v": 1, "words": ["  " + WORDS[0] + " ", "", WORDS[1]], "caption": " Fictional hall ", "alt": "",
                           "side": "right", "pictures": {"image": GOOD}})
        self.assertEqual(got, {"v": 1, "words": WORDS, "caption": "Fictional hall", "pictures": {"image": GOOD}})
        self.assertEqual(check(KIND, {"v": 1, "side": "left"}), {"v": 1, "side": "left"})

    def test_hostile_and_outsized_content_is_refused(self):
        self.assertEqual(refused(self, KIND, {"v": 1, "words": ["a"], "script": "x"}), textimage.UNKNOWN_FIELD)
        self.assertEqual(refused(self, KIND, {"v": 2}), textimage.OLD_VERSION)
        self.assertEqual(refused(self, KIND, {"v": "1"}), textimage.NOT_CONTENT)
        self.assertEqual(refused(self, KIND, ["not", "an", "object"]), textimage.NOT_CONTENT)
        self.assertEqual(refused(self, KIND, {"v": 1, "words": "one string"}), textimage.NOT_CONTENT)
        self.assertEqual(refused(self, KIND, {"v": 1, "words": [5]}), textimage.NOT_A_LINE)
        self.assertEqual(refused(self, KIND, {"v": 1, "words": ["x" * 2001]}), textimage.LONG_PARAGRAPH)
        self.assertEqual(refused(self, KIND, {"v": 1, "words": ["x"] * 21}), textimage.TOO_MANY_WORDS)
        self.assertEqual(refused(self, KIND, {"v": 1, "caption": "x" * 301}), textimage.LONG_LINE)
        self.assertEqual(refused(self, KIND, {"v": 1, "side": "middle"}), textimage.BAD_SIDE)
        self.assertNotIn("<script>", refused(self, KIND, {"v": 1, "caption": "<script>\n</script>"}), "a refusal never quotes")
        self.assertTrue(textimage.TEXT_LIMIT + 8 * 1024 <= sv.ROUTE_BODY_LIMITS["/api/section-body"], "the words fit the section-body route")
        self.assertGreater(textimage.LIMIT, (textimage.PICTURE_MAX + 2) // 3 * 4 + textimage.TEXT_LIMIT, "a picture and its words fit")

    def test_published_picks_the_words_and_the_picture_and_leaves_an_empty_one_out(self):
        self.assertIsNone(published(KIND, {"v": 1}))
        self.assertIsNone(published(KIND, {"v": 1, "caption": "Fictional", "alt": "Fictional", "side": "left"}),
                          "a caption alone is not shown")
        self.assertEqual(published(KIND, {"v": 1, "words": WORDS, "caption": "Not without a picture"}),
                         {"content": {"words": WORDS, "side": "right"}})
        self.assertEqual(published(KIND, {"v": 1, "caption": "Fictional hall", "alt": "A hall", "side": "left", "pictures": {"image": GOOD}}),
                         {"content": {"words": [], "side": "left", "image": GOOD, "caption": "Fictional hall", "alt": "A hall"}})
        self.assertTrue(textimage.READY)


class Route(PictureSteps, Api):
    def snapshot(self):
        con = sqlite3.connect(str(self.path))
        try:
            return (con.execute("SELECT count(*) FROM applies").fetchone()[0],
                    con.execute("SELECT group_concat(id || type || body, '|') FROM report_sections").fetchone()[0])
        finally:
            con.close()

    def no_picture(self, request, words, status=400):
        before = self.snapshot()
        got = self.image(request)
        self.assertEqual((got[0], got[1]["ok"], got[1]["message"]), (status, False, words), str(request)[:200])
        self.assertEqual(self.snapshot(), before, "nothing was written")

    def test_a_picture_is_one_step_and_one_undo(self):
        ref = self.made(KIND)
        self.assertEqual(self.words(ref, {"v": 1, "words": WORDS})[0], 200)
        before, applies = self.body(ref), self.snapshot()[0]
        status, got = self.put(ref, "image", GOOD)
        self.assertEqual(status, 200, got)
        self.assertEqual(self.snapshot()[0], applies + 1, "one step")
        self.assertEqual(self.body(ref), {**before, "pictures": {"image": GOOD}})
        self.assertNotIn("body", json.dumps(got["sections"]), "the reply never carries a body")
        self.assertEqual(self.put(ref, "image", GOOD)[1]["apply_id"], None, "the same picture again changes nothing")
        status, undone = self.undone(got["apply_id"])
        self.assertEqual(status, 200, undone)
        self.assertEqual(self.body(ref), before, "Undo puts the words back without the picture")
        out = self.put(ref, "image", GOOD_JPEG)[1]["apply_id"]
        taken = self.put(ref, "image", None)[1]
        self.assertEqual(self.body(ref), before, "null takes the picture out")
        self.undone(taken["apply_id"])
        self.assertEqual(self.body(ref)["pictures"], {"image": GOOD_JPEG})
        self.assertIsNotNone(out)

    def test_words_keep_the_stored_picture_and_never_carry_one(self):
        ref = self.made(KIND)
        self.put(ref, "image", GOOD)
        status, got = self.words(ref, {"v": 1, "words": WORDS, "caption": "Fictional hall"})
        self.assertEqual(status, 200, got)
        self.assertEqual(self.body(ref), {"v": 1, "words": WORDS, "caption": "Fictional hall", "pictures": {"image": GOOD}})
        self.undone(got["apply_id"])
        self.assertEqual(self.body(ref), {"v": 1, "pictures": {"image": GOOD}}, "Undo of the words keeps the picture")
        self.assertEqual(self.words(ref, {"v": 1, "pictures": {"image": GOOD_JPEG}})[1]["message"], textimage.PICTURES_OWN_WAY)
        self.assertEqual(self.words(ref, {"v": 1, "pictures": {}})[1].get("message"), None, "an empty pictures field is no picture")
        self.assertEqual(self.body(ref)["pictures"], {"image": GOOD})
        padded = json.dumps({"v": 1, "words": WORDS}) + " " * textimage.TEXT_LIMIT      # over the words' limit, under the route's
        status, got = self.change(self.req(changes.UPDATE, id=ref, changes={"body": padded}, place="report"))
        self.assertEqual((status, got["message"]), (400, changes.WORDS_TOO_LONG))
        self.assertEqual(self.body(ref)["pictures"], {"image": GOOD})

    def test_refusals_write_nothing(self):
        ref = self.made(KIND)
        text = self.ok("new", values={"type": "text", "title": "Fictional notes"}, after=None)["ref"]
        callout = self.made("callout")
        base_req = {"project": "ABC", "section": ref, "slot": "image", "image": GOOD}
        self.no_picture({**base_req, "image": EXIF}, textimage.CAMERA_DETAILS)
        self.no_picture({**base_req, "image": BAD[3]}, textimage.NOT_A_PICTURE)
        self.no_picture({**base_req, "image": 5}, changes.PICTURE_NOT_TEXT)
        self.no_picture({**base_req, "slot": "other"}, textimage.BAD_SLOT)
        self.no_picture({**base_req, "slot": 1}, textimage.BAD_SLOT)
        self.no_picture({**base_req, "section": text}, changes.NO_PICTURE_HERE)
        self.no_picture({**base_req, "section": callout}, changes.NO_PICTURE_HERE)
        self.no_picture({**base_req, "section": "XYZ-S-001"}, changes.NOT_MINE)
        self.no_picture({**base_req, "section": ["x"]}, changes.NOT_MINE)
        self.no_picture({**base_req, "project": "abc"}, changes.BAD_PROJECT)
        self.no_picture({**base_req, "project": "ZZZ"}, changes.NO_PROJECT, 404)
        self.no_picture({**base_req, "place": "excel"}, changes.BAD_PLACE)
        self.no_picture({**base_req, "kind": "report_sections"}, "A picture request doesn't take 'kind'. Reload the page and try again.")
        self.no_picture(["not an object"], changes.NOT_JSON_OBJECT)


class Http(unittest.TestCase):
    """The route on the real server: the token, its own body limit, and 503 with no seam."""

    def setUp(self):
        from _demo import DemoStore
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = Running(change=changes.make_change(self.demo.store.path, [], USER))
        self.addCleanup(self.s.close)

    def post(self, path, body, **kw):
        status, _, raw = self.s.api("POST", path, json.dumps(body).encode(), **kw)
        return status, json.loads(raw or b"{}")

    def test_the_route_sets_a_picture_and_keeps_its_own_limit(self):
        status, got = self.post("/api/section-image", {"project": "ABC", "section": "ABC-S-001", "slot": "image", "image": GOOD})
        self.assertEqual((status, got.get("code")), (503, "saving_off"), "no seam: saving is off")
        self.s.httpd.section_image = changes.make_section_image(self.demo.store.path, [], USER)
        status, made = self.post("/api/change", {"project": "ABC", "kind": "report_sections", "op": "new",
                                                 "values": {"type": KIND, "title": "Fictional"}, "after": None})
        self.assertEqual(status, 200, made)
        status, got = self.post("/api/section-image", {"project": "ABC", "section": made["ref"], "slot": "image", "image": GOOD})
        self.assertEqual(status, 200, got)
        self.assertIsInstance(got["apply_id"], int)
        self.assertEqual(self.post("/api/section-image", {"project": "ABC"}, token="wrong")[0], 403)
        self.assertEqual(sv.ROUTE_BODY_LIMITS["/api/section-image"], 1536 * 1024)
        for route in ("/api/section-image", "/api/change"):
            over = {sv.TOKEN_HEADER: sv.TOKEN, "Content-Type": "application/json", "Content-Length": str(sv.ROUTE_BODY_LIMITS[route] + 1)}
            status, _, raw = self.s.ask("POST", route, over, b"{}")
            self.assertEqual((status, json.loads(raw)["code"]), (400, "too_large"), route)
        limit = sv.ROUTE_BODY_LIMITS["/api/section-image"]
        head = json.dumps({"project": "ABC", "section": made["ref"], "slot": "image", "image": "data:image/png;base64,"})[:-2]
        fits = (head + "A" * (limit - len(head) - 2) + '"}').encode()
        self.assertEqual(len(fits), limit)
        status, _, raw = self.s.api("POST", "/api/section-image", fits)
        self.assertEqual((status, json.loads(raw)["message"]), (400, textimage.BIG_PICTURE), "read, then refused by its own rules")
        self.assertLess(sv.ROUTE_BODY_LIMITS["/api/change"], (textimage.PICTURE_MAX + 2) // 3 * 4, "a full-size picture never fits the change route")
        self.assertIn("/api/section-image", sv.POST_ROUTES)


class InTheFile(PictureSteps, Api):
    def test_a_filled_section_publishes_its_words_and_picture_and_an_empty_or_hidden_one_is_left_out(self):
        full = self.made(KIND, "Fictional site visit")
        self.words(full, {"v": 1, "words": WORDS, "caption": "Fictional hall", "alt": "The new hall"})
        self.put(full, "image", GOOD)
        empty = self.made(KIND, "Fictional empty")
        self.words(empty, {"v": 1, "caption": "Fictional orphan caption"})
        hidden = self.made(KIND, "Fictional hidden")
        self.words(hidden, {"v": 1, "words": ["Fictional hidden words"]})
        self.put(hidden, "image", GOOD_WEBP)
        self.ok(changes.UPDATE, id=hidden, changes={"hidden": 1})
        sections, text = self.file()
        self.assertEqual(sections[full]["content"], {"words": WORDS, "side": "right", "image": GOOD, "caption": "Fictional hall", "alt": "The new hall"})
        self.assertNotIn("body", sections[full])
        self.assertNotIn(empty, sections)
        self.assertNotIn(hidden, sections)
        for marker in ("Fictional orphan caption", "Fictional hidden words", "Fictional hidden", GOOD_WEBP.split(",")[1]):
            self.assertNotIn(marker, text)
        self.assertIn(GOOD.split(",")[1], text)


class Parity(BarePage):
    def test_the_page_shows_what_publish_publishes(self):
        self.assertTrue(self.val("P.ready.textimage"))
        self.parity(KIND, [{"v": 1}, {"v": 1, "words": WORDS}, {"v": 1, "caption": "Fictional"},
                           {"v": 1, "words": WORDS, "caption": "Fictional", "alt": "A", "side": "left", "pictures": {"image": GOOD}},
                           {"v": 1, "pictures": {"image": GOOD_JPEG}}])

    def test_a_picture_is_made_smaller_and_loses_the_camera_details(self):
        """The canvas step: a large picture comes back no longer than 1600 px and within the size, as a PNG or a JPEG the server takes."""
        made = self.val("""(async () => {
          const c = document.createElement('canvas'); c.width = 3200; c.height = 1600;
          const g = c.getContext('2d');
          for (let i = 0; i < 4000; i++) { g.fillStyle = `rgb(${i % 255},${(i * 7) % 255},${(i * 13) % 255})`; g.fillRect((i * 37) % 3200, (i * 53) % 1600, 40, 40); }
          const blob = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.95));
          const r = await P.shrink(new File([blob], 'photo.jpg', { type: 'image/jpeg' }), { longest: 1600, most: 300 * 1024 });
          return { ok: r.ok, w: r.width, h: r.height, start: (r.data || '').slice(0, 23), bytes: P.dataBytes(r.data), data: r.data };
        })()""", wait_for_promise=True)
        self.assertTrue(made["ok"], made.get("message"))
        self.assertEqual((made["w"], made["h"]), (1600, 800))
        self.assertEqual(made["start"], "data:image/jpeg;base64,")
        self.assertLessEqual(made["bytes"], 300 * 1024)
        self.assertEqual(textimage.picture(made["data"]), made["data"], "the server takes what the page made")
        refused_kind = self.val("P.shrink(new File(['<svg/>'], 'a.svg', { type: 'image/svg+xml' }))", wait_for_promise=True)
        self.assertEqual(refused_kind, {"ok": False, "message": "That file isn't a picture that can go in the report. Choose a PNG, JPEG or WebP picture."})

    def test_the_running_total_counts_only_pictures_that_would_publish(self):
        sections = [{"type": KIND, "hidden": 0, "body": json.dumps({"v": 1, "pictures": {"image": GOOD}})},
                    {"type": "imagecap", "hidden": 1, "body": json.dumps({"v": 1, "pictures": {"image": GOOD_JPEG}})},
                    {"type": "text", "hidden": 0, "body": "<p>" + GOOD + "</p>"},
                    {"type": "gallery", "hidden": 0, "body": "not json"}]
        self.assertEqual(self.val(f"P.picturesTotal({json.dumps(sections)})"), len(GOOD))


class InThePage(PageBase):
    def setUp(self):
        super().setUp()
        self.s.httpd.section_image = changes.make_section_image(self.store.path, [], USER)

    def add(self, body=None, title="Fictional site visit", hidden=0):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": KIND, "title": title, "sort_order": 999, "hidden": hidden})
        if body is not None:
            with self.store.step("dashboard", USER) as st:
                st.update("report_sections", ref, {"body": json.dumps(body)})
        return ref

    def body(self, ref):
        row = next(r for r in self.store.read("report_sections", "ABC") if r["id"] == ref)
        return json.loads(row["body"]) if row["body"] else {}

    def applies(self):
        con = sqlite3.connect(str(self.store.path))
        try:
            return con.execute("SELECT count(*) FROM applies").fetchone()[0]
        finally:
            con.close()

    def test_view_draws_words_and_picture_and_leaves_empty_and_hidden_out(self):
        full = self.add({"v": 1, "words": WORDS, "caption": "Fictional hall", "alt": "The new hall", "pictures": {"image": GOOD}})
        empty = self.add({"v": 1, "caption": "Fictional orphan caption"}, "Fictional empty")
        hidden = self.add({"v": 1, "words": ["Fictional hidden words"]}, "Fictional hidden", hidden=1)
        with chrome() as cdp:
            p = self.visit(cdp)
            sel = f"[data-id={json.dumps(full)}]"
            p.until(f"!!document.querySelector('{sel} .tpl-ti img')", "the picture is drawn")
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} .tpl-words p')].map(e => e.textContent)"), WORDS)
            self.assertEqual(p.js(f"document.querySelector('{sel} figcaption').textContent"), "Fictional hall")
            self.assertEqual(p.js(f"document.querySelector('{sel} img').getAttribute('alt')"), "The new hall")
            self.assertEqual(p.js(f"document.querySelector('{sel} img').getAttribute('src')"), GOOD)
            for ref in (empty, hidden):
                self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(ref)}]')"))
            report = p.js("document.querySelector('#report').textContent")
            self.assertNotIn("Fictional orphan caption", report)
            self.assertNotIn("Fictional hidden words", report)
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
                    box = p.js(f"(function(){{var s=document.querySelector('{sel}'), r=s.getBoundingClientRect(), i=s.querySelector('img').getBoundingClientRect();"
                               "return {fits: s.scrollWidth <= s.clientWidth + 1, inside: i.right <= r.right + 1 && i.left >= r.left - 1,"
                               "fg: getComputedStyle(s.querySelector('.tpl-words p')).color, cap: getComputedStyle(s.querySelector('figcaption')).color};})()")
                    self.assertTrue(box["fits"] and box["inside"], (width, theme, box))
                    self.assertNotEqual(box["fg"], box["cap"], "the caption is quieter than the words")

    def test_edit_fills_words_in_place_one_step_each_and_adds_a_picture(self):
        ref = self.add()
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertFalse(p.js(f"!!document.querySelector('{sel}')"), "an empty template is not in View")
            p.edit()
            p.until(f"!!document.querySelector('{sel} .tpl-ti-edit')", "the Edit part")
            self.assertIn("stays out of the published page", p.js(f"document.querySelector('{sel} .tpl-hint').textContent"))
            start = self.applies()
            p.js(f"document.querySelector('{sel} textarea').focus()")
            p.type(WORDS[0] + "\n" + WORDS[1])
            p.js(f"document.querySelector('{sel} textarea').blur()")
            p.saved()
            self.assertEqual(self.body(ref), {"v": 1, "words": WORDS})
            self.assertEqual(self.applies(), start + 1, "one step")
            self.assertEqual(p.toast(), "Text saved.")
            p.clear_toast()
            cap = f"{sel} input[id$=-caption]"
            p.js(f"document.querySelector('{cap}').focus()")
            p.type("Fictional hall")
            p.key("Escape", code="Escape", vk=27)
            self.assertEqual(p.js(f"document.querySelector('{cap}').value"), "", "Esc puts the saved words back")
            self.assertEqual(self.applies(), start + 1, "Esc saves nothing")
            p.js(f"document.querySelector('{cap}').focus()")
            p.type("Fictional hall")
            p.key("Enter", code="Enter", vk=13)
            p.saved()
            self.assertEqual(self.body(ref)["caption"], "Fictional hall")
            p.clear_toast()
            # a picture, chosen as a file: drawn on a canvas, shrunk and sent on its own
            p.js(f"""(async () => {{
              const c = document.createElement('canvas'); c.width = 2400; c.height = 1200;
              const g = c.getContext('2d'); g.fillStyle = 'rgb(40,90,160)'; g.fillRect(0, 0, 2400, 1200);
              const blob = await new Promise(r => c.toBlob(r, 'image/png'));
              const dt = new DataTransfer(); dt.items.add(new File([blob], 'plan.png', {{ type: 'image/png' }}));
              const input = document.querySelector('{sel} input[type=file]'); input.files = dt.files;
              input.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }})()""")
            p.saved()
            self.assertEqual(p.toast(), "Picture added.")
            pic = self.body(ref)["pictures"]["image"]
            raw = base64.b64decode(pic.split(",", 1)[1])
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n", "a PNG stays a PNG while it fits")
            self.assertEqual(struct.unpack(">II", raw[16:24]), (1600, 800), "the longest side is 1600 px")
            self.assertEqual(self.body(ref)["words"], WORDS, "the picture kept the words")
            self.assertEqual(self.applies(), start + 3)
            p.until(f"!!document.querySelector('{sel} .tpl-pic-slot.has-pic img')", "the picture shows in Edit")
            self.assertIn("Pictures in this report: 0.", p.js(f"document.querySelector('{sel} .tpl-total').textContent"))
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
                    fits = p.js(f"(function(){{var s=document.querySelector('{sel}'), r=s.getBoundingClientRect();"
                                "return s.scrollWidth <= s.clientWidth + 1 && [...s.querySelectorAll('.tpl-edit textarea, .tpl-edit input:not([type=file]), .tpl-pic-slot, .tpl-edit button')]"
                                ".every(e => {var i=e.getBoundingClientRect(); return i.right <= r.right + 1 && i.left >= r.left - 1;});})()")
                    self.assertTrue(fits, f"Edit fits at {width} px, {theme}")
            p.js(f"document.querySelector('{sel} [data-act=pick]').focus()")
            self.assertNotEqual(p.js("getComputedStyle(document.activeElement).outlineStyle"), "none", "the focus ring shows")
            # one Undo takes the picture back out, and keeps the words
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"!document.querySelector('{sel} .tpl-pic-slot.has-pic')", "Undo took the picture out")
            self.assertEqual(self.body(ref), {"v": 1, "words": WORDS, "caption": "Fictional hall"})
            p.view()
            p.until(f"!!document.querySelector('{sel} .tpl-words')", "View draws the words")
            self.assertFalse(p.js(f"!!document.querySelector('{sel} img')"))
            self.assertFalse(p.js(f"!!document.querySelector('{sel} input, {sel} textarea, {sel} button')"), "View is read only")

    def test_the_published_page_draws_it_from_its_own_data(self):
        full = self.add({"v": 1, "words": WORDS, "caption": "Fictional hall", "alt": "The new hall", "pictures": {"image": GOOD}})
        built = publish.build(self.store, "ABC", now="2030-01-15")
        html = built["body"].decode("utf-8")
        self.assertNotIn("section-image", html)
        self.assertNotIn("tpl-pic-slot", html)
        server = Running(page_html=lambda: html)
        self.addCleanup(server.close)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{server.port}/"}, sid)
            sel = f"[data-id={json.dumps(full)}]"
            self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{sel} .tpl-ti img')", sid), 15), "the file draws the picture")
            self.assertEqual(cdp.js(f"[...document.querySelectorAll('{sel} .tpl-words p')].map(e => e.textContent)", sid), WORDS)
            self.assertEqual(cdp.js(f"document.querySelector('{sel} figcaption').textContent", sid), "Fictional hall")


if __name__ == "__main__":
    unittest.main()
