"""Row 1270, the Peek a RAID card opens (ticket decisions 8, 10 and 11): Previous and Next step through the section's cards, the author's View Peek
shows the item's Latest update, and a card's Peek in a published file has no Client wording row. A Peek opened any other way is as it was.

Run: python3 dev/run_tests.py test_raid_cards_peek_steps_1270
Fictional rows. Opened in headless Chrome at 1400 and 900 (the only widths checked).
"""
import json

import tempfile

from _real_server import real_server
from clark import page, theme
from _demo import USER
from _publish import PublishedFile
import test_glance_page as glance
from test_report_editor import Base as PageBase
from test_server import chrome, wait

PEEK = """(() => { const p = document.querySelector('#peek'); const open = !!p && !p.hidden && p.getBoundingClientRect().width > 0;
  const id = p && p.querySelector('.pk-id, [data-pk-id]'); const dis = (s) => { const b = p && p.querySelector(s); return b ? b.disabled : null; };
  return { open, text: open ? p.textContent : '', latest: !!(p && p.querySelector('[data-ms-row=latest_update]')), wording: !!(p && p.querySelector('[data-ms-row=client_message]')),
           latestText: p && p.querySelector('[data-ms-row=latest_update]') ? p.querySelector('[data-ms-row=latest_update]').textContent : '', prev: dis('[data-pk-prev]'), next: dis('[data-pk-next]') }; })()"""

ESC_KEY = "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))"


def seed(self):
    """A risk, a decision and an action, put on the cards in that order (the Work items list orders them differently), and an item with no card."""
    self.demo.plant_builtin_sections()
    with self.store.step("dashboard", USER) as st:
        ids = {
            "risk": st.create("raid", {"project": "ABC", "type": "Risk", "description": "Kiln roof may leak", "raised": "2026-10-01", "source": "demo",
                                       "latest_update": "RISKLATEST", "client_message": "RISKWORDS", "impact": "High", "likelihood": "High"}),
            "decision": st.create("decisions", {"project": "ABC", "decision": "Use the blue vendor", "source": "demo", "status": "Pending",
                                                "needed_by": "2030-02-05", "latest_update": "DECISIONLATEST", "client_message": "DECISIONWORDS"}),
            "action": st.create("actions", {"project": "ABC", "description": "Agree the plan", "raised": "2026-10-01", "source": "demo",
                                            "latest_update": "ACTIONLATEST", "client_message": "ACTIONWORDS", "due_date": "2030-02-01"}),
            "other": st.create("actions", {"project": "ABC", "description": "Not on a card", "raised": "2026-10-01", "source": "demo", "due_date": "2030-02-02"}),
        }
        ref = st.create("report_sections", {"project": "ABC", "type": "raid4", "title": "Fictional cards", "sort_order": 993})
        cards = [{"id": ids[k], "source": "client"} for k in ("risk", "decision", "action")]
        st.update("report_sections", ref, {"body": json.dumps({"v": 2, "across": 3, "cards": cards})})
    ids["sec"] = ref
    return ids


def shown(p):
    return p.js(PEEK)


class Steps:
    """Previous and Next, in whichever page the mixing class draws."""

    def open_card(self, p, item_id):
        p.js(f"document.querySelector('.raid-card[data-card={json.dumps(item_id)}] .raid-id').click()")
        self.assertTrue(wait(lambda: item_id in shown(p)["text"] and shown(p)["open"]), f"the peek opens on {item_id}")

    def step(self, p, hook, item_id):
        p.js(f"document.querySelector('#peek [{hook}]').click()")
        self.assertTrue(wait(lambda: item_id in shown(p)["text"] and shown(p)["open"]), f"{hook} moves the peek to {item_id}: {shown(p)['text'][:80]}")


class FilePeek(PublishedFile, glance.Setup, Steps):
    def test_previous_and_next_step_through_the_cards_and_no_client_wording(self):
        ids = seed(self)
        path = self.publish()
        with chrome() as cdp:
            for w in (1400, 900):
                p = self.draw(cdp, path, width=w)
                self.open_card(p, ids["decision"])
                s = shown(p)
                self.assertEqual((s["prev"], s["next"]), (False, False), "a card in the middle has both steps")
                self.step(p, "data-pk-next", ids["action"])
                self.assertTrue(shown(p)["next"], "the last card has no Next")
                self.assertTrue(wait(lambda: "ACTIONLATEST" in shown(p)["text"]), "the file's Latest update row: " + shown(p)["text"][:400])
                self.step(p, "data-pk-prev", ids["decision"])
                self.assertFalse(shown(p)["wording"], "a decision card's Peek has no Client wording row either")
                self.assertNotIn("DECISIONWORDS", shown(p)["text"])
                self.step(p, "data-pk-prev", ids["risk"])
                s = shown(p)
                self.assertTrue(s["prev"], "the first card has no Previous")
                self.assertTrue(s["latest"] and "RISKLATEST" in s["latestText"], "a card's Peek in the file shows the Latest update")
                self.assertFalse(s["wording"], "a card's Peek in the file has no Client wording row")
                self.assertNotIn("RISKWORDS", s["text"])
                p.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                self.assertTrue(wait(lambda: not shown(p)["open"]), "Esc closes it")
                # the same item opened by its address is the Peek as it was: the Client wording row stays
                p.js(f"location.hash = '#work&p=ABC&item={ids['risk']}'")
                self.assertTrue(wait(lambda: shown(p)["open"] and ids["risk"] in shown(p)["text"]), "the address opens the peek")
                self.assertTrue(shown(p)["wording"], "the Client wording row is still there when no card opened the Peek")
                self.assertIn("RISKWORDS", shown(p)["text"])


    def test_clicking_a_second_card_with_the_peek_open_keeps_it_open_on_the_second(self):
        ids = seed(self)
        path = self.publish()
        with chrome() as cdp:
            for w in (1400, 900):
                p = self.draw(cdp, path, width=w)
                self.open_card(p, ids["risk"])
                p.js(f"document.querySelector('.raid-card[data-card={json.dumps(ids['decision'])}] .raid-id').click()")
                self.assertTrue(wait(lambda: ids["decision"] in shown(p)["text"] and ids["risk"] not in shown(p)["text"]), f"the peek moves to the second card at {w}: {shown(p)['text'][:80]}")
                self.assertTrue(shown(p)["open"], "the peek stays open")
                self.assertEqual(p.js("document.querySelectorAll('.raid-card.rc-sel').length"), 1, "one selected card")
                self.assertEqual(p.js("document.querySelector('.raid-card.rc-sel').dataset.card"), ids["decision"])


class ViewPeek(PageBase, Steps):
    def test_the_authors_view_shows_the_latest_update_of_a_card_and_steps_through_the_cards(self):
        ids = seed(self)
        # the card is Classic only (Cards is frozen): its ID is a button only when the page has <style id="theme">
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=self.seam)
        self.addCleanup(self.s.close)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.view()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.open_card(p, ids["risk"])
                s = shown(p)
                self.assertTrue(s["latest"] and "RISKLATEST" in s["latestText"], f"View shows the Latest update at {w}: {s}")
                self.assertEqual((s["prev"], s["next"]), (True, False), "the first card has no Previous")
                self.step(p, "data-pk-next", ids["decision"])
                self.step(p, "data-pk-next", ids["action"])
                self.assertIn("ACTIONLATEST", shown(p)["latestText"])
                self.assertEqual(shown(p)["next"], True, "the last card has no Next, the Work items list is not followed")
                p.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                self.assertTrue(wait(lambda: not shown(p)["open"]), "Esc closes it")
                # an item opened by its address is not a card's Peek: no Latest update row in View, and Next follows the list
                p.js(f"location.hash = '#dashboard&p=ABC&item={ids['risk']}'")
                self.assertTrue(wait(lambda: shown(p)["open"] and ids["risk"] in shown(p)["text"]), "the address opens the peek")
                self.assertFalse(shown(p)["latest"], "no Latest update row when no card opened the Peek")
                p.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                self.assertTrue(wait(lambda: not shown(p)["open"]))


class PickerRows(PageBase):
    def arr(self, p, expr):
        return json.loads(p.js(f"JSON.stringify({expr})"))

    def test_a_picker_row_says_the_kind_and_the_rating_and_the_search_finds_a_word_or_an_id(self):
        """Ticket 1270, the picker: each row has the ID, the kind, the rating word (risk and issue) and the whole text; search by ID or any word, at 1400 and 900."""
        ids = seed(self)
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", ids["sec"], {"body": json.dumps({"v": 2, "across": 3, "cards": []})})
        q = f"[data-id={json.dumps(ids['sec'])}]"
        rows = lambda p: self.arr(p, f"[...document.querySelectorAll('{q} .rce-opts button')].map(b => b.dataset.pick + '|' + b.textContent)")
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                if not p.js(f"!!document.querySelector('{q} .rce-opts')"):
                    p.js(f"document.querySelector('{q} .rce-pick').click()")
                p.until(f"!!document.querySelector('{q} .rce-opts')", "the picker is open")
                p.js(f"(() => {{ const i = document.querySelector('{q} .rce-picker input'); i.value = ''; i.dispatchEvent(new Event('input', {{bubbles: true}})); }})()")      # the search of the width before is cleared
                row = next(r for r in rows(p) if r.startswith(ids["risk"] + "|"))
                self.assertIn("Risk", row)
                self.assertIn("Red Kiln", row, "the rating word, then the text")
                self.assertIn("Kiln roof may leak", row, "the whole text")
                act = next(r for r in rows(p) if r.startswith(ids["action"] + "|"))
                self.assertIn("Action", act)
                self.assertNotIn("Red", act, "an action has no rating word")
                set_q = lambda v: p.js(f"(() => {{ const i = document.querySelector('{q} .rce-picker input'); i.value = {json.dumps(v)}; i.dispatchEvent(new Event('input', {{bubbles: true}})); }})()")
                set_q("roof")
                p.until(f"document.querySelectorAll('{q} .rce-opts button').length === 1", "a word of the text finds one item")
                set_q(ids["action"].lower())
                p.until(f"document.querySelectorAll('{q} .rce-opts button').length === 1", "an ID finds one item")
                set_q("zzzz nothing")
                p.until(f"document.querySelectorAll('{q} .rce-opts button').length === 0 && document.querySelector('{q} .rce-none').textContent === 'No item matches'", "the no-match line")

    def test_a_long_text_is_whole_in_the_picker_row_and_in_the_search_at_both_widths(self):
        """Ticket 1270, the picker shows the whole text: a long description is in the row, whole, and does not overflow, at 1400 and 900."""
        ids = seed(self)
        long = "The kiln roof may leak in the wet season and ruin the stock stored under it for the whole winter, so the whole long description must show in the picker row without being cut at the end ENDMARK"
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", ids["sec"], {"body": json.dumps({"v": 2, "across": 3, "cards": []})})
            big = st.create("raid", {"project": "ABC", "type": "Risk", "description": long, "raised": "2026-10-01", "source": "demo", "impact": "High", "likelihood": "High"})
        q = f"[data-id={json.dumps(ids['sec'])}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for w, dark in ((1400, False), (900, False), (1400, True), (900, True)):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.js("document.documentElement.dataset.theme = %s" % json.dumps("dark" if dark else "light"))
                if not p.js(f"!!document.querySelector('{q} .rce-opts')"):
                    p.js(f"document.querySelector('{q} .rce-pick').click()")
                p.until(f"!!document.querySelector('{q} .rce-opts')", "the picker is open")
                p.js(f"(() => {{ const i = document.querySelector('{q} .rce-picker input'); i.value = 'ENDMARK'; i.dispatchEvent(new Event('input', {{bubbles: true}})); }})()")
                p.until(f"document.querySelectorAll('{q} .rce-opts button').length === 1", "the last word of the long text finds it")
                got = p.js(f"(() => {{ const b = document.querySelector('{q} .rce-opts button'); return {{ id: b.dataset.pick, text: b.textContent, over: b.scrollWidth > b.clientWidth + 1, cut: getComputedStyle(b).textOverflow === 'ellipsis' || getComputedStyle(b).whiteSpace === 'nowrap' }}; }})()")
                self.assertEqual(got["id"], big)
                self.assertTrue(got["text"].endswith(long), "the whole text is in the row at %d dark=%s: %s" % (w, dark, got["text"]))
                self.assertFalse(got["over"] or got["cut"], "the row is not cut or sideways at %d dark=%s: %s" % (w, dark, got))


class EditPeek(PageBase, Steps):
    def test_a_cards_peek_opened_in_view_is_editable_in_edit_and_an_edit_in_it_is_saved_at_both_widths(self):
        """Ticket 1270, "Edit: the Peek is editable": Edit draws the card's form, not the card, so the author opens the card's Peek in View and switches to
        Edit with it open; the Peek then has its edit controls, and a title typed in it is saved to the item."""
        ids = seed(self)
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=self.seam)
        self.addCleanup(self.s.close)
        editable = "#peek .pk-title-in, #peek [data-pk-foot-in], #peek .pk-foot-in, #peek textarea, #peek input"
        with chrome() as cdp:
            p = self.visit(cdp)
            for n, w in enumerate((1400, 900)):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.view()
                self.open_card(p, ids["risk"])
                self.assertEqual(p.js("document.querySelectorAll('#peek .pk-title-in').length"), 0, "the Peek opened from a card in View has no title box at %d" % w)
                p.edit()
                self.assertTrue(wait(lambda: shown(p)["open"] and ids["risk"] in shown(p)["text"]), "the card's Peek stays open in Edit at %d" % w)
                self.assertTrue(wait(lambda: p.js(f"document.querySelectorAll({json.dumps(editable)}).length") > 0), "the Peek has edit controls in Edit at %d" % w)
                if w == 900:
                    self.assertLessEqual(abs(p.js("document.querySelector('#peek').getBoundingClientRect().width - document.documentElement.clientWidth")), 2, "at 900 the Peek fills the window")
                new = f"Kiln roof edit {w}"
                p.js("document.querySelector('#peek .pk-title-in').click()")
                self.assertTrue(wait(lambda: p.js("!!document.querySelector('#peek textarea.pk-title-in')")), "the title opens for editing at %d" % w)
                p.js(f"(() => {{ const t = document.querySelector('#peek textarea.pk-title-in'); t.value = {json.dumps(new)}; t.dispatchEvent(new Event('input', {{bubbles: true}})); t.blur(); }})()")
                self.assertTrue(wait(lambda: next(r for r in self.store.read("raid", "ABC") if r["id"] == ids["risk"])["description"] == new), "the edit made in the card's Peek is saved at %d" % w)
                p.js(ESC_KEY)
                self.assertTrue(wait(lambda: not shown(p)["open"]), "Esc closes it at %d" % w)
