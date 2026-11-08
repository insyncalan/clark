"""#96 G2, the RAID cards templates, three across (store type raid3; test_tpl_raid4.py runs the same for four across).

A card is a work item's id and where its words come from (Client wording, Own words, or an action's Latest update). The checker,
the published fields (a hidden, archived, not client visible, sensitive or hidden-section item never publishes; an empty template
stays out of the file), one change = one step = one Undo, and the page: View draws only what the file would, Edit saves each
choice as one change. Fictional data only.

Run: python3 dev/run_tests.py test_tpl_raid3
Needs Chrome for the page tests (they fail, never skip, without it).
"""
import json
import shutil
import subprocess
import unittest

from _demo import USER
from _paths import SRC
from clark import changes, publish, section_bodies, store as store_module
from clark.section_kinds import base, raid3, raid4
from test_changes import Api
from test_report_editor import Base as PageBase
from test_server import chrome

QUIET = "Not shown on this page yet."


def card(id, source="client", own=None):
    out = {"id": id, "source": source}
    if own is not None:
        out["own"] = own
    return out


def body(*cards):
    return json.dumps({"v": 1, "cards": list(cards)})


class Kind:
    """What differs between three and four across."""
    TYPE, SIZE, MODULE = "raid3", 3, raid3


class CheckerBase:
    def rules(self):
        return section_bodies.Rules(plain=store_module._plain_ok, visible=store_module._visible_ok)

    def check(self, text):
        return section_bodies.check(self.TYPE, text, self.rules())

    def bad(self, text, words=None):
        with self.assertRaises(base.Bad) as got:
            self.check(text)
        self.assertNotIn("ABC-", str(got.exception), "a refusal never quotes the value")
        if words:
            self.assertEqual(str(got.exception), words)
        return str(got.exception)

    def test_ready_and_registered(self):
        self.assertIs(self.MODULE.READY, True)
        self.assertIs(section_bodies.CHECKERS[self.TYPE], self.MODULE.check)
        self.assertEqual(section_bodies.EMPTY[self.TYPE], "")
        self.assertEqual(self.check(""), "", "no content is no content")

    def test_a_good_body_is_stored_in_one_canonical_text(self):
        cards = [card("ABC-001"), card("ABC-A-002", "latest"), card("ABC-D-003", "own", "  Two   words ")][: self.SIZE]
        text = self.check(body(*cards))
        self.assertEqual(self.check(text), text, "saving again changes nothing")
        got = json.loads(text)
        self.assertEqual(got["v"], 1)
        self.assertEqual([c["id"] for c in got["cards"]], [c["id"] for c in cards])
        self.assertEqual(got["cards"][-1].get("own"), "Two words" if len(cards) == 3 else None)
        self.assertEqual(json.loads(self.check(json.dumps({"v": 1, "cards": [{"id": "ABC-001"}]})))["cards"], [{"id": "ABC-001", "source": "client"}])
        self.assertEqual(json.loads(self.check(json.dumps({"v": 1, "cards": []}))), {"v": 1, "cards": []})

    def test_the_number_of_cards_is_the_templates(self):
        ids = [f"ABC-{n:03d}" for n in range(1, self.SIZE + 2)]
        self.check(body(*[card(i) for i in ids[: self.SIZE]]))
        self.bad(body(*[card(i) for i in ids]), f"A card row holds {self.SIZE} cards at most.")

    def test_hostile_content_is_refused_in_plain_words(self):
        shapes = ["[]", "{}", json.dumps({"v": 2, "cards": []}), json.dumps({"v": 1}), json.dumps({"v": 1, "cards": {}}),
                  json.dumps({"v": 1, "cards": [], "x": 1}), json.dumps({"v": 1, "cards": ["ABC-001"]}),
                  json.dumps({"v": 1, "cards": [{"id": "ABC-001", "x": "y"}]})]
        for s in shapes:
            with self.subTest(shape=s):
                self.bad(s)
        for bad_id in ("ABC-M-001", "ABC-U-001", "ABC-W-001", "abc-001", "ABC-1", "ABC-0001", "ABC-A-1", "AB-001", "ABC-001 ",
                       "ABC-A-001; DROP TABLE x", "<b>ABC-001</b>", "../ABC-001", "", None, 7, ["ABC-001"]):
            with self.subTest(id=bad_id):
                self.bad(body({"id": bad_id}), "A card needs the number of a risk, issue, action or decision.")
        self.bad(body(card("ABC-001"), card("ABC-001")), "The same item is on two cards.")
        self.bad(body(card("ABC-001", "latest")), "Only an action has a latest update. Choose Client wording or Own words for this card.")
        self.bad(body(card("ABC-D-001", "latest")))
        self.check(body(card("ABC-A-001", "latest")))
        self.bad(body(card("ABC-001", "other")), "Choose Client wording, Own words or Latest update for a card.")
        self.bad(body(card("ABC-001", "own", "x" * 401)), "A card's own words can be 400 characters at most.")
        self.check(body(card("ABC-001", "own", "x" * 400)))
        self.bad(body({"id": "ABC-001", "source": "own", "own": 7}))
        self.bad(body({"id": "ABC-001", "source": "own", "own": "a‮b"}))
        self.bad(body({"id": "ABC-001", "source": "own", "own": "a\nb"}))
        self.bad(body({"id": "ABC-001\n"}))
        self.bad(body({"id": "ABC-001", "source": "own", "own": "a​b"}))

    def test_markup_in_own_words_is_only_text(self):
        text = self.check(body(card("ABC-001", "own", "<script>alert(1)</script> & <b>bold</b>")))
        self.assertEqual(json.loads(text)["cards"][0]["own"], "<script>alert(1)</script> & <b>bold</b>")

    def test_a_body_over_the_limit_is_refused_before_it_is_read(self):
        self.bad(" " * (self.MODULE.LIMIT + 1), "That content is too long to save.")
        self.assertGreaterEqual(self.MODULE.LIMIT, 4 * (6 * raid3.OWN_MAX + 40), "the largest allowed body fits")
        biggest = body(*[card(f"ABC-{n:03d}", "own", "é" * 400) for n in range(1, self.SIZE + 1)])
        self.assertLessEqual(len(self.check(biggest)), self.MODULE.LIMIT)


class Items(Api):
    """The store with a risk, an issue, an action and a decision, and a card section of the type under test."""
    TYPE, SIZE = "raid3", 3

    def setUp(self):
        super().setUp()
        with self.s.step("dashboard", USER) as st:
            self.risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier may slip", "raised": "2026-10-01",
                                           "source": "demo", "client_message": "We are watching the supplier."})
            self.issue = st.create("raid", {"project": "ABC", "type": "Issue", "description": "Test rig down", "raised": "2026-10-01",
                                            "source": "demo", "client_message": "RIGWORDS"})
            self.action = st.create("actions", {"project": "ABC", "description": "Agree the plan", "raised": "2026-10-01", "source": "demo",
                                                "latest_update": "LATESTWORDS", "client_message": "Plan nearly agreed.", "due_date": "2030-02-01"})
            self.decision = st.create("decisions", {"project": "ABC", "decision": "Use the blue vendor",
                                                    "source": "demo", "client_message": "DECISIONWORDS", "status": "Pending",
                                                    "needed_by": "2030-02-05"})
        self.sec = self.ok("new", values={"type": self.TYPE, "title": "Fictional cards"}, after=None)["ref"]

    def save(self, *cards):
        status, got = self.change(self.req(changes.UPDATE, id=self.sec, changes={"body": body(*cards)}))
        self.assertEqual(status, 200, got)
        return got

    def built(self):
        return publish.build(self.s, "ABC", now="2030-01-15")

    def file_section(self):
        return next((s for s in self.built()["published"]["sections"] if s["id"] == self.sec), None)

    def test_one_save_is_one_step_and_one_undo(self):
        before = self.snapshot()
        got = self.save(card(self.risk), card(self.action, "latest"))
        self.assertEqual(self.snapshot()[0], before[0] + 1, "one step")
        stored = next(r for r in self.s.read("report_sections", "ABC") if r["id"] == self.sec)["body"]
        self.assertEqual([c["id"] for c in json.loads(stored)["cards"]], [self.risk, self.action])
        status, _ = self.undone(got["apply_id"])
        self.assertEqual(status, 200)
        self.assertEqual(next(r for r in self.s.read("report_sections", "ABC") if r["id"] == self.sec)["body"], "")

    def test_the_change_route_refuses_a_bad_card_and_writes_nothing(self):
        before = self.snapshot()
        for b in (body(card("ABC-M-001")), body(card(self.risk, "latest")), "not json", body(card(self.risk), card(self.risk))):
            status, got = self.change(self.req(changes.UPDATE, id=self.sec, changes={"body": b}))
            self.assertEqual((status, got["ok"]), (400, False), b)
            self.assertNotIn("ABC-", got["message"])
        self.assertEqual(self.snapshot(), before)

    def test_an_empty_template_stays_out_of_the_file(self):
        self.assertIsNone(self.file_section(), "no body")
        self.save()
        self.assertIsNone(self.file_section(), "no cards")
        self.save(card("ABC-099"))
        self.assertIsNone(self.file_section(), "a card whose item is not in the record")

    def test_the_file_carries_the_id_and_the_chosen_words_only(self):
        self.save(card(self.risk), card(self.action, "latest"), card(self.decision, "own", "Own decision words"))
        text = self.built()["body"].decode("utf-8")
        sec = self.file_section()
        self.assertEqual([c["id"] for c in sec["cards"]], [self.risk, self.action, self.decision][: self.SIZE])
        self.assertEqual(sec["cards"][0]["text"], "We are watching the supplier.")
        self.assertEqual(sec["cards"][1]["text"], "LATESTWORDS")
        self.assertEqual(set(sec["cards"][0]), {"id", "text"})
        self.assertIn("Supplier may slip", text, "the item itself is in the file's data, as before")
        if self.SIZE == 3:
            self.assertEqual(sec["cards"][2]["text"], "Own decision words")
            self.assertNotIn("DECISIONWORDS", json.dumps(sec["cards"]), "a card that says Own words never carries the item's client wording")
        self.assertNotIn("source", json.dumps(sec["cards"]))

    def test_a_client_card_with_no_wording_publishes_the_items_title_and_never_other_fields(self):
        """#916: Client wording falls back to the title (a decision's decision, else description), never latest_update, notes or owner."""
        with self.s.step("dashboard", USER) as st:
            st.update("actions", self.action, {"client_message": "", "latest_update": "LATESTWORDS", "owner": "Pat Owner"})
            st.update("raid", self.risk, {"client_message": ""})
            st.update("decisions", self.decision, {"client_message": ""})
        self.save(card(self.action), card(self.risk), card(self.decision))
        cards = self.file_section()["cards"]
        self.assertEqual([c["text"] for c in cards], ["Agree the plan", "Supplier may slip", "Use the blue vendor"][: self.SIZE])
        for marker in ("LATESTWORDS", "Pat Owner"):
            self.assertNotIn(marker, json.dumps(cards), marker)

    def test_a_risk_has_no_latest_update_so_client_wording_and_own_words_only(self):
        self.save(card(self.action, "client"))
        self.assertEqual(self.file_section()["cards"][0]["text"], "Plan nearly agreed.")
        self.assertEqual(set(self.file_section()["cards"][0]), {"id", "text"})

    def test_an_item_that_does_not_publish_never_publishes_through_a_card(self):
        """Hidden, archived, not client visible, sensitive: the card is left out (never shown blank) and no word of it is in the file."""
        with self.s.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": self.issue})
            st.update("actions", self.action, {"client_visible": 0})
            st.archive("decisions", self.decision)
        self.save(card(self.risk), card(self.issue, "own", "ISSUEOWN"), card(self.action, "own", "ACTIONOWN"))
        sec = self.file_section()
        self.assertEqual([c["id"] for c in sec["cards"]], [self.risk])
        text = self.built()["body"].decode("utf-8")
        for marker in ("ISSUEOWN", "ACTIONOWN", "RIGWORDS", "Test rig down", "LATESTWORDS", "DECISIONWORDS", "Use the blue vendor"):
            self.assertNotIn(marker, text, marker)

    def test_a_sensitive_item_is_left_out(self):
        with self.s.step("dashboard", USER) as st:
            st.create("item_labels", {"item_id": self.risk, "label": "Sensitive"})
        self.save(card(self.risk, "own", "SENSITIVEOWN"))
        self.assertIsNone(self.file_section(), "the only card is left out, so the section is")
        self.assertNotIn("SENSITIVEOWN", self.built()["body"].decode("utf-8"))

    def test_a_hidden_section_and_a_hidden_kind_publish_nothing(self):
        self.save(card(self.risk))
        self.assertIsNotNone(self.file_section())
        self.change(self.req(changes.UPDATE, id=self.sec, changes={"hidden": 1}))
        self.assertIsNone(self.file_section())
        self.change(self.req(changes.UPDATE, id=self.sec, changes={"hidden": 0}))
        raid_sections = [r["id"] for r in self.s.read("report_sections", "ABC") if r["type"] == "raid"]
        if raid_sections:
            self.change(self.req(changes.UPDATE, id=raid_sections[0], changes={"hidden": 1}))
            self.assertIsNone(self.file_section(), "hiding the risks section drops their rows, so the card has nothing to show")

    def test_a_card_never_changes_the_neighbours_row(self):
        text_ref = self.ok("new", values={"type": "text", "title": "Fictional notes"}, after=None)["ref"]
        pair = self.ok("new", values={"type": self.TYPE, "title": "Fictional pair"}, after=text_ref, beside=1)["ref"]
        sections = {s["id"]: s for s in self.built()["published"]["sections"]}
        self.assertNotIn(pair, sections, "an empty template is not in the file")
        if text_ref in sections:
            self.assertEqual(sections[text_ref]["beside"], 0)


class PageSide(PageBase):
    """The page clark serves: View shows what the file would; Edit saves each choice as one change."""
    TYPE, SIZE = "raid3", 3

    def seed(self):
        with self.store.step("dashboard", USER) as st:
            ids = {
                "risk": st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier may slip", "raised": "2026-10-01",
                                           "source": "demo", "client_message": "We are watching the supplier."}),
                "hidden": st.create("raid", {"project": "ABC", "type": "Issue", "description": "Hidden rig", "raised": "2026-10-01",
                                             "source": "demo", "client_message": "HIDDENWORDS", "client_visible": 0}),
                "action": st.create("actions", {"project": "ABC", "description": "Agree the plan", "raised": "2026-10-01", "source": "demo",
                                                "latest_update": "LATESTWORDS", "due_date": "2030-02-01"}),
                "decision": st.create("decisions", {"project": "ABC", "decision": "Use the blue vendor",
                                                    "source": "demo", "status": "Pending", "needed_by": "2030-02-05"}),
            }
            ref = st.create("report_sections", {"project": "ABC", "type": self.TYPE, "title": "Fictional cards", "sort_order": 999})
        ids["sec"] = ref
        return ids

    def fill(self, ids, *cards):
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", ids["sec"], {"body": body(*cards)})

    def card_ids(self, p, sec):
        return self.arr(p, f"[...document.querySelectorAll('[data-id={json.dumps(sec)}] .raid-card')].map(e => e.dataset.card)")

    def test_view_draws_only_the_cards_the_file_would(self):
        ids = self.seed()
        self.fill(ids, card(ids["risk"]), card(ids["hidden"], "own", "HIDDENOWN"), card(ids["action"], "latest"))
        with chrome() as cdp:
            p = self.visit(cdp)
            sec = ids["sec"]
            self.assertEqual(self.card_ids(p, sec), [ids["risk"], ids["action"]], "the item that is not client visible has no card")
            shown = p.js(f"document.querySelector('[data-id={json.dumps(sec)}]').textContent")
            self.assertIn("We are watching the supplier.", shown)
            self.assertIn("LATESTWORDS", shown)
            self.assertNotIn("HIDDENWORDS", shown)
            self.assertNotIn("HIDDENOWN", shown)
            self.assertEqual(p.js(f"document.querySelectorAll('[data-id={json.dumps(sec)}] .quiet').length"), 0)
            self.assertEqual(p.js(f"document.querySelectorAll('[data-id={json.dumps(sec)}] [contenteditable], [data-id={json.dumps(sec)}] select, [data-id={json.dumps(sec)}] input').length"), 0, "View is read-only")

    def test_view_leaves_an_empty_template_out(self):
        ids = self.seed()
        self.fill(ids, card(ids["hidden"]))
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(ids['sec'])}]')"))
            p.edit()
            p.until(f"!!document.querySelector('[data-id={json.dumps(ids['sec'])}] .rce')", "Edit shows the template to fill in")
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ids['sec'])}]').textContent.includes({json.dumps(QUIET)})"), False)

    def test_edit_saves_each_choice_as_one_change_with_one_undo(self):
        ids = self.seed()
        sec = ids["sec"]
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('[data-id={json.dumps(sec)}] .rce-first')", "the first-step line is shown")
            first = p.js(f"document.querySelector('[data-id={json.dumps(sec)}] .rce-first').textContent")
            self.assertIn("Choose an item", first)
            sel = f"[data-id={json.dumps(sec)}] select[aria-label='Card 1 item']"
            self.set_select(p, sel, ids["risk"])
            p.until(f"!!document.querySelector({json.dumps(f'[data-id={json.dumps(sec)}] select[aria-label=' + chr(34) + 'Card 2 item' + chr(34) + ']')})", "a second card row appears")
            self.assertEqual(len([s for s in self.sent if s[0] == "change"]), 1, "one choice, one request")
            stored = json.loads(next(r for r in self.store.read("report_sections", "ABC") if r["id"] == sec)["body"])
            self.assertEqual(stored["cards"], [{"id": ids["risk"], "source": "client"}])
            options = self.arr(p, "[...document.querySelectorAll(" + json.dumps(sel + " option") + ")].map(o => o.textContent)")
            self.assertTrue(any("left out of the published page" in o and "Hidden rig" in o for o in options), "an item that does not publish says so")
            self.assertEqual(len(options), len(set(options)))
            self.assertFalse(any(ids["risk"] in o for o in self.arr(p, f"[...document.querySelectorAll('[data-id={json.dumps(sec)}] select[aria-label=\"Card 2 item\"] option')].map(o => o.textContent)")), "an item is on one card only")
            self.set_select(p, f"[data-id={json.dumps(sec)}] select[aria-label='Card 2 item']", ids["action"])
            p.until(f"!!document.querySelector('[data-id={json.dumps(sec)}] select[aria-label=\"Card 2 text\"]')", "the text source of card 2")
            kinds = self.arr(p, f"[...document.querySelectorAll('[data-id={json.dumps(sec)}] select[aria-label=\"Card 2 text\"] option')].map(o => o.value)")
            self.assertEqual(kinds, ["client", "own", "latest"], "an action offers its latest update")
            kinds1 = self.arr(p, f"[...document.querySelectorAll('[data-id={json.dumps(sec)}] select[aria-label=\"Card 1 text\"] option')].map(o => o.value)")
            self.assertEqual(kinds1, ["client", "own"], "a risk has none")
            self.set_select(p, f"[data-id={json.dumps(sec)}] select[aria-label='Card 2 text']", "latest")
            self.assertTrue(self.wait_for(lambda: json.loads(next(r for r in self.store.read("report_sections", "ABC") if r["id"] == sec)["body"])["cards"][1]["source"] == "latest"))
            p.until(f"document.querySelector('[data-id={json.dumps(sec)}] select[aria-label=\"Card 2 text\"]').value === 'latest'", "the select shows latest")
            # That select shows what the test just set, so it proves nothing about the page. The page takes the saved body only after it has read the
            # project again, and says so with the toast ("Card text changed." is new here: the two earlier changes said "Card added."). The next
            # choice is built from the body the page holds, so it must not be made before then (the hosted Mac made it first and dropped the latest update).
            p.until("(document.querySelector('.toast-text') || {}).textContent === 'Card text changed.'", "the page has taken the saved text source of card 2 (toast)")
            n = len([s for s in self.sent if s[0] == "change"])
            self.set_select(p, f"[data-id={json.dumps(sec)}] select[aria-label='Card 1 text']", "own")
            p.until(f"!!document.querySelector('[data-id={json.dumps(sec)}] input[aria-label=\"Card 1 own words\"]')", "own words box")
            p.js(f"(function(){{ const i = document.querySelector('[data-id={json.dumps(sec)}] input[aria-label=\"Card 1 own words\"]'); i.focus(); i.value = 'Typed words'; i.dispatchEvent(new Event('input', {{bubbles: true}})); i.dispatchEvent(new Event('blur')); }})()")
            p.until(f"document.querySelector('[data-id={json.dumps(sec)}] input[aria-label=\"Card 1 own words\"]').value === 'Typed words'", "kept")
            self.assertTrue(self.wait_for(lambda: json.loads(next(r for r in self.store.read("report_sections", "ABC") if r["id"] == sec)["body"])["cards"][0].get("own") == "Typed words"))
            self.assertEqual(len([s for s in self.sent if s[0] == "change"]), n + 2, "the source and the words are one change each")
            final = json.loads(next(r for r in self.store.read("report_sections", "ABC") if r["id"] == sec)["body"])["cards"]
            self.assertEqual(final[1]["source"], "latest", "the words change did not undo the earlier choice of card 2")
            # View now draws the cards
            p.view()
            self.assertEqual(self.card_ids(p, sec), [ids["risk"], ids["action"]])
            p.until(f"document.querySelector('[data-id={json.dumps(sec)}]').textContent.includes('Typed words')", "View draws the words just typed")      # the page takes the saved section a moment after the field shows it; the hosted Mac drew View first
            self.assertIn("Typed words", p.js(f"document.querySelector('[data-id={json.dumps(sec)}]').textContent"))
            p.until(f"document.querySelector('[data-id={json.dumps(sec)}]').textContent.includes('LATESTWORDS')", "View draws the latest update of card 2")      # drawn with the words above, but a slow hosted Mac has drawn the card without it for a moment
            self.assertIn("LATESTWORDS", p.js(f"document.querySelector('[data-id={json.dumps(sec)}]').textContent"))
            self.assertEqual(self.sent[-1][1]["place"], "report")

    def test_removing_a_card_and_undo(self):
        ids = self.seed()
        sec = ids["sec"]
        self.fill(ids, card(ids["risk"]), card(ids["action"]))
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sel = f"[data-id={json.dumps(sec)}] select[aria-label='Card 1 item']"
            p.until(f"!!document.querySelector({json.dumps(sel)})", "card 1")
            self.set_select(p, sel, "")
            self.assertTrue(self.wait_for(lambda: [c["id"] for c in json.loads(next(r for r in self.store.read("report_sections", "ABC") if r["id"] == sec)["body"])["cards"]] == [ids["action"]]))
            p.saved()
            self.assertEqual(p.toast(), "Card removed.")
            self.assertEqual(len([s for s in self.sent if s[0] == "change"]), 1, "one removal, one request")
            p.js("document.querySelector('[data-undo]').click()")
            p.until("document.querySelector('.toast-text').textContent === 'Undone.'", "Undo")
            self.assertTrue(self.wait_for(lambda: [c["id"] for c in json.loads(next(r for r in self.store.read("report_sections", "ABC") if r["id"] == sec)["body"])["cards"]] == [ids["risk"], ids["action"]]),
                            "one Undo puts both cards back")

    def arr(self, p, expr):
        return json.loads(p.js(f"JSON.stringify({expr})"))

    def set_select(self, p, selector, value):
        p.until(f"!!document.querySelector({json.dumps(selector)})", f"{selector} is there")
        p.js(f"(function(){{ const s = document.querySelector({json.dumps(selector)}); s.value = {json.dumps(value)}; s.dispatchEvent(new Event('change', {{bubbles: true}})); }})()")

    def wait_for(self, fn, seconds=10):
        import time
        end = time.time() + seconds
        while time.time() < end:
            try:
                if fn():
                    return True
            except Exception:
                pass
            time.sleep(0.1)
        return False

    def test_the_published_page_has_no_edit_part_and_no_dangerous_markup(self):
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("rce-card", view)
        self.assertNotIn("Choose an item for the first card", view)
        self.assertIn("raid-card", view)
        for f in ("templates/RaidCards.jsx", "templates/Raid3.jsx", "templates/Raid4.jsx", "edit/templates/raidEdit.jsx"):
            self.assertNotIn("dangerouslySetInnerHTML=", (SRC / "clark" / "page" / "src" / f).read_text(encoding="utf-8"))


class PageWordsOf(unittest.TestCase):
    """#916: the page's wordsOf (templates/raid.js) chooses the same words as raid3._words, with no browser."""
    def words(self, card, row):
        if not shutil.which("node"):
            raise unittest.SkipTest("no node")
        url = (SRC / "clark" / "page" / "src" / "templates" / "raid.js").as_uri()
        code = f"const m = await import({json.dumps(url)}); console.log(JSON.stringify(m.wordsOf({json.dumps(card)}, {json.dumps(row)})));"
        done = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_client_wording_falls_back_to_the_title_only(self):
        row = {"description": "Agree the plan", "client_message": "  ", "latest_update": "LATESTWORDS", "notes": "N", "owner": "O"}
        self.assertEqual(self.words({"id": "ABC-A-001", "source": "client"}, row), "Agree the plan")
        self.assertEqual(self.words({"id": "ABC-D-001", "source": "client"}, {"decision": "Use the blue vendor", "description": "x", "client_message": ""}),
                         "Use the blue vendor")
        self.assertEqual(self.words({"id": "ABC-A-001", "source": "client"}, {**row, "client_message": "Said so"}), "Said so")


class Raid3Checker(CheckerBase, unittest.TestCase):
    TYPE, SIZE, MODULE = "raid3", 3, raid3


if __name__ == "__main__":
    unittest.main()
