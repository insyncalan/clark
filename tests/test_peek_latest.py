"""The peek's Latest update with Draft and the 'Last updated' stamp, and the overdue and weekend warning bar (v0.9 prototype parity).
Run: python3 dev/run_tests.py test_peek_latest

Part 1 is clark/changes.py: an action's latest_update is one more field of the work-item change (plain text, line breaks allowed, 1000
characters at most, blank clears it), one step and one Undo, and a risk or a decision has none. Part 2 is the source and the built page.
Part 3 is the page in a real browser at 1400 and 900 px in Edit: Draft, the box, the stamp, Move to Friday, Move a week on and the
weekend bar's two moves, each one request and one Undo; View has none of it. In dark, at both widths, the box, its stamp, the overdue bar
and Draft are drawn with the dark tokens and each line of text reads at 4.5:1 or more on what it is drawn over.
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
        for text in ("x" * (changes.LATEST_UPDATE_MAX + 1), "a​b", "a\x00b", "a‮b", "a\tb", "a\rb", "a\ud800b", 5, False, True, ["x"], {"a": 1}):
            code, body = self.send(text)
            self.assertEqual((code, body["ok"]), (400, False), repr(text)[:20])
        self.assertEqual(self.latest(), was)
        self.assertEqual(self.send("x" * changes.LATEST_UPDATE_MAX)[0], 200, "the limit itself is allowed")

    def test_each_refusal_says_what_is_wrong_in_its_own_plain_sentence(self):
        said = lambda text: self.send(text)[1]["message"]
        self.assertEqual(said("x" * (changes.LATEST_UPDATE_MAX + 1)), changes.LATEST_LONG_WORDS)
        self.assertIn(str(changes.LATEST_UPDATE_MAX), changes.LATEST_LONG_WORDS)
        for text in ("a​b", "a\x00b", "a‮b", "a\tb", "line one\nline two\u200b"):
            self.assertEqual(said(text), changes.LATEST_HIDDEN_WORDS, repr(text))
        self.assertEqual(said(5), changes.ITEM_VALUE_WORDS)
        self.assertNotIn("line breaks", changes.LATEST_HIDDEN_WORDS, "line breaks are allowed in a latest update, so it never says to remove them")
        self.assertNotEqual(changes.LATEST_HIDDEN_WORDS, changes.ITEM_TEXT_WORDS)

    def test_a_good_owner_with_a_bad_latest_update_writes_nothing(self):
        was = next(a for a in self.store.data_for(self.code)["actions"] if a["id"] == OVERDUE)
        code, body = self.change({"project": self.code, "kind": "actions", "op": "update", "id": OVERDUE,
                                  "changes": {"owner": "Someone Else", "latest_update": "a\tb"}, "place": "peek"})
        self.assertEqual((code, body["ok"]), (400, False))
        now = next(a for a in self.store.data_for(self.code)["actions"] if a["id"] == OVERDUE)
        self.assertEqual((now["owner"], now["latest_update"]), (was["owner"], was["latest_update"]))

    def test_other_routes_do_not_take_a_latest_update(self):
        for req in ({"kind": "actions", "op": "bulk", "ids": [OVERDUE], "changes": {"latest_update": "x"}, "place": "peek"},
                    {"kind": "actions", "op": "new", "values": {"title": "Something", "latest_update": "x"}, "place": "peek"}):
            code, body = self.change({"project": self.code, **req})
            self.assertEqual((code, body["ok"]), (400, False), req["op"])
        self.assertNotIn("x", (self.latest() or ""))

    def test_the_last_updated_stamp_moves_on_with_a_change_and_with_its_undo(self):
        stamp = lambda: next(a for a in self.store.data_for(self.code)["actions"] if a["id"] == OVERDUE)["updated_at"]
        was = stamp()
        code, body = self.send("A stamp test.")
        self.assertEqual(code, 200, body)
        changed = stamp()
        self.assertGreater(changed, was, "a change writes a later stamp")
        self.undo({"project": self.code, "apply_id": body["apply_id"]})
        self.assertGreaterEqual(stamp(), changed, "the Undo is a change too: the stamp is never put back to an older time")

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

    def test_the_page_says_the_two_new_refusals_in_its_own_words(self):
        report = (ROOT / "src/clark/page/src/stores/report.js").read_text(encoding="utf-8")
        for sentence in (changes.LATEST_LONG_WORDS, changes.LATEST_HIDDEN_WORDS):
            self.assertIn(json.dumps(sentence) + ":", report, "plainChange knows the server's sentence, or the page would say 'could not be made'")

    def test_a_refusal_keeps_the_typed_text_and_the_page_checks_hidden_characters_first(self):
        edit = ROOT / "src/clark/page/src/edit"
        jsx = (edit / "PeekLatest.jsx").read_text(encoding="utf-8")
        helper = (edit / "peekLatest.js").read_text(encoding="utf-8")
        self.assertIn("\\p{Cc}", helper)
        self.assertIn('replace(/\\n/g, "")', helper, "a line break is allowed in a latest update")
        save = jsx[jsx.index("const save ="):jsx.index("const draft =")]
        self.assertLess(save.index("changeCell("), save.rindex("stop()"), "the box closes only after clark has answered")
        self.assertIn("refused:", save)
        self.assertEqual(save.count("stop()"), 2, "closed when unchanged and when saved, never before the request")

    def test_each_change_is_sent_with_its_own_place(self):
        jsx = (ROOT / "src/clark/page/src/edit/PeekLatest.jsx").read_text(encoding="utf-8")
        self.assertEqual(jsx.count('place: "peek"'), 3, "a move, a saved update and the Needed from the client switch (row 811)")
        self.assertEqual(jsx.count('place: "draft"'), 1)
        self.assertIn('done.place || "cell"', (ROOT / "src/clark/page/src/stores/changes.js").read_text(encoding="utf-8"))
        self.assertTrue({"peek", "draft"} <= set(changes.PLACES))

    def test_the_peek_hands_both_parts_to_edit_only(self):
        peek = (ROOT / "src/clark/page/src/components/Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("editing && forItem && tools.PeekWarn", peek)
        self.assertIn("editing && forItem && tools.PeekLatest", peek)
        self.assertNotIn("edit/", peek.replace("tools.", "").replace("../edit/editing.js", ""), "Peek.jsx imports nothing from edit/ but the one editing test (edit/editing.js)")


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

    HOLD = ("(() => { const st = window.setTimeout, raf = window.requestAnimationFrame; window.requestAnimationFrame = (f) => st(() => raf(f), 4000);"
            " window.setTimeout = (f, d, ...a) => st(f, d >= 20 && d <= 150 ? d + 4000 : d, ...a); })();")     # frames and Preact's effect timers arrive 4 s late

    def load(self, cdp, width, item, edit=True, dark=False, late=False):
        self.fresh()
        sent = []
        real = changes.make_change(self.store.path, [], "Demo User")
        projects = self.store.read("projects")            # read here: the store's connection belongs to this thread, and the server answers on another
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: projects, page_html=lambda: testpage.html(),
                    sneak=sneak.make_read(self.store.data_for), change=lambda req: (sent.append(req), real(req))[1],
                    undo=changes.make_undo(self.store.path, [], "Demo User"))
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        if late:
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": self.HOLD}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#work&p={self.code}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0))
        if dark:
            cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
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
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-latest-in')", sid)), "focus is in the box once it is open")
                cdp.js("(t => { t.value = 'Brand new words'; t.dispatchEvent(new Event('input', {bubbles: true})); })(document.activeElement)", sid)
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: cdp.js("(document.querySelector('[data-pk-latest-text]') || {textContent: ''}).textContent", sid) == "Brand new words"))
                self.assertEqual((len(sent), sent[0]["changes"]), (1, {"latest_update": "Brand new words"}))

    def test_pressing_draft_does_not_take_the_focus_from_the_box(self):
        """Safari and Firefox give a pressed button no focus, so the box's blur has no relatedTarget and saves the typed text before the click.
        A press on Draft is cancelled (no focus move at all), so the box keeps its focus and its blur never races the click."""
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            click(cdp, sid, "[data-pk-latest-text]")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-latest-in')", sid)), "focus is in the box")
            self.assertTrue(cdp.js("(b => { const e = new MouseEvent('mousedown', {bubbles: true, cancelable: true}); b.dispatchEvent(e); return e.defaultPrevented; })(document.querySelector('[data-pk-draft]'))", sid),
                            "the press on Draft is cancelled")
            self.assertTrue(cdp.js("document.activeElement.hasAttribute('data-pk-latest-in')", sid), "the box still has the focus")
            self.assertEqual(sent, [], "nothing was sent by the press")

    def test_the_box_has_the_focus_as_it_is_drawn_not_a_frame_later(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE, late=True)
            click(cdp, sid, "[data-pk-latest-text]")
            self.assertTrue(cdp.js("!!document.querySelector('[data-pk-latest-in]')", sid), "the click opened the box")
            self.assertTrue(cdp.js("document.activeElement.hasAttribute('data-pk-latest-in')", sid), "the box has the focus with no frame in between")

    def test_a_too_long_update_is_refused_in_words_and_the_box_stays(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            click(cdp, sid, "[data-pk-latest-text]")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-latest-in')", sid)), "focus is in the box once it is open")
            cdp.js("(t => { t.value = 'x'.repeat(1001); t.dispatchEvent(new Event('input', {bubbles: true})); })(document.activeElement)", sid)
            key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: "1000 characters at most" in cdp.js("(document.querySelector('[data-pk-latest-err]') || {textContent: ''}).textContent", sid)), "the box says the update is too long")
            self.assertEqual(sent, [])
            self.assertTrue(cdp.js("!!document.querySelector('[data-pk-latest-in]')", sid), "the box keeps what was typed")

    def test_a_hidden_character_is_refused_in_words_and_the_box_keeps_the_text(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            click(cdp, sid, "[data-pk-latest-text]")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-latest-in')", sid)), "focus is in the box once it is open")
            cdp.js("(t => { t.value = 'Pasted\\twith a tab'; t.dispatchEvent(new Event('input', {bubbles: true})); })(document.activeElement)", sid)
            key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: "hidden character" in cdp.js("(document.querySelector('[data-pk-latest-err]') || {textContent: ''}).textContent", sid)), "the box says the character is hidden")
            self.assertEqual(sent, [], "nothing was sent")
            self.assertEqual(cdp.js("(document.querySelector('[data-pk-latest-in]') || {value: null}).value", sid), "Pasted\twith a tab", "the box keeps what was typed")

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

    def kinds(self):
        """(a client-visible action, an internal action) of the demo data."""
        acts = self.data["actions"]
        return (next(a["id"] for a in acts if a.get("client_visible")), next(a["id"] for a in acts if not a.get("client_visible")))

    def test_a_client_visible_action_labels_its_latest_update_shown_to_the_client_in_edit_only(self):
        shown, internal = self.kinds()
        probe = "(l => l ? l.textContent.trim() : null)(document.querySelector('#peek [data-pk-latest] [data-pk-latest-client]'))"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, shown)
                self.assertEqual(cdp.js(probe, sid), "Shown to the client")
                self.assertTrue(self.inside(cdp, sid, "[data-pk-latest-client]"), "the label fits the peek")
                click(cdp, sid, "[data-pk-latest-text]")                                  # still there while the box is open
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-latest-in]')", sid)))
                self.assertEqual(cdp.js(probe, sid), "Shown to the client")
            with self.subTest(width=width, item="internal"), chrome() as cdp:
                sent, sid = self.load(cdp, width, internal)
                self.assertTrue(cdp.js("!!document.querySelector('[data-pk-latest-text]')", sid))
                self.assertIsNone(cdp.js(probe, sid), "an internal action's update is not published, so no label")
            with self.subTest(width=width, item="view"), chrome() as cdp:
                sent, sid = self.load(cdp, width, shown, edit=False)
                self.assertTrue(cdp.js("!!document.querySelector('[data-pk-latest-client]')", sid), "View has the label too (row 824)")

    def test_the_label_is_in_edit_only_and_never_in_a_published_file(self):
        built = (ROOT / "src/clark/page/page.html").read_text(encoding="utf-8")
        view = (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8")
        self.assertIn("data-pk-latest-client", built)
        self.assertNotIn("pk-latest-client", view)

    # In dark: what a part is drawn with, read from the page itself. `ink` is the part's text colour, `ground` the colour it is drawn over
    # (its own background, or the first one behind it, transparent layers blended in), and `want(name)` the colour a dark token gives.
    LOOK = """((sel) => {
      const e = document.querySelector(sel);
      if (!e) return null;
      const rgb = (c) => (c.match(/[\\d.]+/g) || []).map(Number);
      const probe = (v) => { const d = document.createElement('i'); d.style.color = v; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return rgb(c).slice(0, 3); };
      let ground = [0, 0, 0], left = 1, layers = [];
      for (let n = e; n; n = n.parentElement) layers.push(rgb(getComputedStyle(n).backgroundColor));
      layers.push(probe('var(--bg)').concat(1));
      let out = null;
      for (const l of layers) {
        const a = l.length > 3 ? l[3] : 1;
        if (!a) continue;
        out = out ? out.map((c, i) => c + l[i] * a * left) : l.slice(0, 3).map((c) => c * a);
        left *= 1 - a;
        if (left <= 0.001) break;
      }
      const lum = (c) => { const v = c.map((x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); }); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
      const s = getComputedStyle(e), r = e.getBoundingClientRect(), ink = rgb(s.color).slice(0, 3), g = out.map(Math.round);
      const hi = Math.max(lum(ink), lum(g)), lo = Math.min(lum(ink), lum(g));
      return {ink: ink, ground: g, bg: rgb(s.backgroundColor).slice(0, 3), border: rgb(s.borderTopColor).slice(0, 3), ratio: (hi + 0.05) / (lo + 0.05),
              shown: r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) > 0,
              text: e.textContent.trim()};
    })"""

    def look(self, cdp, sid, selector):
        return cdp.js(f"{self.LOOK}({json.dumps(selector)})", sid)

    def want(self, cdp, sid, token):
        return cdp.js(f"(v => {{ const d = document.createElement('i'); d.style.color = v; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return (c.match(/[\\d.]+/g) || []).map(Number).slice(0, 3); }})('var({token})')", sid)

    def test_in_dark_the_latest_update_box_its_stamp_and_the_overdue_bar_use_the_dark_tokens_and_read_clearly(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE, dark=True)
                self.assertEqual(cdp.js("document.documentElement.dataset.theme", sid), "dark")
                self.assertEqual(self.want(cdp, sid, "--surface"), [14, 45, 56], "the dark tokens are in force (#0E2D38)")
                bar, warn = self.look(cdp, sid, ".pk-warnbar"), self.look(cdp, sid, "[data-pk-warn] .pk-warn")
                self.assertTrue(bar["shown"])
                self.assertIn("6 days overdue (due 22-10-2026)", warn["text"])
                self.assertEqual(bar["bg"], self.want(cdp, sid, "--status-amber-tint"), "the bar is the dark amber tint")
                self.assertEqual(bar["border"], self.want(cdp, sid, "--status-amber"))
                self.assertEqual(warn["ink"], self.want(cdp, sid, "--status-amber-text"))
                self.assertGreaterEqual(warn["ratio"], 4.5, warn)
                for i in (1, 2):
                    move = self.look(cdp, sid, f"[data-pk-move]:nth-child({i})")
                    self.assertTrue(move["shown"], i)
                    self.assertGreaterEqual(move["ratio"], 4.5, move)
                self.assertTrue(self.inside(cdp, sid, ".pk-warnbar") and self.inside(cdp, sid, "[data-pk-move]:last-child"), "the bar fits the peek")
                box = self.look(cdp, sid, "[data-pk-latest-text]")
                self.assertTrue(box["shown"])
                self.assertIn(self.action(OVERDUE)["latest_update"], box["text"])
                self.assertEqual(box["ink"], self.want(cdp, sid, "--text"))
                self.assertGreaterEqual(box["ratio"], 4.5, box)
                lab = self.look(cdp, sid, "#pk-latest-lab")
                self.assertEqual(lab["text"], "Latest update")
                self.assertGreaterEqual(lab["ratio"], 4.5, lab)
                stamp = self.look(cdp, sid, "[data-pk-last]")
                self.assertTrue(stamp["shown"] and stamp["text"].startswith("Last updated "), stamp)
                self.assertEqual(stamp["ink"], self.want(cdp, sid, "--text-muted"))
                self.assertGreaterEqual(stamp["ratio"], 4.5, stamp)
                self.assertTrue(self.inside(cdp, sid, "[data-pk-last]"))
                click(cdp, sid, "[data-pk-latest-text]")                                          # the open box is dark too
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-latest-in]')", sid)))
                typing = self.look(cdp, sid, "[data-pk-latest-in]")
                self.assertEqual(typing["bg"], self.want(cdp, sid, "--surface"))
                self.assertEqual(typing["ink"], self.want(cdp, sid, "--text"))
                self.assertGreaterEqual(typing["ratio"], 4.5, typing)
                hint = self.look(cdp, sid, ".pk-latest-hint")
                self.assertGreaterEqual(hint["ratio"], 4.5, hint)
                key(cdp, sid, "Escape")
                self.assertEqual(sent, [], "looking sends nothing")

    def test_in_dark_the_draft_control_shows_and_reads_clearly(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE, dark=True)
                draft = self.look(cdp, sid, "[data-pk-draft]")
                self.assertIsNotNone(draft, "Draft is there in dark")
                self.assertTrue(draft["shown"])
                self.assertEqual(draft["text"], "Draft")
                self.assertEqual(draft["ink"], self.want(cdp, sid, "--status-blue-text"))
                self.assertEqual(draft["bg"], self.want(cdp, sid, "--surface"))
                self.assertGreaterEqual(draft["ratio"], 4.5, draft)
                self.assertTrue(self.inside(cdp, sid, "[data-pk-draft]"))
                self.assertTrue(cdp.js("(i => !!i && i.getBoundingClientRect().width > 0)(document.querySelector('[data-pk-draft] svg, [data-pk-draft] .i'))", sid), "its icon shows")
                click(cdp, sid, "[data-pk-draft]")
                self.assertTrue(wait(lambda: len(sent) == 1), "it still works in dark: one request")
                self.assertTrue(wait(lambda: cdp.js("(t => !!t && t.textContent.startsWith('Overdue since 22-10-2026.'))(document.querySelector('[data-pk-latest-text]'))", sid)))

    def test_view_has_all_of_it_on_work_items(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE, edit=False)
                self.assertTrue(cdp.js("!!document.querySelector('[data-pk-warn],[data-pk-draft],[data-pk-latest],[data-pk-last]')", sid), "Work items have no mode: View has the warning and Latest update too (row 824)")


if __name__ == "__main__":
    unittest.main()
