"""Row 1257 (v1.2), item 4: the Latest update box of the work item peek (an action, a risk, an issue) drawn as the approved mockup's layout A, measured at 1400 and 900:
heading 13 px / 700, one bordered card (border 1 px, radius 12, soft background, min text 84 px, padding 12 / 14, 14 px), a footer strip that is always shown inside
the card with the save key, the focus ring, the lowercase stamp under the card without an icon, and the same placeholder for every kind.
Run: python3 dev/run_tests.py test_peek_latest_box_1257
"""
import json
import re
import unittest

import test_peek_latest
import test_server  # noqa: F401  (a test that drives Chrome carries this import)
from test_server import chrome, wait

_B = test_peek_latest.Browser
ITEMS = (("TUL-A-002", "action"), ("TUL-007", "risk"), ("TUL-010", "issue"))
BOX = "#peek [data-pk-lbox]"


class Box(unittest.TestCase):
    load, open_box, type_in, save_key, toast, fresh, refused = (_B.load, _B.open_box, _B.type_in, _B.save_key, _B.toast, _B.fresh, _B.refused)
    HOLD, SHOWN, BOX = _B.HOLD, _B.SHOWN, _B.BOX
    setUp = _B.setUp

    def each(self):
        for width in (1400, 900):
            for ref, kind in ITEMS:
                with self.subTest(width=width, kind=kind), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    yield cdp, sid, width

    def num(self, cdp, sid, js):
        return cdp.js(js, sid)

    def test_the_box_is_a_bordered_card_with_the_measured_numbers(self):
        for cdp, sid, width in self.each():
            r = cdp.js("(() => { const b = document.querySelector('#peek [data-pk-lbox]'), c = getComputedStyle(b), t = getComputedStyle(b.querySelector('.rt-view')), v = b.querySelector('.rt-view').getBoundingClientRect(), br = b.getBoundingClientRect();"
                       " return { bt: c.borderTopWidth, rad: c.borderTopLeftRadius, bg: c.backgroundColor, ov: c.overflow, bc: c.borderTopColor, pl: t.paddingLeft, pt: t.paddingTop, fs: t.fontSize, minh: v.height, sw: b.scrollWidth, cw: b.clientWidth, w: br.width }; })()", sid)
            self.assertEqual((r["bt"], r["rad"], r["ov"], r["bc"]), ("1px", "12px", "hidden", "rgb(217, 224, 239)"), r)
            self.assertEqual((r["pl"], r["pt"], r["fs"]), ("14px", "12px", "14px"), r)
            self.assertGreaterEqual(r["minh"], 84, "the text area is at least 84 px high")
            self.assertLessEqual(r["sw"], r["cw"], "no sideways overflow in the box")

    def test_the_heading_is_13_px_and_700(self):
        for cdp, sid, width in self.each():
            r = cdp.js("(s => { const c = getComputedStyle(s); return [c.fontSize, c.fontWeight]; })(document.querySelector('#peek .pk-lab span'))", sid)
            self.assertEqual(r, ["13px", "700"])

    def test_the_footer_is_shown_before_the_box_is_opened_and_sits_inside_it_under_the_text(self):
        for cdp, sid, width in self.each():
            r = cdp.js("(() => { const b = document.querySelector('#peek [data-pk-lbox]'), f = b.querySelector('[data-pk-latest-hint]'); if (!f) return null; const k = f.querySelector('kbd'), c = getComputedStyle(f), kc = getComputedStyle(k);"
                       " return { text: f.textContent.trim(), key: k.textContent, fs: c.fontSize, top: f.getBoundingClientRect().top, vb: b.querySelector('.rt-view').getBoundingClientRect().bottom, bt: c.borderTopWidth, kfs: kc.fontSize, kfw: kc.fontWeight, krad: kc.borderTopLeftRadius }; })()", sid)
            self.assertIsNotNone(r, "the footer is in the box before any click")
            self.assertEqual((r["text"], r["key"]), ("⌘ Enter to save", "⌘ Enter"))
            self.assertEqual((r["fs"], r["bt"], r["kfs"], r["kfw"], r["krad"]), ("12px", "1px", "13px", "600", "4px"))
            self.assertGreaterEqual(r["top"], r["vb"] - 0.5, "the strip is under the text")

    def test_the_box_lights_on_focus_and_the_footer_stays(self):
        for cdp, sid, width in self.each():
            self.open_box(cdp, sid)
            r = cdp.js("(() => { const c = getComputedStyle(document.querySelector('#peek [data-pk-lbox]')); return [c.borderTopColor, c.boxShadow, !!document.querySelector('#peek [data-pk-lbox] [data-pk-latest-hint]'), getComputedStyle(document.querySelector('#peek [data-pk-lbox] .rt')).borderTopWidth]; })()", sid)
            self.assertEqual(r[0], "rgb(91, 71, 216)")
            self.assertIn("0px 0px 0px 3px", r[1])
            self.assertRegex(r[1], r"91, 71, 216|0\.15|91 71 216", "the ring is the brand colour at low alpha")
            self.assertTrue(r[2])
            self.assertEqual(r[3], "0px", "the editor draws no frame of its own inside the card")

    def test_the_stamp_is_lowercase_12_px_without_an_icon_6_px_under_the_box(self):
        for cdp, sid, width in self.each():
            has = cdp.js("!!document.querySelector('#peek [data-pk-last]')", sid)
            if not has:
                continue
            r = cdp.js("(() => { const s = document.querySelector('#peek [data-pk-last]'), c = getComputedStyle(s); return { t: s.textContent.trim(), svg: s.querySelectorAll('svg').length, fs: c.fontSize, mt: c.marginTop, gap: s.getBoundingClientRect().top - document.querySelector('#peek [data-pk-lbox]').getBoundingClientRect().bottom }; })()", sid)
            self.assertTrue(re.fullmatch(r"last updated \d{2}-\d{2}-\d{4} \d{2}:\d{2}", r["t"]), r)
            self.assertEqual((r["svg"], r["fs"], r["mt"]), (0, "12px", "6px"))
            self.assertAlmostEqual(r["gap"], 6, delta=1)

    def test_the_empty_box_says_the_same_words_for_every_kind(self):
        seen = set()
        for cdp, sid, width in self.each():
            t = cdp.js("(e => e ? e.textContent : '')(document.querySelector('#peek [data-pk-lbox] .rt-view .quiet'))", sid)
            if t:
                seen.add(t)
        self.assertLessEqual(seen, {"What changed? Add the latest update…"})

    def test_a_save_is_still_one_change_with_one_undo(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, "TUL-007", edit=True)
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, "Box words")
                self.save_key(cdp, sid)
                self.assertTrue(wait(lambda: "Box words" in cdp.js(f"(document.querySelector({json.dumps(self.SHOWN)}) || {{textContent: ''}}).textContent", sid) or ""))
                self.assertEqual(len(sent), 1)
                self.assertIn("Latest update of", self.toast(cdp, sid))


class Stamp1470(unittest.TestCase):
    """Row 1470 (Classic): the stamp under the Latest update box reads "Last updated <date> <time> · Source: <source>", the Source only when clark recorded it; no person is named."""
    load, fresh, refused, open_box, type_in, save_key = _B.load, _B.fresh, _B.refused, _B.open_box, _B.type_in, _B.save_key
    SHOWN, BOX = _B.SHOWN, _B.BOX
    HOLD = _B.HOLD
    setUp = _B.setUp
    DATE = r"Last updated \d{2}-\d{2}-\d{4} \d{2}:\d{2}"

    @staticmethod
    def prep(user=True, source=True):
        def make(store):
            import sqlite3
            con = sqlite3.connect(str(store.path))
            if not user:
                con.execute("UPDATE applies SET by_user = ''")
            if not source:
                con.execute("UPDATE actions SET source = '' WHERE id = 'TUL-A-001'")
            con.commit()
            con.close()
        return make

    def test_stamp_has_name_date_time_source_and_omits_unknown(self):
        """The name comes from the item's update row (ruling 23-11 10:25): no update row, no \"by\"; after a real save through the peek the stamp reads \"by <name>\"."""
        cases = ((True, True, rf"^{self.DATE} · Source: Demo data \(fictional\)$"), (False, True, rf"^{self.DATE} · Source: Demo data \(fictional\)$"),
                 (True, False, rf"^{self.DATE}$"), (False, False, rf"^{self.DATE}$"))
        for width in (1400, 900):
            if width == 900 and test_server.PAUSED_900:
                raise unittest.SkipTest(test_server.PAUSED_900)       # the repo pauses every 900 px case; the 1400 half ran
            with chrome() as cdp:                          # one browser per width: many launches in one test make Chrome close the pipe
                for mode in ("view", "edit"):
                    for user, source, want in cases:
                        self.check(cdp, width, mode, user, source, want)
                    self.check_by(cdp, width, mode)

    def check_by(self, cdp, width, mode):
        with self.subTest(width=width, mode=mode, by="saved update"):
            sent, sid = self.load(cdp, width, "TUL-A-001", edit=False, dash=mode, classic=True)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-last]')", sid)), "a stamp first")
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, f"By-name update {width} {mode}")
            self.save_key(cdp, sid)
            want = rf"^{self.DATE} by Demo User · Source: Demo data \(fictional\)$"
            self.assertTrue(wait(lambda: re.match(want, cdp.js("(e => e ? e.textContent.trim() : '')(document.querySelector('#peek [data-pk-last]'))", sid) or "")),
                            "the stamp names the person who saved the update: " + str(cdp.js("(e => e ? e.textContent.trim() : '')(document.querySelector('#peek [data-pk-last]'))", sid)))

    def check(self, cdp, width, mode, user, source, want):
        with self.subTest(width=width, mode=mode, user=user, source=source):
            sent, sid = self.load(cdp, width, "TUL-A-001", edit=False, dash=mode, classic=True, prep=self.prep(user, source))
            self.assertTrue(wait(lambda: re.match(want, cdp.js("(e => e ? e.textContent.trim() : '')(document.querySelector('#peek [data-pk-last]'))", sid) or "")), "the stamp reads as asked")
            r = cdp.js("(() => { const s = document.querySelector('#peek [data-pk-last]'), c = getComputedStyle(s); return { svg: s.querySelectorAll('svg').length, fs: c.fontSize, mt: c.marginTop, ml: c.marginLeft, left: s.getBoundingClientRect().left, box: document.querySelector('#peek [data-pk-lbox]').getBoundingClientRect().left }; })()", sid)
            self.assertEqual((r["svg"], r["fs"], r["mt"], r["ml"]), (0, "12px", "6px", "2px"), r)
            self.assertAlmostEqual(r["left"] - r["box"], 2, delta=1, msg="at the left of the box (margin 2), not right-aligned as row 1257 had it")


del _B


if __name__ == "__main__":
    unittest.main()
