"""Row 1270: hostile input for the RAID cards card as Edit and View have it now (item pickers only, no own words, no client wording).

Run: python3 dev/run_tests.py test_raid_cards_hostile_1270
Checker level: the 400 and 401 limit, joined emoji, direction marks, next-line characters and markup in an OLD saved body's own words (older bodies
are still read and kept). Page level (Chrome, 1400 and 900, Classic and Cards): item text with markup, a 10,000 character description, a long unbroken
line, right-to-left words and emoji, a hidden or archived item, and old own words never drawn in View or Edit. Fictional data only.
"""
import json
import unittest

from _demo import USER
from _publish import PublishedFile
import test_glance_page as glance
import test_tpl_raid3 as three
from test_report_editor import Base as PageBase
from test_server import chrome, wait
from clark.section_kinds import base

NEL, LS, PS = "\u0085", " ", " "
MARKUP = "<script>window.__r=1</script><img src=x onerror=\"window.__r=2\"> & <b>bold</b>"
RTL = "مرحبا שלום \U0001F468 \U0001F680"
UNBROKEN = "W" * 600
OWN = "OLDOWNWORDS"
OPEN = "(() => { const p = document.querySelector('#peek'); return !!p && !p.hidden && p.getBoundingClientRect().width > 0; })()"
NO_SIDEWAYS = "document.documentElement.scrollWidth <= window.innerWidth"


class Checker(unittest.TestCase):
    TYPE = "raid4"
    rules = three.CheckerBase.rules
    check = three.CheckerBase.check
    bad = three.CheckerBase.bad

    def own(self, text, v2=False):
        card = {"id": "ABC-001", "source": "own", "own": text}
        return json.dumps({"v": 2, "across": 4, "cards": [card]} if v2 else {"v": 1, "cards": [card]})

    def test_400_and_401_in_letters_and_in_emoji(self):
        for v2 in (False, True):
            for ch in ("x", "\U0001F680"):
                self.check(self.own(ch * 400, v2))
                self.bad(self.own(ch * 401, v2), "A card's own words can be 400 characters at most.")

    def test_joined_emoji_and_direction_marks_are_refused(self):
        for text in ("\U0001F468‍\U0001F469 ok", "abc‏def", "abc‮def", "a​b"):
            with self.subTest(text=text):
                self.bad(self.own(text))

    def test_next_line_and_separators_are_spaces_or_refused_never_kept(self):
        for text in ("one%stwo" % NEL, "a%sb%sc" % (LS, PS), "a\nb", "a\tb"):
            with self.subTest(text=repr(text)):
                try:
                    got = json.loads(self.check(self.own(text)))["cards"][0]["own"]
                except base.Bad:
                    continue
                for c in (NEL, LS, PS, "\n", "\t"):
                    self.assertNotIn(c, got)

    def test_markup_rtl_and_emoji_are_kept_as_text(self):
        for text in (MARKUP, RTL):
            self.assertEqual(json.loads(self.check(self.own(text)))["cards"][0]["own"], text)

    def test_only_spaces_is_no_words(self):
        self.assertEqual(json.loads(self.check(self.own("  　 ")))["cards"], [{"id": "ABC-001", "source": "own"}])


class View(PublishedFile, glance.Setup):
    def seed(self):
        self.demo.plant_builtin_sections()
        with self.store.step("dashboard", USER) as st:
            rows = [st.create("raid", {"project": "ABC", "type": "Risk", "description": MARKUP, "raised": "2026-10-01", "source": "demo", "latest_update": MARKUP}),
                    st.create("raid", {"project": "ABC", "type": "Risk", "description": RTL, "raised": "2026-10-01", "source": "demo", "latest_update": RTL}),
                    st.create("raid", {"project": "ABC", "type": "Issue", "description": "D" * 10000, "raised": "2026-10-01", "source": "demo", "latest_update": "L" * 10000}),
                    st.create("raid", {"project": "ABC", "type": "Issue", "description": UNBROKEN, "raised": "2026-10-01", "source": "demo", "latest_update": UNBROKEN}),
                    st.create("raid", {"project": "ABC", "type": "Risk", "description": "Plain one", "raised": "2026-10-01", "source": "demo", "client_message": "CLIENTWORDS"})]
            hidden = st.create("raid", {"project": "ABC", "type": "Risk", "description": "HIDDENITEM", "raised": "2026-10-01", "source": "demo"})
            st.create("report_hidden", {"project": "ABC", "item_id": hidden})
            cards = [{"id": r, "source": s} for r, s in zip(rows + [hidden], ("client", "client", "client", "client", "own", "client"))]
            cards[4]["own"] = OWN
            ref = st.create("report_sections", {"project": "ABC", "type": "raid4", "title": "Fictional cards", "sort_order": 993})
            st.update("report_sections", ref, {"body": json.dumps({"v": 2, "across": 3, "cards": cards})})
        return rows

    def check_page(self, cdp, path, w, rows, shown=5):
        p = self.draw(cdp, path, width=w)
        self.assertEqual(p.js(NO_SIDEWAYS), True, "no sideways scroll at %d" % w)
        self.assertEqual(p.js("!!window.__r || document.querySelectorAll('.raid-card script, .raid-card img, .raid-card b').length"), 0, "markup is not run")
        titles = p.js("[...document.querySelectorAll('.raid-card .raid-title')].map(e => e.textContent)")
        self.assertIn(MARKUP, titles)
        self.assertIn(RTL, titles)
        self.assertIn("D" * 10000, titles)
        self.assertEqual(p.js("[...document.querySelectorAll('.raid-card')].filter(c => c.scrollWidth > c.clientWidth + 1).length"), 0, "no card is wider than itself")
        body = p.js("document.querySelector('.raid-cards').textContent")
        self.assertNotIn(OWN, body, "old own words are not drawn")
        self.assertNotIn("CLIENTWORDS", body, "client wording is not drawn")
        self.assertNotIn("HIDDENITEM", p.js("document.body.textContent"), "an item hidden from the client is not published")
        self.assertEqual(p.js("document.querySelectorAll('.raid-card').length"), shown, "Classic draws every published card (up to 8), Cards is frozen at the old four")

    def test_hostile_item_text_in_classic_and_cards(self):
        rows = self.seed()
        path = self.publish()
        with chrome() as cdp:
            for w in (1400, 900):
                self.check_page(cdp, path, w, rows)
        raw = path.read_bytes()      # a published file is always Classic: take the Theme mark off to draw it as Cards does
        path.write_bytes(raw.replace(b'id="theme"', b'data-was="theme"'))
        with chrome() as cdp:
            for w in (1400, 900):
                self.check_page(cdp, path, w, rows, shown=4)

    def test_the_peek_shows_item_text_as_text_and_holds_the_page(self):
        rows = self.seed()
        path = self.publish()
        with chrome() as cdp:
            for w in (1400, 900):
                p = self.draw(cdp, path, width=w)
                for rid, text in ((rows[0], MARKUP), (rows[3], UNBROKEN)):
                    p.js("document.querySelector('.raid-card[data-card=%s] .idl').click()" % json.dumps(rid))
                    self.assertTrue(wait(lambda: p.js(OPEN)))
                    self.assertIn(text[:20], p.js("document.querySelector('#peek').textContent"))
                    self.assertEqual(p.js("!!window.__r || document.querySelectorAll('#peek script, #peek img, #peek b').length"), 0)
                    self.assertEqual(p.js(NO_SIDEWAYS), True, "no sideways scroll with the peek open at %d" % w)
                    p.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                    self.assertTrue(wait(lambda: not p.js(OPEN)))


class Edit(PageBase):
    arr = three.PageSide.arr
    wait_for = three.PageSide.wait_for

    def seed(self):
        self.demo.plant_builtin_sections()
        with self.store.step("dashboard", USER) as st:
            rows = [st.create("raid", {"project": "ABC", "type": "Risk", "description": d, "raised": "2026-10-01", "source": "demo"})
                    for d in (MARKUP, RTL, "D" * 10000, UNBROKEN)]
            gone = st.create("raid", {"project": "ABC", "type": "Risk", "description": "ARCHIVEDITEM", "raised": "2026-10-01", "source": "demo"})
            st.archive("raid", gone)
            hid = st.create("raid", {"project": "ABC", "type": "Risk", "description": "HIDDENITEM", "raised": "2026-10-01", "source": "demo"})
            st.create("report_hidden", {"project": "ABC", "item_id": hid})
            body = {"v": 1, "cards": [{"id": rows[0], "source": "client"}, {"id": rows[2], "source": "own", "own": OWN}, {"id": rows[3], "source": "client"}]}
            ref = st.create("report_sections", {"project": "ABC", "type": "raid4", "title": "Fictional cards", "sort_order": 999, "body": json.dumps(body)})
        return ref, rows, gone, hid

    def test_edit_holds_hostile_item_text_and_never_draws_old_own_words(self):
        sec, rows, gone, hid = self.seed()
        q = f"[data-id={json.dumps(sec)}]"
        for w in (1400, 900):
            with chrome() as cdp:
                cdp.FOCUS_EMULATION = False
                p = self.visit(cdp)
                p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.edit()
                p.until(f"!!document.querySelector('{q} select[aria-label=\"Card 1 item\"]')", "the picker is there")
                self.assertEqual(p.js(NO_SIDEWAYS), True, "no sideways scroll in Edit at %d" % w)
                self.assertEqual(p.js(f"!!window.__r || document.querySelectorAll('{q} script, {q} img, {q} b').length"), 0, "markup is not run")
                text = p.js(f"document.querySelector('{q}').textContent")
                self.assertNotIn(OWN, text, "old own words are not drawn in Edit")
                self.assertEqual(p.js(f"document.querySelectorAll('{q} .rce-f .ProseMirror, {q} textarea, {q} input[type=text]').length"), 0, "no own words field")
                what = self.arr(p, f"[...document.querySelectorAll('{q} .rce-what')].map(e => e.textContent)")
                self.assertTrue(any("<script>" in x for x in what), "markup shown as text")
                self.assertTrue(all(len(x) < 200 for x in what), "a 10,000 character description is cut in the line under the card")
                opts = self.arr(p, f"[...document.querySelectorAll('{q} select[aria-label=\"Card 4 item\"] option')].map(o => o.value + '|' + o.textContent)")
                joined = "\n".join(opts)
                self.assertNotIn("ARCHIVEDITEM", joined, "an archived item is not offered")
                self.assertTrue(all(len(o) < 200 for o in opts), "long text is cut in the picker")
                self.assertIn(RTL, joined)
                self.assertTrue(any(hid in o for o in opts), "an item hidden from the client is listed in the picker (it cannot be picked, but it is shown)")
                for o in opts:
                    if hid in o:
                        self.assertIn("left out of the published page", o, "a hidden item is marked, not silently published")
                n = len([s for s in self.sent if s[0] == "change"])
                self.assertEqual(n, 0, "opening Edit saves nothing")


if __name__ == "__main__":
    unittest.main()
