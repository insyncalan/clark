"""Row 1292 bundle B: killers for the survivors of the change-card sweep in AskChange.jsx (kept apart from test_ask_change_page).

Run: python3 dev/run_tests.py test_ask_change_page_killers
Covers: Undo all is not offered when one saved change cannot be undone, Undo all sends one request for both steps, a milestone card links to the
milestone. Fictional data only.
"""
import json

from test_ask_change_page import Card
from test_server import chrome

SECOND_NOT_UNDOABLE = """(() => {
  const real = window.fetch; let n = 0;
  window.fetch = async (url, init) => {
    const r = await real(url, init);
    if (!String(url).includes('/api/ask/change/apply') || ++n !== 2) return r;
    const b = await r.json();
    return new Response(JSON.stringify({ ...b, undoable: false }), { status: r.status, headers: { 'Content-Type': 'application/json' } });
  };
})()"""

RECORD_UNDOS = """(() => {
  const real = window.fetch; window.__undos = [];
  window.fetch = (url, init) => {
    if (String(url).includes('/api/undo')) window.__undos.push(JSON.parse(init.body));
    return real(url, init);
  };
})()"""


class Killers(Card):
    def test_undo_all_is_not_offered_when_one_saved_change_cannot_be_undone(self):
        second = self.demo.action(owner="Kim Roe", description="Order the badges", client_visible=0)
        self.says(self.close_it(), "CHANGE: " + json.dumps({"op": "change", "id": second, "current_title": "Order the badges", "status": "Closed"}))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "both cards")
            p.js(SECOND_NOT_UNDOABLE)
            p.js("document.querySelector('[data-ask-apply-all]').click()")
            p.until("!!document.querySelector('[data-ask-group-line]')", "the group line")
            self.assertEqual((self.status(), self.store.read("actions", ref=second)["status"]), ("Closed", "Closed"))
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-undo-all]').length"), 0, "one step cannot be undone: no Undo all")

    def test_undo_all_is_one_undo_request_for_both_steps(self):
        second = self.demo.action(owner="Kim Roe", description="Order the badges", client_visible=0)
        self.says(self.close_it(), "CHANGE: " + json.dumps({"op": "change", "id": second, "current_title": "Order the badges", "status": "Closed"}))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 2", "both cards")
            p.js(RECORD_UNDOS)
            p.js("document.querySelector('[data-ask-apply-all]').click()")
            p.until("!!document.querySelector('[data-ask-undo-all]')", "done with one Undo")
            p.js("document.querySelector('[data-ask-undo-all]').click()")
            p.until("document.querySelector('[data-ask-group-line]').textContent === 'Undone. The old values are back.'", "Undone")
            sent = json.loads(p.js("JSON.stringify(window.__undos)"))
            self.assertEqual(len(sent), 1, "one undo request for the lot")
            self.assertEqual(len(sent[0]["steps"]), 2)
            self.assertEqual(self.status(), "Open")

    def test_a_milestone_card_links_to_the_milestone(self):
        ref = self.demo.milestone
        self.says("CHANGE: " + json.dumps({"op": "change", "id": ref, "current_title": "Pilot live", "forecast_date": "2030-04-01"}))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            href = p.js("document.querySelector('[data-ask-change] a[data-ask-item]') && document.querySelector('[data-ask-change] a[data-ask-item]').getAttribute('href')")
            self.assertTrue(href and href.startswith("#milestones&p=") and href.endswith("&ms=" + ref), href)
