"""The peek's Latest update with Draft and the 'Last updated' stamp, and the overdue and weekend warning bar (v0.9 prototype parity).
Run: python3 dev/run_tests.py test_peek_latest

Part 1 is clark/changes.py: an action's latest_update is one more field of the work-item change (plain text, line breaks allowed, 1000
characters at most, blank clears it), one step and one Undo, and a risk or a decision has none. Part 2 is the source and the built page.
Part 3 is the page in a real browser at 1400 and 900 px in Edit: Draft, the box, the stamp, Move to Friday, Move a week on and the
weekend bar's two moves, each one request and one Undo; View has none of it.
"""
import json
import unittest
from datetime import datetime, timezone

from _paths import ROOT
import _testpage as testpage

from clark import changes, sneak  # noqa: E402
from test_peek import key  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402
from test_work_filters import click  # noqa: E402

OVERDUE, WEEKEND = "TUL-A-002", "TUL-A-006"       # demo data at 28-10-2026 (a Wednesday): due 22-10-2026, and Saturday 07-11-2026


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.code = next(iter(cls.ids))
        cls.change = staticmethod(changes.make_change(cls.store.path, [], "Demo User"))
        cls.undo = staticmethod(changes.make_undo(cls.store.path, [], "Demo User"))

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def latest(self, ref=OVERDUE):
        return next(a for a in self.store.data_for(self.code)["actions"] if a["id"] == ref)["latest_update"]

    def send(self, text, kind="actions", ref=OVERDUE):
        return self.change({"project": self.code, "kind": kind, "op": "update", "id": ref, "changes": {"latest_update": text}, "place": "peek"})

    def test_a_latest_update_is_saved_with_a_line_break_and_undone_in_one_step(self):
        was = self.latest()
        code, body = self.send("Venue confirmed.\nContract next.")
        self.assertEqual((code, body["ok"], body["undoable"]), (200, True, True), body)
        self.assertEqual(body["item"]["latest_update"], "Venue confirmed.\nContract next.")
        self.assertEqual(self.latest(), "Venue confirmed.\nContract next.")
        code, body2 = self.undo({"project": self.code, "apply_id": body["apply_id"]})
        self.assertEqual(code, 200, body2)
        self.assertEqual(self.latest(), was, "one Undo puts the old text back")

    def test_a_blank_latest_update_clears_it_and_undo_brings_it_back(self):
        was = self.latest()
        code, body = self.send("   ")
        self.assertEqual(code, 200, body)
        self.assertIsNone(self.latest())
        self.undo({"project": self.code, "apply_id": body["apply_id"]})
        self.assertEqual(self.latest(), was)

    def test_too_long_or_hidden_characters_are_refused_and_nothing_is_written(self):
        was = self.latest()
        for text in ("x" * (changes.LATEST_UPDATE_MAX + 1), "a​b", "a\x00b", "a‮b", 5):
            code, body = self.send(text)
            self.assertEqual((code, body["ok"]), (400, False), repr(text)[:20])
        self.assertEqual(self.latest(), was)
        self.assertEqual(self.send("x" * changes.LATEST_UPDATE_MAX)[0], 200, "the limit itself is allowed")

    def test_a_risk_or_a_decision_has_no_latest_update(self):
        data = self.store.data_for(self.code)
        for kind, ref in (("raid", data["raid"][0]["id"]), ("decisions", data["decisions"][0]["id"])):
            code, body = self.send("Anything", kind, ref)
            self.assertEqual((code, body["ok"]), (400, False), kind)

    def test_the_undo_words_never_repeat_the_text(self):
        entry = {"field": "latest_update", "to": "A secret sentence", "ref": OVERDUE}
        words = changes._field_words(entry, OVERDUE)
        self.assertIn("latest update", words)
        self.assertNotIn("secret", words)


class Source(unittest.TestCase):
    LINES = ("Latest update", "Draft", "Last updated", "Move to Friday", "Move a week on", "Move to Monday", "a working day is usually meant",
             "Latest update drafted from the item's own fields.")

    def test_each_line_is_in_the_source_and_the_edit_page_and_not_in_a_published_file(self):
        src = "".join((ROOT / "src/clark/page/src/edit" / f).read_text(encoding="utf-8") for f in ("PeekLatest.jsx", "peekLatest.js"))
        built = (ROOT / "src/clark/page/page.html").read_text(encoding="utf-8")
        view = (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8")
        for line in self.LINES:
            self.assertIn(line, src, line)
            self.assertIn(line, built, line)
        for line in ("Move a week on", "Last updated", "Latest update drafted", "pk-warnbar"):
            self.assertNotIn(line, view, "the published page carries none of it: " + line)

    def test_the_peek_hands_both_parts_to_edit_only(self):
        peek = (ROOT / "src/clark/page/src/components/Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("editing && forItem && tools.PeekWarn", peek)
        self.assertIn("editing && forItem && tools.PeekLatest", peek)
        self.assertNotIn("edit/", peek.replace("tools.", ""), "Peek.jsx imports nothing from edit/")


class Browser(unittest.TestCase):
    def fresh(self):
        """A fresh demo database: a move or a draft at one width never reaches the next width or test."""
        self.store, folder, self.ids = load_demo()
        self.code = next(iter(self.ids))
        self.data = self.store.data_for(self.code)

        def cleanup(store=self.store):
            store.close()
            import shutil
            shutil.rmtree(str(folder), ignore_errors=True)
        self.addCleanup(cleanup)

    def setUp(self):
        self.fresh()

    def action(self, ref):
        return next(a for a in self.data["actions"] if a["id"] == ref)

    def load(self, cdp, width, item, edit=True):
        self.fresh()
        sent = []
        real = changes.make_change(self.store.path, [], "Demo User")
        s = Running(data_for=self.store.data_for, projects=lambda: self.store.read("projects"), page_html=lambda: testpage.html(),
                    sneak=sneak.make_read(self.store.data_for), change=lambda req: (sent.append(req), real(req))[1],
                    undo=changes.make_undo(self.store.path, [], "Demo User"))
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#work&p={self.code}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0))
        if edit:
            cdp.js("document.querySelector('[data-view=dashboard]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-mode=edit]')", sid)))
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            cdp.js("document.querySelector('[data-view=work]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0))
        cdp.js(f"clarkPage.openPeek({json.dumps(item)})", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek dt')", sid)))
        return sent, sid

    def due(self, cdp, sid):
        return cdp.js("(d => d ? d.textContent.replace('Changed', '').trim() : '')(document.querySelector('#peek [data-row=due] dd'))", sid)

    def toast(self, cdp, sid):
        return cdp.js("(document.querySelector('.toast') || {textContent: ''}).textContent", sid)

    def inside(self, cdp, sid, selector):
        return cdp.js(f"(c => {{ const r = c.getBoundingClientRect(), p = document.querySelector('#peek').getBoundingClientRect(); return r.left >= p.left - 1 && r.right <= p.right + 1; }})(document.querySelector({json.dumps(selector)}))", sid)

    def test_the_overdue_bar_says_how_late_and_moves_to_friday_with_one_undo(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.assertEqual(cdp.js("document.querySelector('[data-pk-warn]').dataset.pkWarn", sid), "overdue")
                self.assertIn("6 days overdue (due 22-10-2026)", cdp.js("document.querySelector('[data-pk-warn]').textContent", sid))
                self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pk-move]')].map(b => b.textContent)", sid), ["Move to Friday 30-10-2026", "Move a week on"])
                self.assertTrue(self.inside(cdp, sid, ".pk-warnbar") and self.inside(cdp, sid, "[data-pk-move]:last-child"), "the bar fits the peek")
                before = self.due(cdp, sid)
                click(cdp, sid, "[data-pk-move='2026-10-30']")
                self.assertTrue(wait(lambda: self.due(cdp, sid).startswith("30-10-2026")), "the date moved")
                self.assertEqual(len(sent), 1, "one move is one request")
                self.assertEqual((sent[0]["kind"], sent[0]["id"], sent[0]["changes"]), ("actions", OVERDUE, {"due_date": "2026-10-30"}))
                self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[data-pk-warn]')", sid)), "no longer overdue: the bar goes")
                self.assertIn(f"{OVERDUE} moved to 30-10-2026.", self.toast(cdp, sid))
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: self.due(cdp, sid) == before), "one Undo puts the date back")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-warn]')", sid)), "and the bar returns")

    def test_move_a_week_on_goes_a_week_from_today(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                click(cdp, sid, "[data-pk-move='2026-11-04']")
                self.assertTrue(wait(lambda: self.due(cdp, sid).startswith("04-11-2026")))
                self.assertEqual((len(sent), sent[0]["changes"]), (1, {"due_date": "2026-11-04"}))

    def test_the_weekend_bar_offers_the_friday_before_and_the_monday_after(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, WEEKEND)
                self.assertEqual(cdp.js("document.querySelector('[data-pk-warn]').dataset.pkWarn", sid), "weekend")
                self.assertIn("Due on a Saturday (07-11-2026): a working day is usually meant", cdp.js("document.querySelector('[data-pk-warn]').textContent", sid))
                self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pk-move]')].map(b => b.textContent)", sid), ["Move to Friday 06-11-2026", "Move to Monday 09-11-2026"])
                before = self.due(cdp, sid)
                click(cdp, sid, "[data-pk-move='2026-11-09']")
                self.assertTrue(wait(lambda: self.due(cdp, sid).startswith("09-11-2026")))
                self.assertEqual((len(sent), sent[0]["changes"]), (1, {"due_date": "2026-11-09"}))
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: self.due(cdp, sid) == before))

    def test_an_item_that_is_not_late_or_on_a_weekend_has_no_bar(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, "TUL-A-001")                    # due Monday 02-11-2026
            self.assertFalse(cdp.js("!!document.querySelector('[data-pk-warn]')", sid))

    def test_draft_writes_the_update_from_the_items_fields_with_one_undo(self):
        a = self.action(OVERDUE)
        ms = next(m for m in self.data["milestones"] if m["id"] == a["milestone"])
        name = ms["name"][0].lower() + ms["name"][1:]
        d, y, m = ms["baseline_date"][8:], ms["baseline_date"][:4], ms["baseline_date"][5:7]
        want = f"Overdue since 22-10-2026. {a['owner']} is working on it. Needed for {name} on {d}-{m}-{y}."
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.assertIn(a["latest_update"], cdp.js("document.querySelector('[data-pk-latest-text]').textContent", sid))
                self.assertTrue(self.inside(cdp, sid, "[data-pk-draft]"))
                click(cdp, sid, "[data-pk-draft]")
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-pk-latest-text]').textContent", sid) == want))
                self.assertEqual((len(sent), sent[0]["changes"]), (1, {"latest_update": want}), "one request, no AI call")
                self.assertIn("Latest update drafted from the item's own fields.", self.toast(cdp, sid))
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-pk-latest-text]').textContent", sid) == a["latest_update"]))

    def test_the_box_saves_on_enter_and_leaves_the_text_on_escape(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                click(cdp, sid, "[data-pk-latest-text]")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-latest-in')", sid)), "focus is in the box")
                cdp.js("(t => { t.value = 'Typed and abandoned'; t.dispatchEvent(new Event('input', {bubbles: true})); })(document.activeElement)", sid)
                key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-latest-text]')", sid)), "Esc closes the box only")
                self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "the peek stays")
                self.assertEqual(sent, [], "nothing was sent")
                click(cdp, sid, "[data-pk-latest-text]")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-latest-in')", sid)))
                cdp.js("(t => { t.value = 'Brand new words'; t.dispatchEvent(new Event('input', {bubbles: true})); })(document.activeElement)", sid)
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: cdp.js("(document.querySelector('[data-pk-latest-text]') || {textContent: ''}).textContent", sid) == "Brand new words"))
                self.assertEqual((len(sent), sent[0]["changes"]), (1, {"latest_update": "Brand new words"}))

    def test_a_too_long_update_is_refused_in_words_and_the_box_stays(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            click(cdp, sid, "[data-pk-latest-text]")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-latest-in')", sid)))
            cdp.js("(t => { t.value = 'x'.repeat(1001); t.dispatchEvent(new Event('input', {bubbles: true})); })(document.activeElement)", sid)
            key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: "1000 characters at most" in cdp.js("(document.querySelector('[data-pk-latest-err]') || {textContent: ''}).textContent", sid)))
            self.assertEqual(sent, [])
            self.assertTrue(cdp.js("!!document.querySelector('[data-pk-latest-in]')", sid), "the box keeps what was typed")

    def test_the_last_updated_stamp_is_shown_in_local_time_and_follows_a_change(self):
        a = self.action(OVERDUE)
        utc = datetime.strptime(a["updated_at"][:16], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).astimezone()
        want = "Last updated " + utc.strftime("%d-%m-%Y %H:%M")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                got = lambda: cdp.js("(e => e ? e.textContent.trim() : '')(document.querySelector('[data-pk-last]'))", sid)
                self.assertEqual(got(), want)
                self.assertTrue(self.inside(cdp, sid, "[data-pk-last]"))
                click(cdp, sid, "[data-pk-draft]")
                self.assertTrue(wait(lambda: got() != want), "the stamp is the one clark wrote")

    def test_a_risk_shows_the_stamp_but_no_latest_update(self):
        risk = self.data["raid"][0]["id"]
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, risk)
            self.assertTrue(cdp.js("!!document.querySelector('[data-pk-last]')", sid))
            self.assertFalse(cdp.js("!!document.querySelector('[data-pk-draft],[data-pk-latest-text]')", sid))

    def test_view_has_none_of_it(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE, edit=False)
                self.assertFalse(cdp.js("!!document.querySelector('[data-pk-warn],[data-pk-draft],[data-pk-latest],[data-pk-last]')", sid))


if __name__ == "__main__":
    unittest.main()
