"""Row 1270 sweep killers: the places the full sweep found no test pinning (Edit select and version, card look details, the id button's attributes).

Run: python3 dev/run_tests.py test_raid_cards_sweep_1270
Fictional rows. Page checks at 1400 and 900 only.
"""
import json
import unittest

from _demo import USER
from _publish import PublishedFile
import test_glance_page as glance
from test_report_editor import Base as PageBase
import test_raid_cards_one_1270 as one
from test_server import chrome


class Kind(unittest.TestCase):
    def test_limit_is_close_to_eight_cards_and_the_choice_must_be_a_whole_number(self):
        self.assertLess(one.raid4.LIMIT, 8 * one.raid3.CARD_BYTES + 200, "the limit is eight cards, not more")
        for across in (3.0, 4.0):
            with self.assertRaises(one.base.Bad):
                one.raid4.check({**one.v2(4, 2), "across": across}, one.Rules())


class View(PublishedFile, glance.Setup):
    def put(self, rows, body_cards, kind="raid3", across=0):
        ids = []
        self.demo.plant_builtin_sections()      # the cards are drawn beside the built-in sections (row 1193)
        with self.store.step("dashboard", USER) as st:
            for table, fields in rows:
                ids.append(st.create(table, dict({"project": "ABC", "raised": "2026-10-01", "source": "demo"}, **fields)))
            ref = st.create("report_sections", {"project": "ABC", "type": kind, "title": "Fictional cards", "sort_order": 993})
            st.update("report_sections", ref, {"body": json.dumps(dict({"v": 2, "across": across} if across else {"v": 1}, cards=[dict(c, id=ids[i]) for i, c in enumerate(body_cards)]))})
        return ids

    def look(self, p):
        return p.js("""(() => [...document.querySelectorAll('.raid-card')].map(c => ({ label: (c.querySelector('.raid-label:not(.raid-what)') || {}).textContent || '', rating: !!c.querySelector('.raid-rating'),
            text: !!c.querySelector('.raid-text'), latest: c.querySelectorAll('.raid-latest').length, btn: (() => { const b = c.querySelector('.raid-id'); return b ? [b.getAttribute('aria-label'), b.hasAttribute('data-open')] : null; })() })))()""")

    def test_card_details(self):
        ids = self.put([("raid", {"type": "Risk", "description": "Tide table", "client_message": "Roof survey booked.", "latest_update": "Roof survey booked.  "}),
                        ("actions", {"description": "Book the crane", "owner": "Pat", "due_date": "2026-12-01", "client_message": "Words.", "latest_update": "Called them."}),
                        ("raid", {"type": "Issue", "description": "Crane down", "latest_update": ""})],
                       [{"source": "client"}, {"source": "client"}, {"source": "own"}])
        path = self.publish()
        with chrome() as cdp:
            for w in (1400, 900):
                cs = self.look(self.draw(cdp, path, width=w))
                self.assertEqual(len(cs), 3, w)
                self.assertEqual(cs[0]["latest"], 1)
                self.assertEqual([c["text"] for c in cs], [False] * 3, "slice A: client and own words are never drawn, only the latest update")
                self.assertEqual(cs[0]["label"], "Latest update")
                self.assertFalse(cs[1]["rating"], "an action has no rating element")
                self.assertEqual(cs[0]["btn"], ["Open " + ids[0] + " details", True], "the id button names its item and keeps the peek open")

    def test_card_colours_by_rating(self):
        ids = self.put([("raid", {"type": "Risk", "description": "Red one", "impact": "High", "likelihood": "High", "client_message": "Words.", "latest_update": "Called them.", "owner": "Pat"}),
                        ("raid", {"type": "Risk", "description": "Amber one", "impact": "Medium", "likelihood": "Medium"}),
                        ("raid", {"type": "Issue", "description": "Green one", "impact": "Low", "likelihood": "Low"}),
                        ("raid", {"type": "Risk", "description": "Plain one"}),
                        ("actions", {"description": "Book the crane", "owner": "Pat", "due_date": "2026-12-01"})],
                       [{"source": "client"}] * 5, kind="raid4", across=3)
        path = self.publish()
        want = [("Red", "--status-red-text", "--status-red-tint", "--status-red-text"), ("Amber", "--status-amber-text", "--status-amber-tint", "--status-amber-text"),
                ("Green", "--status-green-text", "--status-green-text".replace("text", "tint"), "--status-green-text"), ("Not rated", "--grey-700", "--grey-100", "--grey-700"),
                ("", "--brand-blue", "--brand-blue-tint", "--brand-blue-strong")]
        with chrome() as cdp:
            for w in (1400, 900):
                p = self.draw(cdp, path, width=w)
                got = p.js("""(() => { const probe = (prop, v) => { const e = document.createElement('i'); e.style[prop] = 'var(' + v + ')'; document.body.appendChild(e); const c = getComputedStyle(e)[prop]; e.remove(); return c; };
                    const sty = (el, k) => getComputedStyle(el)[k];
                    return { cards: [...document.querySelectorAll('.raid-card')].map(c => { const top = c.querySelector('.raid-top'), r = c.querySelector('.raid-rating'), lab = c.querySelector('.raid-label:not(.raid-what)'), lat = c.querySelector('.raid-latest'), m = c.querySelector('.raid-meta');
                        return { word: r ? r.textContent : '', edge: sty(c, 'borderTopColor'), band: sty(top, 'backgroundColor'), ink: sty(top, 'color'),
                          ratingW: r ? sty(r, 'fontWeight') : '', ratingGap: r ? Math.round(c.getBoundingClientRect().right - r.getBoundingClientRect().right) : -1,
                          labelW: lab ? sty(lab, 'fontWeight') : '', labelColour: lab ? sty(lab, 'color') : '', latestColour: lat ? sty(lat, 'color') : '',
                          metaTop: m ? sty(m, 'borderTopWidth') + ' ' + sty(m, 'borderTopColor') : '' }; }),
                      p: { edge: Object.fromEntries(['--status-red-text','--status-amber-text','--status-green-text','--grey-700','--brand-blue','--status-red-tint','--status-amber-tint','--status-green-tint','--grey-100','--brand-blue-tint','--brand-blue-strong','--text-muted','--text','--grey-200'].map(v => [v, probe('color', v)])),
                           medium: probe('fontWeight', '--weight-medium') } }; })()""")
                tok = got["p"]["edge"]
                self.assertEqual(len(got["cards"]), 5, w)
                for c, (word, edge, band, ink) in zip(got["cards"], want):
                    self.assertEqual(c["word"], word, w)
                    self.assertEqual((c["edge"], c["band"], c["ink"]), (tok[edge], tok[band], tok[ink]), f"{word or 'action'} at {w}")
                    self.assertEqual(c["metaTop"], "1px " + tok["--grey-200"], "the foot line")
                    if word:
                        self.assertEqual(c["ratingW"], got["p"]["medium"])
                        self.assertLessEqual(c["ratingGap"], 24, "the rating sits at the right end of the band")
                self.assertEqual(got["cards"][0]["labelW"], got["p"]["medium"], got["cards"][0])
                self.assertEqual(got["cards"][0]["labelColour"], tok["--text-muted"])
                self.assertEqual(got["cards"][0]["latestColour"], tok["--text"])


class Edit(PageBase):
    arr = one.Edit.arr
    set_select = one.Edit.set_select
    wait_for = one.Edit.wait_for
    stored = one.Edit.stored

    def make(self, body, n=9):
        self.demo.plant_builtin_sections()      # the cards are drawn beside the built-in sections (row 1193)
        with self.store.step("dashboard", USER) as st:
            made = [st.create("raid", {"project": "ABC", "type": "Risk", "description": f"Fictional risk {i}", "raised": "2026-10-01", "source": "demo"}) for i in range(n)]
            ref = st.create("report_sections", {"project": "ABC", "type": "raid4", "title": "Fictional cards", "sort_order": 999, "body": body(made)})
        return ref, made

    def across(self, p, q):
        return p.js(f"document.querySelector('{q} select[aria-label=\"Cards across\"]').value")

    def show_picker(self, cdp, sec):
        q = f"[data-id={json.dumps(sec)}]"
        cdp.FOCUS_EMULATION = False
        p = self.visit(cdp)
        p.edit()
        p.until(f"!!document.querySelector('{q} select[aria-label=\"Cards across\"]')", "the choice is there")
        return p, q

    def cards(self, made, n, source="client"):
        return [{"id": i, "source": source} for i in made[:n]]

    def test_the_select_reads_the_saved_choice(self):
        for body, want in ((lambda m: json.dumps({"v": 2, "across": 3, "cards": self.cards(m, 6)}), "3"),
                           (lambda m: json.dumps({"v": 2, "across": 4, "cards": self.cards(m, 6)}), "4"),
                           (lambda m: "", "4")):
            sec, made = self.make(body)
            with chrome() as cdp:
                p, q = self.show_picker(cdp, sec)
                self.assertEqual(self.across(p, q), want)
                self.assertIn("Cards across", p.js(f"document.querySelector('{q} .rce-across span').textContent"))
                self.assertEqual(p.js(f"document.querySelector('{q} .rce-across span').textContent"), "Cards across")

    def test_a_change_keeps_version_two_and_the_choice(self):
        sec, made = self.make(lambda m: json.dumps({"v": 2, "across": 4, "cards": self.cards(m, 6)}))
        with chrome() as cdp:
            p, q = self.show_picker(cdp, sec)
            self.set_select(p, f"{q} select[aria-label='Card 2 item']", made[6])
            self.assertTrue(self.wait_for(lambda: self.stored(sec)["cards"][1]["id"] == made[6]))
            got = self.stored(sec)
            self.assertEqual((got["v"], got["across"], len(got["cards"])), (2, 4, 6))
            self.set_select(p, f"{q} select[aria-label='Cards across']", "3")
            self.assertTrue(self.wait_for(lambda: self.stored(sec).get("across") == 3))
            self.assertEqual(len(self.stored(sec)["cards"]), 6, "all six cards kept")
            self.set_select(p, f"{q} select[aria-label='Cards across']", "4")
            self.assertTrue(self.wait_for(lambda: self.stored(sec).get("across") == 4))
            self.assertEqual(self.across(p, q), "4")

    def test_a_body_of_version_one_with_four_cards(self):
        sec, made = self.make(lambda m: json.dumps({"v": 1, "cards": self.cards(m, 4)}))
        with chrome() as cdp:
            p, q = self.show_picker(cdp, sec)
            self.set_select(p, f"{q} select[aria-label='Card 1 item']", made[6])
            self.assertTrue(self.wait_for(lambda: self.stored(sec)["cards"][0]["id"] == made[6]))
            self.assertEqual(self.stored(sec)["v"], 1, "four cards, changed: still version one")
            p.until(f"!!document.querySelector('{q} select[aria-label=\"Card 5 item\"]')", "slot 5")
            self.set_select(p, f"{q} select[aria-label='Card 5 item']", made[4])
            self.assertTrue(self.wait_for(lambda: len(self.stored(sec)["cards"]) == 5))
            got = self.stored(sec)
            self.assertEqual((got["v"], got["across"]), (2, 4), "a fifth card saves as version two, four across")

    def test_a_second_change_keeps_the_first(self):
        sec, made = self.make(lambda m: json.dumps({"v": 2, "across": 4, "cards": self.cards(m, 6)}))
        with chrome() as cdp:
            p, q = self.show_picker(cdp, sec)
            for n, k in ((2, 6), (3, 7)):
                self.set_select(p, f"{q} select[aria-label='Card {n} item']", made[k])
                self.assertTrue(self.wait_for(lambda: self.stored(sec)["cards"][n - 1]["id"] == made[k]))
            self.assertEqual([c["id"] for c in self.stored(sec)["cards"][1:3]], [made[6], made[7]])

    def test_a_card_whose_item_is_gone_says_so_and_a_present_one_says_nothing(self):
        sec, made = self.make(lambda m: json.dumps({"v": 2, "across": 4, "cards": [{"id": "ABC-099", "source": "client"}, {"id": m[1], "source": "client"}]}))
        with chrome() as cdp:
            p, q = self.show_picker(cdp, sec)
            p.until(f"document.querySelectorAll('{q} .rce-card').length >= 2", "the cards are there")
            self.assertEqual(p.js(f"[...document.querySelectorAll('{q} .rce-card')].slice(0, 2).map(c => (c.querySelector('.rce-note') || {{}}).textContent || '')"),
                             ["This item is not in the record any more. Choose another item or remove the card.", ""])

    def test_no_words_choice_is_offered_and_an_old_one_is_kept(self):
        old = lambda m: json.dumps({"v": 2, "across": 4, "cards": [{"id": m[0], "source": "own", "own": "Old own words"}, {"id": m[1], "source": "client"}]})
        sec, made = self.make(old)
        with chrome() as cdp:
            p, q = self.show_picker(cdp, sec)
            self.assertEqual(p.js(f"document.querySelectorAll('{q} select[aria-label$=\" text\"], {q} .rce-own').length"), 0, "no text choice and no own words field")
            self.set_select(p, f"{q} select[aria-label='Cards across']", "3")
            self.assertTrue(self.wait_for(lambda: self.stored(sec).get("across") == 3))
            self.assertEqual(self.stored(sec)["cards"][0], {"id": made[0], "source": "own", "own": "Old own words"}, "an old saved choice is kept as it was")
            self.set_select(p, f"{q} select[aria-label='Card 1 item']", made[5])
            self.assertTrue(self.wait_for(lambda: self.stored(sec)["cards"][0]["id"] == made[5]))
            self.assertEqual(self.stored(sec)["cards"][0], {"id": made[5], "source": "own", "own": "Old own words"}, "another item on the card keeps the old saved choice")


if __name__ == "__main__":
    unittest.main()
