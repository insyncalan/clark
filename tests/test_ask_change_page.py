"""#47e part 2: a suggested change in the ask panel, in a real browser, against the real page, the real change routes and the real
store (the answer comes from a STUB provider; nothing here calls a model).

Run: python3 dev/run_tests.py test_ask_change_page
Covers: the card's before and after come from the data, Apply saves once and the board shows it, Done with Undo puts it back, a
change from an answer that read your files needs the box ticked and Enter alone never applies it, a refusal is one plain line,
the off state leaves nothing to press, the card at 1400 and 900 px in light and dark, and every new sentence in askWords.js.
Fictional data only.
"""
import json
import re
import threading
import time
import unittest
from unittest import mock

from _demo import USER
from _paths import ROOT
import _testpage as testpage
from _real_server import real_server
from clark import page, theme as themes
from test_report_editor import Base
from test_server import chrome
from clark import ask, ask_apply, ask_passages, ask_service

WORDS = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "askWords.js").read_text(encoding="utf-8")
CARD = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "AskChange.jsx").read_text(encoding="utf-8")
NEVER = re.compile(r"\w*(Error|Exception)\b|Traceback|JSON|Not allowed|Bad request|\bAPI\b|\bHTTP\b|!")
FILE = ask.Passage("notes/plan.md", "The cut-over plan was signed off on Monday, so it can be closed.")
NEW_WORDS = ("CHANGE_HEAD", "NEW_HEAD", "FIELD", "NOW", "AFTER", "NOT_SET", "APPLY", "APPLYING_LINE", "FROM_FILE", "CONFIRM_LINE",
             "CONFIRM_NO_PASSAGE_LINE", "CONFIRM_BOX", "DONE_LINE", "UNDO", "UNDONE_LINE", "UNDO_FAILED_LINE", "REFUSED_LINE",
             "NOT_SAVED_LINE", "CHANGES_GONE_LINE", "WHY", "NOT_NOW", "NOT_NOW_LINE", "BRING_BACK", "UNDO_ALL", "ALL_UNDONE_LINE")


class Card(Base):
    THEME = "prototype-2.0"      # row 1292: the new card is Classic only; CardsStayAsTheyWere serves no Theme

    def setUp(self):
        super().setUp()
        self.s.close()
        css = themes.css(self.THEME) if self.THEME else None
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css) if css else testpage.html(), seam=self.seam)
        self.addCleanup(self.s.close)
        self.demo.plant_builtin_sections()      # row 1193: a new project's report has Work items lists, these tests pin the built-in sections
        self.action = self.demo.action(owner="Sam Lee", client_visible=1)
        self.provider = ask.StubProvider(reply="")
        self.files = ()
        self.service = ask_service.AskService(self.store.path, self.provider, [],
                                              applier=ask_apply.AskApply(self.store.path, [], USER))
        self.s.httpd.ask = self.service
        patch = mock.patch.object(ask_service.ask_passages, "folder_data",
                                  lambda *_a, **_k: ask_passages.FolderData(passages=tuple(self.files)))
        patch.start()
        self.addCleanup(patch.stop)

    def says(self, *lines, files=()):
        self.files = files
        self.provider.reply = "\n".join(("Here is what I found.",) + lines)

    def close_it(self, **more):
        return "CHANGE: " + json.dumps({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan",
                                        "status": "Closed", **more})

    def opened(self, cdp):
        p = self.visit(cdp)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel') && !document.querySelector('#ask-send').disabled", "the panel is ready")
        return p

    def ask_it(self, p, text="What should change?"):
        p.js("document.querySelector('#ask-box').focus()")
        p.type(text)
        p.key("Enter", code="Enter", vk=13)

    def card(self, p):
        p.until("!!document.querySelector('[data-ask-change], [data-ask-refused]')", "the card came")

    def status(self):
        return self.store.read("actions", ref=self.action)["status"]


class TheCard(Card):
    def test_before_and_after_from_the_data_then_apply_then_undo(self):
        self.says(self.close_it())
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            row = "document.querySelector('[data-ask-change] [data-field=status]')"
            self.assertEqual(p.js(f"{row}.querySelector('[data-before]').textContent"), "Open")
            self.assertEqual(p.js(f"{row}.querySelector('[data-after]').textContent"), "Closed")
            self.assertEqual(p.js("document.querySelector('[data-ask-change]').dataset.ref"), self.action)
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-confirm]').length"), 0, "a change from the report needs no Confirm")
            self.assertEqual(self.status(), "Open", "showing it saved nothing")
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "Done.")
            self.assertEqual(self.status(), "Closed")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-apply]').length"), 0, "Apply is gone: one Apply, one step")
            p.js("document.querySelector('[data-ask-undo]').click()")
            p.until("document.querySelector('[data-ask-line]').textContent === 'Undone. The old values are back.'", "Undone")
            self.assertEqual(self.status(), "Open")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-undo]').length"), 0)
            self.assertTrue(any(w == "undo" for w, _r in self.sent), "Undo went through the board's own /api/undo")
            self.assertFalse(any(w == "change" for w, _r in self.sent), "Apply never used the hand-edit route")

    def test_apply_and_undo_from_the_keyboard_keep_focus_in_the_card(self):
        self.says(self.close_it())
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            inside = "!!document.activeElement && !!document.activeElement.closest('[data-ask-change]')"
            p.js("(() => { const b = document.querySelector('[data-ask-apply]'); b.focus(); b.click(); })()")      # a key press on a focused button is a click that leaves focus on it
            p.until("document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "Done.")
            p.until(inside, "after Apply focus is in the card, not on the page body")
            p.js("(() => { const b = document.querySelector('[data-ask-undo]'); b.focus(); b.click(); })()")
            p.until("document.querySelector('[data-ask-line]').textContent === 'Undone. The old values are back.'", "Undone")
            p.until(inside, "after Undo focus is in the card, not on the page body")

    def test_an_applied_card_stays_done_with_undo_after_the_panel_is_closed_and_opened(self):
        self.says(self.close_it())
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "Done.")
            p.js("document.querySelector('#ask-close').click()")
            p.until("!document.querySelector('#ask-panel')", "the panel is closed")
            p.js("document.body.focus()")
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel') && !document.querySelector('#ask-send').disabled", "the panel is back")
            p.until("!!document.querySelector('[data-ask-change]')", "the card is back")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-apply]').length"), 0, "an applied change is not offered again")
            self.assertTrue(p.js("document.querySelector('[data-ask-line]').textContent.startsWith('Done.')"))
            p.js("document.querySelector('[data-ask-undo]').click()")
            p.until("document.querySelector('[data-ask-line]').textContent === 'Undone. The old values are back.'", "Undone")
            self.assertEqual(self.status(), "Open")

    def test_a_use_case_change_shows_in_plain_words_and_applies_with_undo(self):         # issue 729
        uc = self.demo.use_case
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", uc, {"standing": "<p>Going <strong>well</strong></p>", "client_visible": 1})
        self.says("CHANGE: " + json.dumps({"op": "change", "id": uc, "current_title": "Invoice matching", "status": "Flag",
                                            "standing": "Two files are late."}))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            cell = lambda f, w: p.js(f"document.querySelector('[data-ask-change] [data-field={f}] [data-{w}]').textContent")
            label = lambda f: p.js(f"document.querySelector('[data-ask-change] [data-field={f}] [data-label]').textContent")
            self.assertEqual((label("status"), cell("status", "before"), cell("status", "after")), ("Status", "On track", "Flag"))
            self.assertEqual((label("standing"), cell("standing", "before"), cell("standing", "after")),
                             ("Where it stands", "Going well", "Two files are late."))
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-change] [data-field=commitment]').length"), 0, "no commitment row")
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "Done.")
            self.assertEqual(self.store.read("use_cases", ref=uc)["status"], "Flag")
            p.js("document.querySelector('[data-ask-undo]').click()")
            p.until("document.querySelector('[data-ask-line]').textContent === 'Undone. The old values are back.'", "Undone")
            self.assertEqual(self.store.read("use_cases", ref=uc)["status"], "On track")

    def test_a_change_from_your_files_needs_the_box_and_enter_alone_never_applies(self):
        self.says(self.close_it(), "CITE: P5", files=(FILE,))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("!!document.querySelector('[data-ask-confirm]')", "the Confirm box")
            self.assertIn("signed off on Monday", p.js("document.querySelector('[data-ask-passage] blockquote').textContent"))
            self.assertEqual(p.js("document.querySelector('[data-ask-passage] figcaption').textContent"), "From your file: notes/plan.md")
            self.assertTrue(p.js("document.querySelector('[data-ask-apply]').disabled"), "Apply waits for the box")
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.js("document.querySelector('[data-ask-confirm]').focus()")
            p.key("Enter", code="Enter", vk=13)
            self.assertFalse(p.js("document.querySelector('[data-ask-confirm]').checked"), "Enter does not tick the box")
            p.js("document.querySelector('#ask-box').focus()")
            p.key("Enter", code="Enter", vk=13)
            self.assertEqual(self.status(), "Open")
            p.js("document.querySelector('[data-ask-confirm]').click()")
            p.until("!document.querySelector('[data-ask-apply]').disabled", "Apply is ready once ticked")
            p.js("document.querySelector('[data-ask-apply]').focus()")
            for kind in ("keyDown", "keyUp"):    # a real Enter carries its character, which is what makes a button click
                p.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
                                                      "text": "\r"}, p.sid)
            time.sleep(0.4)
            self.assertEqual(self.status(), "Open", "Enter alone on Apply never applies a change from a file")
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "Done.")
            self.assertEqual(self.status(), "Closed")

    # ----- #1292 S4: change cards (item link and title, old struck through, new marked, Why, Apply and Not now, Apply all, one Undo)
    def test_the_card_names_the_item_strikes_the_old_marks_the_new_and_gives_the_why(self):
        self.says(self.close_it(why="It was signed off on Monday."))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            link = "document.querySelector('[data-ask-change] [data-ask-item]')"
            self.assertEqual(p.js(f"{link}.textContent"), self.action)
            self.assertIn(f"item={self.action}", p.js(f"{link}.getAttribute('href')"))
            self.assertEqual(p.js("document.querySelector('[data-ask-change] [data-ask-title]').textContent"), "Draft the cut-over plan")
            self.assertEqual(p.js("document.querySelector('[data-field=status] del[data-before]').textContent"), "Open")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('[data-field=status] del[data-before]')).textDecorationLine"), "line-through")
            self.assertEqual(p.js("document.querySelector('[data-field=status] mark[data-after]').textContent"), "Closed")
            self.assertEqual(p.js("document.querySelector('[data-ask-why]').textContent"), "Why: It was signed off on Monday.")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-change] table').length"), 0, "the table is gone")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-apply-all]').length"), 0, "one card: no Apply all")

    def owners_page(self, lines, ids, expect):
        """Ask for `lines`, then read each card's owner span at 1400 and 900: expect maps an ID (or 'new') to its text, or None for no span."""
        self.says(*lines)
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until(f"document.querySelectorAll('[data-ask-change]').length === {len(lines)}", "the cards")
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for i, want in enumerate(expect):
                    card = f"document.querySelectorAll('[data-ask-change]')[{i}]"
                    got = p.js(f"[...{card}.querySelectorAll('[data-ask-owner]')].map(e => e.textContent)")
                    self.assertEqual(got, [] if want is None else [want], f"{width}: card {i} {ids[i]}")

    def change_line(self, ref, title, **more):
        return "CHANGE: " + json.dumps({"op": "change", "id": ref, "current_title": title, "status": "Closed", **more})

    def test_owner_tbc_shows_owner_tbc_as_stored(self):         # ruling 20-11 on 2035: TBC shows 'Owner: TBC'
        tbc = self.demo.action(owner="TBC", description="Unassigned job")
        self.owners_page([self.change_line(self.action, "Draft the cut-over plan"), self.change_line(tbc, "Unassigned job")],
                         ["named", "tbc"], ["Owner: Sam Lee", "Owner: TBC"])

    def test_a_blank_owner_and_a_new_item_show_no_owner(self):
        blank = self.demo.action(description="Blank job")
        self.store.con.execute("UPDATE actions SET owner = '  ' WHERE id = ?", (blank,))
        self.store.con.commit()
        uc = self.demo.use_case
        new = "CHANGE: " + json.dumps({"op": "new", "kind": "action", "title": "Book the room", "owner": "Zed Ng"})
        new_tbc = "CHANGE: " + json.dumps({"op": "new", "kind": "action", "title": "Book the hall", "owner": "TBC"})
        self.owners_page([self.change_line(blank, "Blank job"), new, new_tbc, self.change_line(uc, "Invoice matching", status="Flag")],
                         ["blank", "new", "new TBC", "use case"], [None, None, None, None])

    def test_a_decision_shows_made_by_the_name_or_tbc(self):
        with self.store.step("dashboard", USER) as st:
            named = st.create("decisions", {"project": "ABC", "decision": "Use the new tool", "status": "Pending", "made_by": "Dev Lal", "source": "demo"})
            tbc = st.create("decisions", {"project": "ABC", "decision": "Pick a venue", "status": "Pending", "made_by": "TBC", "source": "demo"})
        lines = ["CHANGE: " + json.dumps({"op": "change", "id": r, "current_title": t, "needed_by": "2030-01-05"}) for r, t in ((named, "Use the new tool"), (tbc, "Pick a venue"))]
        self.owners_page(lines, ["named", "tbc"], ["Made by: Dev Lal", "Made by: TBC"])

    def test_a_reason_with_markup_is_drawn_as_text(self):
        self.says(self.close_it(why="<img src=x onerror=alert(1)> done"))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-why] img').length"), 0)
            self.assertIn("<img", p.js("document.querySelector('[data-ask-why]').textContent"))

    def test_without_a_reason_there_is_no_why_line(self):
        self.says(self.close_it())
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-why]').length"), 0)

    def test_not_now_saves_nothing_and_bring_it_back_offers_it_again(self):
        self.says(self.close_it())
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.js("document.querySelector('[data-ask-not-now]').click()")
            p.until("document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent.startsWith('Not now.')", "Not now")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-apply]').length"), 0)
            self.assertEqual(self.status(), "Open")
            self.assertEqual(p.js("document.querySelector('[data-ask-bring-back]').textContent"), "Bring it back")
            p.js("document.querySelector('[data-ask-bring-back]').click()")
            p.until("!!document.querySelector('[data-ask-apply]')", "Apply is back")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-line]').length"), 0)
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "Done.")
            self.assertEqual(self.status(), "Closed")

    def two_cards(self):
        self.second = self.demo.action(owner="Kim Roe", description="Order the badges")
        self.says(self.close_it(), "CHANGE: " + json.dumps({"op": "change", "id": self.second, "current_title": "Order the badges", "status": "Closed"}))

    def test_apply_all_saves_every_card_and_one_undo_puts_them_all_back(self):
        self.two_cards()
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "both cards")
            self.assertEqual(p.js("document.querySelector('[data-ask-apply-all]').textContent"), "Apply all 2")
            p.js("document.querySelector('[data-ask-apply-all]').click()")
            p.until("!!document.querySelector('[data-ask-group-line]') && !!document.querySelector('[data-ask-undo-all]')", "done with one Undo")
            self.assertEqual(p.js("document.querySelector('[data-ask-group-line]').textContent.startsWith('Done. 2 changes saved.')"), True)
            self.assertEqual((self.status(), self.store.read("actions", ref=self.second)["status"]), ("Closed", "Closed"))
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-apply-all], [data-ask-apply], [data-ask-undo]').length"), 0, "one Undo for the lot, none per card")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-undo-all]').length"), 1)
            self.assertEqual(p.js("document.querySelector('[data-ask-undo-all]').textContent"), "Undo all")
            p.js("document.querySelector('[data-ask-undo-all]').click()")
            p.until("document.querySelector('[data-ask-group-line]').textContent === 'Undone. The old values are back.'", "Undone")
            self.assertEqual((self.status(), self.store.read("actions", ref=self.second)["status"]), ("Open", "Open"))
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-undo-all]').length"), 0)

    def test_apply_all_skips_a_card_put_aside_with_not_now(self):
        self.two_cards()
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "both cards")
            p.js("document.querySelectorAll('[data-ask-not-now]')[1].click()")
            p.until("document.querySelectorAll('[data-ask-apply]').length === 1", "one card left")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-apply-all]').length"), 0, "one still offered: no Apply all")
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "Done.")
            self.assertEqual((self.status(), self.store.read("actions", ref=self.second)["status"]), ("Closed", "Open"))

    def test_apply_all_n_counts_and_applies_only_the_cards_still_offered(self):
        third = self.demo.action(owner="Pat Kay", description="Book the room")
        self.two_cards()
        self.says(self.close_it(), "CHANGE: " + json.dumps({"op": "change", "id": self.second, "current_title": "Order the badges", "status": "Closed"}),
                  "CHANGE: " + json.dumps({"op": "change", "id": third, "current_title": "Book the room", "status": "Closed"}))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 3", "three cards")
            self.assertEqual(p.js("document.querySelector('[data-ask-apply-all]').textContent"), "Apply all 3")
            p.js("document.querySelectorAll('[data-ask-not-now]')[2].click()")
            p.until("document.querySelector('[data-ask-apply-all]').textContent === 'Apply all 2'", "N follows what will be applied")
            p.js("document.querySelector('[data-ask-apply-all]').click()")
            p.until("!!document.querySelector('[data-ask-group-line]')", "the group line")
            self.assertEqual(p.js("document.querySelector('[data-ask-group-line]').firstChild.textContent"), "Done. 2 changes saved.")
            self.assertEqual((self.status(), self.store.read("actions", ref=self.second)["status"], self.store.read("actions", ref=third)["status"]),
                             ("Closed", "Closed", "Open"), "exactly those 2")

    def test_undo_all_leaves_a_card_put_aside_with_not_now_as_it_was(self):         # row 1292 sweep: only a card that was Done is marked Undone
        self.two_cards()
        third = self.demo.action(owner="Pat Kay", description="Book the room")
        self.provider.reply += "\nCHANGE: " + json.dumps({"op": "change", "id": third, "current_title": "Book the room", "status": "Closed"})
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 3", "three cards")
            p.js("document.querySelectorAll('[data-ask-not-now]')[2].click()")
            p.until("document.querySelectorAll('[data-ask-apply]').length === 2", "two left")
            p.js("document.querySelector('[data-ask-apply-all]').click()")
            p.until("!!document.querySelector('[data-ask-undo-all]')", "done with one Undo")
            p.js("document.querySelector('[data-ask-undo-all]').click()")
            p.until("document.querySelector('[data-ask-group-line]').textContent === 'Undone. The old values are back.'", "Undone")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-bring-back]').length"), 1, "the card put aside is still put aside")
            self.assertEqual(self.store.read("actions", ref=third)["status"], "Open")

    def test_a_partial_undo_all_undoes_the_done_ones_and_names_the_one_left(self):         # row 1292: skipped is not total failure
        self.two_cards()
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "both cards")
            p.js("document.querySelector('[data-ask-apply-all]').click()")
            p.until("!!document.querySelector('[data-ask-undo-all]')", "done with one Undo")
            with self.store.step("dashboard", USER) as st:          # a later change to the second action: its step is left as it is
                st.update("actions", self.second, {"status": "Delayed"})
            p.js("window.__undoBodies = []; const f = window.fetch; window.fetch = (u, o) => { if (String(u).includes('/api/undo')) window.__undoBodies.push(JSON.parse(o.body)); return f(u, o); }")
            p.js("document.querySelector('[data-ask-undo-all]').click()")
            p.until("document.querySelectorAll('[data-ask-line]')[0] && document.querySelectorAll('[data-ask-line]')[0].textContent.startsWith('Undone.')", "the first card undone")
            lines = p.js("[...document.querySelectorAll('[data-ask-line]')].map((l) => l.firstChild.textContent)")
            self.assertEqual(lines, ["Undone. The old values are back.", "That could not be undone. Open the item and change it back yourself."])
            self.assertEqual((self.status(), self.store.read("actions", ref=self.second)["status"]), ("Open", "Delayed"))
            self.assertEqual(p.js("document.querySelector('[data-ask-group-line]').firstChild.textContent"), "That could not be undone. Open the item and change it back yourself.")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-undo-all]').length"), 1, "Undo all stays for the one left")
            p.js("document.querySelector('[data-ask-undo-all]').click()")      # pressed again: only the one left is asked for, so it is left again and the first stays undone
            time.sleep(1.5)
            p.until("document.querySelectorAll('[data-ask-undo-all]').length === 1", "the second press is answered")
            self.assertEqual(p.js("[...document.querySelectorAll('[data-ask-line]')].map((l) => l.firstChild.textContent.slice(0, 7))"), ["Undone.", "That co"])
            self.assertEqual((self.status(), self.store.read("actions", ref=self.second)["status"]), ("Open", "Delayed"), "nothing moved on the second press")
            sent = p.js("window.__undoBodies.map((b) => b.steps)")      # the steps each press sent: the second press asks again for the stuck one only
            self.assertEqual(len(sent), 2, "one request per press")
            self.assertEqual(len(sent[0]), 2)
            self.assertEqual(len(sent[1]), 1, "the done step is not sent again")
            self.assertEqual(sent[1], [max(sent[0])], "the stuck step is the second action's, the later one")

    def test_one_change_that_cannot_be_undone_leaves_the_other_cards_their_undo(self):         # row 1292
        self.two_cards()
        calls, real = [], self.service.change_apply

        def second_cannot_be_undone(body):
            calls.append(1)
            status, reply = real(body)
            if len(calls) == 2:
                reply = dict(reply, undoable=False)
            return status, reply
        with chrome() as cdp, mock.patch.object(self.service, "change_apply", second_cannot_be_undone):
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "both cards")
            p.js("document.querySelector('[data-ask-apply-all]').click()")
            p.until("document.querySelectorAll('[data-ask-line]').length === 2", "both saved")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-undo]').length"), 1, "the card that can be undone keeps its Undo")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-undo-all]').length"), 0)
            p.js("document.querySelector('[data-ask-undo]').click()")
            p.until("document.querySelector('[data-ask-line]').textContent.startsWith('Undone.')", "the first undone")
            self.assertEqual((self.status(), self.store.read("actions", ref=self.second)["status"]), ("Open", "Closed"))

    def test_apply_all_stops_at_the_first_asking_off(self):         # row 1292: nothing more is applied once asking is off
        self.two_cards()
        third = self.demo.action(owner="Pat Kay", description="Book the room")
        self.provider.reply += "\nCHANGE: " + json.dumps({"op": "change", "id": third, "current_title": "Book the room", "status": "Closed"})
        calls, real = [], self.service.change_apply

        def off_at_the_second(body):
            calls.append(1)
            if len(calls) == 2:
                return 409, {"ok": False, "code": "asking_off", "message": ask_apply.ASKING_OFF}
            return real(body)
        with chrome() as cdp, mock.patch.object(self.service, "change_apply", off_at_the_second):
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 3", "three cards")
            p.js("document.querySelector('[data-ask-apply-all]').click()")
            p.until("document.querySelectorAll('#ask-off').length === 1", "asking is off")
            time.sleep(1)
            self.assertEqual(len(calls), 2, "the third was never sent")
            self.assertEqual((self.status(), self.store.read("actions", ref=self.second)["status"], self.store.read("actions", ref=third)["status"]), ("Closed", "Open", "Open"))

    def test_apply_all_is_not_offered_when_a_card_needs_the_confirm_box(self):
        self.two_cards()
        self.provider.reply += "\nCITE: P5"
        self.files = (FILE,)
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "both cards")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-apply-all]').length"), 0)

    def test_a_refusal_is_one_plain_line_with_a_next_step(self):
        self.says("CHANGE: " + json.dumps({"op": "archive", "id": self.action}))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            text = p.js("document.querySelector('[data-ask-refused]').textContent")
            self.assertIn("isn't available yet", text)
            self.assertIn("Nothing was changed", text)
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-apply]').length"), 0)

    def test_the_card_says_it_is_saving_while_the_save_is_under_way(self):         # row 1292 sweep: the transient saving state
        self.says(self.close_it())
        gate, real = threading.Event(), self.service.change_apply

        def slow(body):
            gate.wait(20)
            return real(body)
        with chrome() as cdp, mock.patch.object(self.service, "change_apply", slow):
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.js("document.querySelector('[data-ask-apply]').click()")
            try:
                p.until("!!document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent === 'Saving the change\u2026'", "the saving line")
            finally:
                gate.set()
            p.until("document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "Done.")

    def test_a_busy_refusal_shows_its_own_sentence_on_the_card_and_keeps_the_panel_on(self):         # row 1292 sweep: 409 other than asking_off
        self.says(self.close_it())
        busy = (409, {"ok": False, "code": "busy", "message": "Another change is being saved. Try again in a moment."})
        with chrome() as cdp, mock.patch.object(self.service, "change_apply", lambda body: busy):
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("!!document.querySelector('[data-ask-line].problem')", "the failed line")
            self.assertEqual(p.js("document.querySelector('[data-ask-line]').textContent"), "Another change is being saved. Try again in a moment.")
            self.assertEqual(p.js("document.querySelectorAll('#ask-off').length"), 0, "only asking_off turns the panel off")

    def test_apply_all_says_how_many_were_saved_when_one_was_not(self):         # row 1292 sweep: saved === offered.length
        self.two_cards()
        calls, real = [], self.service.change_apply

        def second_fails(body):
            calls.append(1)
            if len(calls) == 2:
                return 409, {"ok": False, "code": "busy", "message": "Another change is being saved. Try again in a moment."}
            return real(body)
        with chrome() as cdp, mock.patch.object(self.service, "change_apply", second_fails):
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "both cards")
            p.js("document.querySelector('[data-ask-apply-all]').click()")
            p.until("!!document.querySelector('[data-ask-group-line]')", "the group line")
            self.assertEqual(p.js("document.querySelector('[data-ask-group-line]').firstChild.textContent"),
                             "1 of 2 changes were saved. The others were not. Check the board and ask again.", "real N and M, exact words")
            self.assertEqual((self.status(), self.store.read("actions", ref=self.second)["status"]), ("Closed", "Open"))

    def test_apply_all_says_nothing_of_partial_saves_when_none_saved(self):         # the note is for some but not all
        self.two_cards()
        busy = (409, {"ok": False, "code": "busy", "message": "Another change is being saved. Try again in a moment."})
        with chrome() as cdp, mock.patch.object(self.service, "change_apply", lambda body: busy):
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "both cards")
            p.js("document.querySelector('[data-ask-apply-all]').click()")
            p.until("document.querySelectorAll('[data-ask-line]').length === 2", "both cards say it was not saved")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-group-line], [data-ask-undo-all]').length"), 0, "no 'N of M saved' note, no Undo all")
            self.assertEqual((self.status(), self.store.read("actions", ref=self.second)["status"]), ("Open", "Open"))

    def test_off_leaves_nothing_to_press(self):
        self.says(self.close_it())
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            with self.store.step("dashboard", USER) as st:
                st.update("app_settings", "1", {"ask_enabled": False})
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("!!document.querySelector('#ask-off')", "the panel went to the off line")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-change] button, [data-ask-change] input').length"), 0)
            self.assertEqual(self.status(), "Open")

    def test_markup_in_a_passage_is_inert_text(self):
        planted = ask.Passage("notes/x.md", '<img src=x onerror="window.__pwn=1"><b>bold</b>')
        self.says(self.close_it(), "CITE: P5", files=(planted,))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("!!document.querySelector('[data-ask-passage]')", "the passage")
            self.assertEqual(p.js("document.querySelectorAll('.ask-changes img, .ask-changes b').length"), 0)
            self.assertEqual(p.js("typeof window.__pwn"), "undefined")

    def test_laptop_widths_light_and_dark(self):
        self.says(self.close_it(), "CITE: P5", files=(FILE,))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("!!document.querySelector('[data-ask-confirm]')", "the card with its Confirm")
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for theme in ("light", "dark"):
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    card = "document.querySelector('[data-ask-change]')"
                    self.assertTrue(p.js(f"{card}.scrollWidth <= {card}.clientWidth + 1"), f"{width} {theme}: the card fits")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "no sideways scroll")
                    bg = p.js(f"getComputedStyle({card}).backgroundColor")
                    fg = p.js(f"getComputedStyle({card}).color")
                    self.assertNotEqual(bg, fg)
                    if theme == "dark":
                        self.assertNotEqual(bg, "rgb(255, 255, 255)", "the card follows dark mode")
                    r = p.js("(function(){var a=document.querySelector('[data-ask-apply]').getBoundingClientRect(),"
                             "b=document.querySelector('#ask-panel').getBoundingClientRect();return a.right<=b.right && a.left>=b.left})()")
                    self.assertTrue(r, "Apply is inside the panel")


    def test_the_published_css_has_neither_changed_rule(self):         # row 936: edit.css is served-page only
        css = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8")
        self.assertIn(".ask-passage {", css)
        view = (ROOT / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for needle in (".ask-passage", ".ask-change {"):
            self.assertNotIn(needle, view)
        self.assertIn(".ask-passage {", (ROOT / "src" / "clark" / "page" / "page.html").read_text(encoding="utf-8"))


class CardsStayAsTheyWere(Card):
    """Row 1292: Cards (no Theme) is frozen. The card draws as it did on main: the table, the old header, Apply alone."""
    THEME = None

    def test_a_card_in_cards_is_the_card_main_drew_and_has_none_of_the_new_pieces(self):
        second = self.demo.action(owner="Kim Roe", description="Order the badges")
        self.says("CHANGE: " + json.dumps({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "owner": "Ana Ruiz", "why": "She took it on."}),
                  "CHANGE: " + json.dumps({"op": "change", "id": second, "current_title": "Order the badges", "status": "Closed"}))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "two cards")
            self.assertFalse(p.js("!!document.getElementById('theme')"), "no Theme layered")
            html = p.js("document.querySelectorAll('[data-ask-change]')[0].outerHTML")
            ref = self.action
            expect = (f'<section class="ask-change" data-ask-change="true" data-ref="{ref}"><header class="ask-change-head"><strong>Suggested change</strong>'
                      f'<span class="muted">{ref}</span></header><table class="ask-diff"><thead><tr><th scope="col">Field</th><th scope="col">Now</th>'
                      '<th scope="col">After Apply</th></tr></thead><tbody><tr data-field="owner"><th scope="row">Owner</th><td data-before="true">Sam Lee</td>'
                      '<td data-after="true">Ana Ruiz</td></tr></tbody></table><div class="ask-change-actions"><button type="button" class="btn primary sm" '
                      'data-ask-apply="true">Apply</button></div></section>')
            self.maxDiff = None
            self.assertEqual(html, expect)
            for sel in ("[data-ask-owner]", "[data-ask-why]", "[data-ask-title]", "[data-ask-item]", "[data-ask-not-now]", "[data-ask-apply-all]", "[data-ask-group-line]"):
                self.assertEqual(p.js(f"document.querySelectorAll('{sel}').length"), 0, f"{sel} is Classic only")

    def test_a_group_line_cannot_appear_in_cards_after_applying_each(self):
        second = self.demo.action(owner="Kim Roe", description="Order the badges")
        self.says(self.close_it(), "CHANGE: " + json.dumps({"op": "change", "id": second, "current_title": "Order the badges", "status": "Closed"}))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-apply]').length === 2", "two Apply buttons")
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("!!document.querySelector('[data-ask-undo]')", "Done with Undo")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-undo-all], [data-ask-bring-back]').length"), 0)

    def test_the_card_has_a_quiet_look_and_a_small_flat_apply(self):         # row 780
        self.says(self.close_it())
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for theme in ("light", "dark"):
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    css = lambda sel, prop: p.js(f"getComputedStyle(document.querySelector('{sel}'))['{prop}']")  # noqa: E731
                    self.assertEqual(css("[data-ask-change]", "borderLeftWidth"), css("[data-ask-change]", "borderTopWidth"), f"{width} {theme}: the card has no one-side stripe (row 936)")
                    self.assertEqual(css("[data-ask-apply]", "backgroundImage"), "none", f"{width} {theme}: Apply is flat, not the pill gradient")
                    self.assertEqual(css("[data-ask-apply]", "boxShadow"), "none", f"{width} {theme}: no glow")
                    self.assertEqual(css("[data-ask-apply]", "minHeight"), "24px")
                    self.assertEqual(p.js("document.querySelector('[data-ask-apply]').textContent"), "Apply", "the words are unchanged")

    def edge_and_contrast(self, p, sel):
        """The sides' widths and the text-on-background contrast of sel, as the page draws it now."""
        return p.js("""(function(sel){ var el = document.querySelector(sel), cs = getComputedStyle(el);
            var num = function(c){ return c.match(/[\\d.]+/g).map(Number); };
            var bg = null; for (var n = el; n && !bg; n = n.parentElement) { var c = num(getComputedStyle(n).backgroundColor);
              if (c.length < 4 || c[3] > 0.99) { if (c.length < 4 || c[3] > 0) bg = c; } }
            var lin = function(v){ v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
            var lum = function(c){ return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]); };
            var fg = num(cs.color), a = lum(fg), b = bg ? lum(bg) : 1;
            return {l: cs.borderLeftWidth, t: cs.borderTopWidth, r: cs.borderRightWidth, b: cs.borderBottomWidth,
                    ratio: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)}; })(%s)""" % json.dumps(sel))

    def check_no_stripe(self, p, cdp, sel):
        for width in (1400, 900):
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            for theme in ("light", "dark"):
                p.js(f"document.documentElement.dataset.theme = '{theme}'")
                got = self.edge_and_contrast(p, sel)
                self.assertEqual({got["l"], got["r"], got["b"]}, {got["t"]}, f"{sel} {width} {theme}: no one-side stripe (row 936)")
                self.assertGreaterEqual(got["ratio"], 4.5, f"{sel} {width} {theme}: text reads on its background")

    def test_the_card_has_no_one_side_stripe_and_reads(self):          # row 936
        self.says(self.close_it())
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            self.check_no_stripe(p, cdp, "[data-ask-change]")

    def test_the_passage_has_no_one_side_stripe_and_reads(self):       # row 936
        self.says(self.close_it(), "CITE: P5", files=(FILE,))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("!!document.querySelector('[data-ask-passage]')", "the passage")
            self.check_no_stripe(p, cdp, "[data-ask-passage] blockquote")
            self.check_no_stripe(p, cdp, "[data-ask-passage]")


class Words(unittest.TestCase):
    def test_every_new_sentence_is_plain_and_starts_with_what_happened_or_the_next_step(self):
        said = dict(re.findall(r'export const ([A-Z_]+) = "((?:[^"\\]|\\.)*)"', WORDS))
        for name in NEW_WORDS:
            self.assertIn(name, said)
            text = said[name]
            self.assertIsNone(NEVER.search(text), f"{name}: {text}")
            self.assertFalse(re.match(r"(ask )?clark", text, re.I), f"{name} starts with the product name")
        for name in NEW_WORDS:
            if name.endswith("_LINE"):
                self.assertRegex(said[name], r"[.…]$", name)
        for name in ("REFUSED_LINE", "NOT_SAVED_LINE", "CHANGES_GONE_LINE", "UNDO_FAILED_LINE", "CONFIRM_LINE"):
            self.assertRegex(said[name], r"(Ask again|Make it yourself|change it back yourself|press Apply)", f"{name} has a next step")

    def test_the_card_draws_text_only_and_says_nothing_of_its_own(self):
        self.assertNotIn("innerHTML", CARD)
        self.assertNotIn("dangerouslySetInnerHTML", CARD)
        self.assertIsNone(re.search(r'>\s*[A-Za-z][^<{]*[a-z]\s*<', CARD), "every sentence comes from askWords.js")

    def test_the_published_page_has_no_card(self):
        html = (ROOT / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for needle in ("/api/ask/change", "ask-change", "data-ask-apply", "After Apply"):
            self.assertNotIn(needle, html)
        self.assertIn("/api/ask/change/apply", (ROOT / "src" / "clark" / "page" / "page.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
