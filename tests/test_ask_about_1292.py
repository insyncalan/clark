"""Row 1292 (reopened): Ask about this (the sparkle and its chip) and the answer's sources (numbered citations, the Used line, the read line).

Run: python3 dev/run_tests.py test_ask_about_1292
Classic only: the sparkle is drawn only when the Theme layer is on; Cards (no Theme layer) is proved to have none. Chrome at 1400 and 900 px, fictional demo data.
The server's `ask` is the stub of test_ask_panel, told to answer with items and a read count, so the page's own drawing is what is read.
"""
import json
import unittest

from clark import page
import test_ask_panel as AP
import _testpage as testpage
from test_report_editor import Base, Pg, tearDownModule  # noqa: F401
from test_tpl_workitems import plant
from clark import changes
from test_server import chrome
from _demo import USER

SPARKLES = "document.querySelectorAll('[data-ask-about]').length"


class Counting(AP.Stub):
    """A stub whose answer names items and says what it read."""

    def __init__(self):
        super().__init__()
        self.items = []
        self.read = None

    def ask(self, body):
        status, got = super().ask(body)
        if got.get("ok"):
            got["items"] = [{"id": i, "state": []} for i in self.items]
            if self.read:
                got["read"] = self.read
        return status, got


class Classic(Base):
    theme = "prototype-2.0"

    def setUp(self):
        super().setUp()
        self.stub = Counting()
        plant(self)
        self.again(self.theme)
        self.ref = self.add({"mode": "all", "owner": ["Pat Demo", "Lee Demo", "Sam Demo", "Kim Demo"]})

    def add(self, value):
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.NEW, "values": {"type": "workitems", "title": "Due soon"}, "after": None})
        self.assertEqual(status, 200, got)
        status, _ = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.UPDATE, "id": got["ref"], "changes": {"body": json.dumps(value)}})
        self.assertEqual(status, 200)
        return got["ref"]

    def ask(self, p, text):
        p.js("document.querySelector('#ask-box').focus()")
        p.type(text)
        p.js("document.querySelector('#ask-send').click()")

    def again(self, theme):
        self.s.close()
        from _real_server import real_server
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.page_html(branding=page.NO_BRAND, theme=theme) if theme else testpage.html(), seam=self.seam)
        self.addCleanup(self.s.close)
        self.s.httpd.ask = self.stub

    def edit_ready(self, cdp, width=1400):
        p = self.visit(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.edit()
        p.until(f"{SPARKLES} > 0", "the sparkles are drawn in Edit")
        return p


class AskAbout(Classic):
    def test_edit_has_a_sparkle_on_each_section_and_each_work_item_and_view_has_none(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(SPARKLES), 0, "View has no sparkle (nothing about ask clark reaches a client)")
            p.edit()
            p.until(f"{SPARKLES} > 0", "drawn in Edit")
            self.assertEqual(p.js("document.querySelectorAll('.sec-head [data-ask-about]').length"), p.js("document.querySelectorAll('.secs > .sec').length"))
            self.assertEqual(p.js("document.querySelectorAll('.wil-table tr[data-id] [data-ask-about]').length"), p.js("document.querySelectorAll('.wil-table tr[data-id]').length"))
            self.assertGreater(p.js("document.querySelectorAll('.wil-table tr[data-id] [data-ask-about]').length"), 0)
            p.view()
            self.assertEqual(p.js(SPARKLES), 0, "back in View the sparkles are gone")

    def test_the_sparkle_is_at_the_right_end_of_a_work_item_row(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit_ready(cdp, width)
                self.assertTrue(p.js("""(() => { const r = document.querySelector('.wil-table tr[data-id]'); const s = r.querySelector('[data-ask-about]').getBoundingClientRect();
                  const t = r.querySelector('.wil-c-title').getBoundingClientRect(); return s.left > t.right - 1 && s.width >= 24 && s.height >= 24; })()"""), "right of the title, a target of 24 px or more")

    def test_the_sparkle_says_the_approved_words_in_its_tooltip_and_its_label(self):
        """Row 1292 (NEW-WORDS L1491 tooltip, L1500 aria label): a capital A, 'clark' lower case; the label names the row's id and title."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit_ready(cdp, width)
                got = p.js("""(() => { const r = document.querySelector('.wil-table tr[data-id]'); const b = r.querySelector('[data-ask-about]');
                  const s = document.querySelector('.sec-head [data-ask-about]');
                  return [b.getAttribute('title'), b.getAttribute('aria-label'), r.dataset.id, s.getAttribute('title'), s.getAttribute('aria-label')]; })()""")
                self.assertEqual(got[0], "Ask clark about this")
                self.assertEqual(got[3], "Ask clark about this")
                self.assertTrue(got[1].startswith("Ask clark about ") and got[1][len("Ask clark about "):].startswith(got[2]), got)
                self.assertTrue(got[4].startswith("Ask clark about ") and len(got[4]) > len("Ask clark about "), got)

    def test_a_sparkle_opens_the_panel_with_a_chip_and_suggestions_about_it(self):
        with chrome() as cdp:
            p = self.edit_ready(cdp)
            p.js("document.querySelector('.wil-table tr[data-id] [data-ask-about]').click()")
            p.until("!!document.querySelector('#ask-panel') && !!document.querySelector('#ask-chip')", "the panel opened with a chip")
            self.assertTrue(p.js("document.querySelector('#ask-chip').textContent.trim().startsWith('About ')"))
            p.until("document.querySelectorAll('#ask-pills button').length > 0", "the panel's read of the project's own asking switch finished and the suggestions are drawn")
            pills = p.js("[...document.querySelectorAll('#ask-pills button')].map(b => b.textContent)")
            self.assertEqual(pills, ["Is it late?", "Who owns it?", "What is it needed for?", "Draft an update", "Move it a week"])
            p.js("document.querySelector('#ask-chip-x').click()")
            p.until("document.querySelector('#ask-chip') === null", "the chip is removed")
            self.assertTrue(p.js("!!document.querySelector('#ask-panel')"), "the panel stays open")
            self.assertNotIn("Is it late?", p.js("[...document.querySelectorAll('#ask-pills button')].map(b => b.textContent)"))

    def test_the_subject_goes_with_the_question_and_the_chat_shows_only_the_words(self):
        with chrome() as cdp:
            p = self.edit_ready(cdp)
            ident = p.js("document.querySelector('.wil-table tr[data-id] [data-ask-about]').getAttribute('data-ask-about')")
            p.js("document.querySelector('.wil-table tr[data-id] [data-ask-about]').click()")
            p.until("!document.querySelector('#ask-send').disabled", "ready")
            self.ask(p, "Who owns it?")
            p.until("document.querySelectorAll('.ask-turn').length >= 2", "answered")
            q = [b for c, b in self.stub.calls if c == "ask"][-1]["question"]
            self.assertIn(ident, q)
            self.assertTrue(q.endswith("Who owns it?"), q)
            self.assertEqual(p.js("document.querySelector('.ask-turn.user .ask-text').textContent"), "Who owns it?")

    def test_a_new_chat_drops_the_chip_and_a_question_without_it_goes_as_typed(self):
        with chrome() as cdp:
            p = self.edit_ready(cdp)
            p.js("document.querySelector('.sec-head [data-ask-about]').click()")
            p.until("!!document.querySelector('#ask-chip')", "chip")
            p.until("!document.querySelector('#ask-send').disabled", "ready")
            p.js("document.querySelector('#ask-new').click()")
            p.until("document.querySelector('#ask-chip') === null", "a new chat has no chip")
            self.ask(p, "Plain one")
            p.until("document.querySelectorAll('.ask-turn').length >= 2", "answered")
            self.assertEqual([b for c, b in self.stub.calls if c == "ask"][-1]["question"], "Plain one")

    def test_the_chip_is_cleared_when_the_project_changes(self):
        with self.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
        with chrome() as cdp:
            p = self.edit_ready(cdp)
            p.js("document.querySelector('.sec-head [data-ask-about]').click()")
            p.until("!!document.querySelector('#ask-chip')", "chip")
            p.js("location.hash = '#dashboard&p=XYZ'")
            p.until("document.querySelector('#ask-chip') === null", "a chip about one project does not follow the person into another")

    def test_the_chip_stays_while_the_project_does_not_change(self):
        with chrome() as cdp:
            p = self.edit_ready(cdp)
            p.js("document.querySelector('.sec-head [data-ask-about]').click()")
            p.until("!!document.querySelector('#ask-chip')", "chip")
            p.js("location.hash = '#work&p=ABC&f=mode:all'")
            p.until("!!document.querySelector('#work table.items tr[data-id]')", "the next page")
            self.assertTrue(p.js("!!document.querySelector('#ask-chip')"), "the same project keeps the chip")

    def test_a_chip_made_in_another_project_stays_in_that_project(self):
        with self.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
        status, got = self.real_change({"project": "XYZ", "kind": "report_sections", "op": changes.NEW, "values": {"type": "workitems", "title": "Other list"}, "after": None})
        self.assertEqual(status, 200, got)
        with chrome() as cdp:
            p = self.visit(cdp, "#dashboard&p=XYZ")
            p.edit()
            p.until(f"{SPARKLES} > 0", "drawn in Edit")
            p.js("document.querySelector('[data-ask-about]').click()")
            p.until("!!document.querySelector('#ask-chip')", "chip")
            p.until("!document.querySelector('#ask-send').disabled", "ready")
            self.assertTrue(p.js("!!document.querySelector('#ask-chip')"), "a chip made in this project stays in it")

    def test_a_use_case_row_has_a_sparkle(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port, "#usecases&p=ABC")
            p.until("document.querySelectorAll('tr.ucr[data-uc]').length > 0", "use case rows")
            p.until(f"{SPARKLES} > 0", "drawn (the page is always editable)")
            self.assertEqual(p.js("document.querySelectorAll('tr.ucr[data-uc] [data-ask-about]').length"), p.js("document.querySelectorAll('tr.ucr[data-uc]').length"))
            self.assertEqual(p.js("document.querySelector('tr.ucr[data-uc] [data-ask-about]').getAttribute('data-ask-about')"), p.js("document.querySelector('tr.ucr[data-uc]').dataset.uc"))

    def test_a_board_card_has_a_sparkle(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port, "#work&p=ABC&f=mode:all")
            p.until("document.querySelectorAll('#work table.items tr[data-id]').length > 0", "rows")
            p.js("(() => { const b = [...document.querySelectorAll('#work [role=tab], #work button')].find(e => /board/i.test(e.getAttribute('aria-label') || e.textContent)); if (b) b.click(); })()")
            p.until("document.querySelectorAll('.bc-top').length > 0", "cards")
            self.assertEqual(p.js("document.querySelectorAll('.bc-top [data-ask-about]').length"), p.js("document.querySelectorAll('.bc-top').length"))

    def test_a_list_row_in_edit_has_a_sparkle_and_view_has_none(self):
        for kind, title in (("raid", "Risks and issues"), ("actions", "Open actions"), ("decisions", "Decisions")):
            status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.NEW, "values": {"type": kind, "title": title}, "after": None})
            self.assertEqual(status, 200, got)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertGreater(p.js("document.querySelectorAll('.wl-row').length"), 0, "the report has list rows")
            self.assertEqual(p.js("document.querySelectorAll('.wl-row [data-ask-about]').length"), 0, "View has none")
            p.edit()
            p.until("document.querySelectorAll('.wl-row [data-ask-about]').length > 0", "a sparkle in Edit")
            self.assertEqual(p.js("document.querySelectorAll('.wl-row [data-ask-about]').length"), p.js("document.querySelectorAll('.wl-row').length"))

    def test_the_work_items_page_has_a_sparkle_on_every_row(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port, "#work&p=ABC&f=mode:all")
            p.until("document.querySelectorAll('#work table.items tr[data-id]').length > 0", "rows")
            p.until(f"{SPARKLES} > 0", "drawn (the page is always editable)")
            self.assertEqual(p.js("document.querySelectorAll('#work table.items tr[data-id] [data-ask-about]').length"), p.js("document.querySelectorAll('#work table.items tr[data-id]').length"))
            self.assertTrue(p.js("(() => { const r = document.querySelector('#work table.items tr[data-id]'); return r.querySelector('[data-ask-about]').getBoundingClientRect().left >= r.querySelector('.c-item').getBoundingClientRect().right; })()"), "at the right of the row")

    def test_cards_has_no_sparkle(self):
        self.again(None)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until("document.querySelectorAll('.wil-table tr[data-id]').length > 0", "rows")
            self.assertEqual(p.js(SPARKLES), 0, "Cards is left as it was")


class Sources(Classic):
    def item_id(self, p):
        return p.js("document.querySelector('.wil-table tr[data-id]').dataset.id")

    def test_a_named_item_gets_a_numbered_chip_and_the_used_line_lists_it(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            ident = self.item_id(p)
            self.stub.answer = f"{ident} is late. Ask about {ident} again."
            self.stub.items = [ident]
            self.stub.read = {"work_items": 17, "milestones": 6, "use_cases": 8, "as_at": "17-11-2026"}
            p.key("/", code="Slash", vk=191)
            p.until("!document.querySelector('#ask-send') || !document.querySelector('#ask-send').disabled", "ready")
            self.ask(p, "What is late?")
            p.until("document.querySelectorAll('.ask-cite').length > 0", "a chip drew")
            self.assertEqual(p.js("document.querySelectorAll('.ask-cite').length"), 2, "one after each mention")
            self.assertEqual(p.js("[...new Set([...document.querySelectorAll('.ask-cite')].map(b => b.textContent.trim()))]"), ["1"])
            self.assertEqual(p.js("document.querySelector('.ask-cite').getAttribute('aria-label')"), f"Source 1: open {ident}")
            self.assertEqual(p.js("document.querySelector('[data-ask-used]').textContent.replace(/\\s+/g, ' ').trim()"), f"Used: 1 {ident}")
            self.assertEqual(p.js("document.querySelector('[data-ask-read]').textContent.trim()"), "17 work items, 6 milestones and 8 use cases read · as at 17-11-2026")

    def test_an_id_the_answer_does_not_name_gets_no_chip_and_no_used_line(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            ident = self.item_id(p)
            self.stub.answer = f"Nothing to say about {ident}."
            self.stub.items = []
            p.key("/", code="Slash", vk=191)
            p.until("!document.querySelector('#ask-send') || !document.querySelector('#ask-send').disabled", "ready")
            self.ask(p, "Anything?")
            p.until("document.querySelectorAll('.ask-turn').length >= 2", "answered")
            self.assertEqual(p.js("document.querySelectorAll('.ask-cite').length"), 0)
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-used], [data-ask-read]').length"), 0)

    def test_a_chip_opens_the_item_beside_the_panel_not_behind_it(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.edit()
                ident = self.item_id(p)
                self.stub.answer = f"{ident} is late."
                self.stub.items = [ident]
                p.key("/", code="Slash", vk=191)
                p.until("!document.querySelector('#ask-send') || !document.querySelector('#ask-send').disabled", "ready")
                self.ask(p, "What is late?")
                p.until("document.querySelectorAll('.ask-cite').length > 0", "chip")
                p.js("document.querySelector('.ask-cite').click()")
                p.until("!!document.querySelector('.peek')", "the peek opened")
                self.assertTrue(p.js(f"location.hash.includes({json.dumps(ident)})"))
                p.until("document.querySelector('.peek').getBoundingClientRect().right <= document.querySelector('#ask-panel').getBoundingClientRect().left + 1", "the peek is left of the panel")
                self.assertTrue(p.js("!!document.querySelector('#ask-panel')"), "the panel stays open")

    def test_the_used_chip_opens_the_item_too_and_has_a_name(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            ident = self.item_id(p)
            self.stub.answer = f"{ident} is late."
            self.stub.items = [ident]
            p.key("/", code="Slash", vk=191)
            p.until("!document.querySelector('#ask-send') || !document.querySelector('#ask-send').disabled", "ready")
            self.ask(p, "What is late?")
            p.until("!!document.querySelector('[data-ask-used] button')", "used chip")
            self.assertIn(ident, p.js("document.querySelector('[data-ask-used] button').getAttribute('aria-label')"))
            p.js("document.querySelector('[data-ask-used] button').click()")
            p.until("!!document.querySelector('.peek')", "peek")

    def test_a_reopened_chat_keeps_its_chips_used_line_read_line_and_about_line(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            ident = self.item_id(p)
            self.stub.answer = f"{ident} is late."
            self.stub.items = [ident]
            self.stub.read = {"work_items": 17, "milestones": 6, "use_cases": 8, "as_at": "17-11-2026"}
            p.js("document.querySelector('.wil-table tr[data-id] [data-ask-about]').click()")
            p.until("!document.querySelector('#ask-send').disabled", "ready")
            self.ask(p, "Is it late?")
            p.until("document.querySelectorAll('.ask-cite').length > 0 && !!document.querySelector('.ask-about-line')", "answered")
            p.until("!!document.querySelector('#ask-new') && !document.querySelector('#ask-new').disabled", "idle")
            p.js("document.querySelector('#ask-new').click()")
            p.until("document.querySelectorAll('.ask-turn').length === 0", "a new chat")
            p.js("document.querySelector('#ask-history').click()")
            p.until("!!document.querySelector('.ask-hist-open')", "history open")
            p.js("document.querySelector('.ask-hist-open').click()")
            p.until("document.querySelectorAll('.ask-turn').length >= 2", "the chat is back")
            self.assertGreater(p.js("document.querySelectorAll('.ask-cite').length"), 0, "the citation chips are back")
            self.assertEqual(p.js("document.querySelector('[data-ask-used]').textContent.replace(/\\s+/g, ' ').trim()"), f"Used: 1 {ident}")
            self.assertEqual(p.js("document.querySelector('[data-ask-read]').textContent.trim()"), "17 work items, 6 milestones and 8 use cases read · as at 17-11-2026")
            self.assertTrue(p.js("!!document.querySelector('.ask-about-line')"), "the About line is back")

    def test_cards_draws_no_citation_chips_used_line_or_read_line(self):
        self.again(None)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            ident = self.item_id(p)
            self.stub.answer = f"{ident} is late."
            self.stub.items = [ident]
            self.stub.read = {"work_items": 17, "milestones": 6, "use_cases": 8, "as_at": "17-11-2026"}
            p.key("/", code="Slash", vk=191)
            p.until("!document.querySelector('#ask-send') || !document.querySelector('#ask-send').disabled", "ready")
            self.ask(p, "What is late?")
            p.until("document.querySelectorAll('.ask-turn').length >= 2", "answered")
            self.assertEqual(p.js("document.querySelectorAll('.ask-cite, [data-ask-used], [data-ask-read]').length"), 0, "Cards is left as it was")

    def test_the_peek_goes_back_to_the_edge_when_the_panel_is_closed(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            ident = self.item_id(p)
            self.stub.answer = f"{ident} is late."
            self.stub.items = [ident]
            p.key("/", code="Slash", vk=191)
            p.until("!document.querySelector('#ask-send') || !document.querySelector('#ask-send').disabled", "ready")
            self.ask(p, "What is late?")
            p.until("document.querySelectorAll('.ask-cite').length > 0", "chip")
            p.js("document.querySelector('.ask-cite').click()")
            p.until("!!document.querySelector('.peek')", "peek")
            p.js("document.querySelector('#ask-close').click()")
            p.until("document.querySelector('#ask-panel') === null", "closed")
            p.until("Math.round(document.documentElement.clientWidth - document.querySelector('.peek').getBoundingClientRect().right) === 0", "the peek is at the edge again")


if __name__ == "__main__":
    unittest.main()
