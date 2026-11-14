"""The peek's Latest update and the 'Last updated' stamp, and the overdue and weekend warning bar (v0.9 prototype parity). Row 1077:
the Draft chip is gone from every peek (ruling 1), so nothing here presses it; test_peek_ruled_1077.py pins its absence.
Run: python3 dev/run_tests.py test_peek_latest

Part 1 is clark/changes.py: an action's latest_update is one more field of the work-item change (plain text, line breaks allowed, 1000
characters at most, blank clears it), one step and one Undo, and a risk or a decision has none. Part 2 is the source and the built page.
Part 3 is the page in a real browser at 1400 and 900 px in Edit: the box, the stamp, Move to Friday, Move a week on and the
weekend bar's two moves, each one request and one Undo; View has none of it. In dark, at both widths, the box, its stamp and the overdue bar
are drawn with the dark tokens and each line of text reads at 4.5:1 or more on what it is drawn over.
"""
import json
import unittest
from _editor_checks import for_url
from datetime import datetime, timezone

from _paths import ROOT
import _testpage as testpage
from clark import activity_read  # noqa: E402

from clark import changes, sneak  # noqa: E402
from test_peek import key  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402
from test_work_filters import click, where  # noqa: E402

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
        code, body = self.send("Venue confirmed.\nContract next.")        # row 1005: plain text from an older caller is stored as the editor's paragraphs
        self.assertEqual((code, body["ok"], body["undoable"]), (200, True, True), body)
        self.assertEqual(body["item"]["latest_update"], "<p>Venue confirmed.</p><p>Contract next.</p>")
        self.assertEqual(self.latest(), "<p>Venue confirmed.</p><p>Contract next.</p>")
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
        for text in ("x" * (changes.LATEST_UPDATE_MAX + 1), "a​b", "a\x00b", "a‮b", "a\tb", "a\rb", "a\r\nb", "<p>a\rb</p>", "a\ud800b", "<p>a​b</p>", "<p>a&#x200b;b</p>", "<p>a\tb</p>", 5, False, True, ["x"], {"a": 1}):
            code, body = self.send(text)
            self.assertEqual((code, body["ok"]), (400, False), repr(text)[:20])
        self.assertEqual(self.latest(), was)
        self.assertEqual(self.send("x" * changes.LATEST_UPDATE_MAX)[0], 200, "the limit itself is allowed")
        self.assertEqual(self.send("<p><strong>" + "x" * changes.LATEST_UPDATE_MAX + "</strong></p>")[0], 200, "the limit counts the words, not the markup")

    def test_each_refusal_says_what_is_wrong_in_its_own_plain_sentence(self):
        said = lambda text: self.send(text)[1]["message"]
        self.assertEqual(said("x" * (changes.LATEST_UPDATE_MAX + 1)), changes.LATEST_LONG_WORDS)
        self.assertIn(str(changes.LATEST_UPDATE_MAX), changes.LATEST_LONG_WORDS)
        for text in ("a​b", "a\x00b", "a‮b", "a\tb", "a\rb", "line one\nline two\u200b", "<p>a&#x200b;b</p>"):
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
    LINES = ("Latest update", "Last updated", "Move to Friday", "Move a week on", "Move to Monday", "a working day is usually meant")

    def test_each_line_is_in_the_source_and_the_edit_page_and_not_in_a_published_file(self):
        src = "".join((ROOT / "src/clark/page/src/edit" / f).read_text(encoding="utf-8") for f in ("PeekLatest.jsx", "peekLatest.js"))
        built = (ROOT / "src/clark/page/page.html").read_text(encoding="utf-8")
        view = (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8")
        for line in self.LINES:
            self.assertIn(line, src, line)
            self.assertIn(line, built, line)
        for line in ("Move a week on", "Last updated", "pk-warnbar"):
            self.assertNotIn(line, view, "the published page carries none of it: " + line)

    def test_the_page_says_the_two_new_refusals_in_its_own_words(self):
        report = (ROOT / "src/clark/page/src/stores/report.js").read_text(encoding="utf-8")
        for sentence in (changes.LATEST_LONG_WORDS, changes.LATEST_HIDDEN_WORDS):
            self.assertIn(json.dumps(sentence) + ":", report, "plainChange knows the server's sentence, or the page would say 'could not be made'")

    def test_a_refusal_keeps_the_typed_text_and_the_page_checks_hidden_characters_first(self):
        edit = ROOT / "src/clark/page/src/edit"
        jsx = (edit / "PeekLatest.jsx").read_text(encoding="utf-8")
        helper = (edit / "peekLatest.js").read_text(encoding="utf-8")
        self.assertNotIn("\\p{Cc}", helper, "item 1005: the server refuses hidden characters and says so in a toast; the page keeps no copy of the check")
        self.assertIn("<RichField", jsx, "the one editor (item 1005)")
        self.assertNotIn("<textarea", jsx)
        save = jsx[jsx.index("const save ="):jsx.index("return (", jsx.index("const save ="))]
        self.assertIn("changeCell(", save)
        self.assertNotIn("refused:", save, "a refusal is the toast's; RichText keeps the editor open when the save answers null")

    def test_each_change_is_sent_with_its_own_place(self):
        jsx = (ROOT / "src/clark/page/src/edit/PeekLatest.jsx").read_text(encoding="utf-8")
        self.assertEqual(jsx.count('place: "peek"'), 2, "a move and a saved update (item 1158: the Needed from the client switch is gone)")
        self.assertNotIn('place: "draft"', jsx, "row 1077: the page no longer drafts (the server still knows the place, for its history)")
        self.assertIn('done.place || "cell"', (ROOT / "src/clark/page/src/stores/changes.js").read_text(encoding="utf-8"))
        self.assertTrue({"peek", "draft"} <= set(changes.PLACES))

    def test_the_label_ids_come_from_the_item_id_not_fixed_names(self):
        """#550: two peeks (or a peek and a stale one while it leaves) must not share an id, so the ids carry the item id."""
        jsx = (ROOT / "src/clark/page/src/edit/PeekLatest.jsx").read_text(encoding="utf-8")
        self.assertNotIn('id="pk-latest-lab"', jsx)
        self.assertNotIn('id="pk-latest-txt"', jsx)
        self.assertIn("id={`pk-latest-lab-${row.id}`}", jsx)
        self.assertIn("viewId={`pk-latest-txt-${row.id}`}", jsx)               # item 1005: the text is RichField's view; the id and the label list reach it as props
        self.assertIn("labelledBy={`pk-latest-lab-${row.id} pk-latest-txt-${row.id}`}", jsx)
        field = (ROOT / "src/clark/page/src/edit/RichField.jsx").read_text(encoding="utf-8")
        self.assertIn("id={viewId}", field)
        self.assertIn("aria-labelledby={labelledBy}", field)

    def test_the_peek_hands_both_parts_to_edit_only(self):
        peek = (ROOT / "src/clark/page/src/components/Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("editing && forItem && tools.PeekWarn", peek)
        self.assertIn("editing && forItem && tools.PeekLatest", peek)
        self.assertNotIn("edit/", peek.replace("tools.", "").replace("../edit/editing.js", ""), "Peek.jsx imports nothing from edit/ but the one editing test (edit/editing.js)")


class Browser(unittest.TestCase):
    def fresh(self):
        """A fresh demo database: a move or a save at one width never reaches the next width or test."""
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

    def load(self, cdp, width, item, edit=True, dark=False, late=False, seed=None, refuse=False):
        self.fresh()
        if seed is not None:                                  # a row an older clark wrote: plain text in the column
            with self.store.step("dashboard", "Demo User") as st:
                st.update("actions", item, {"latest_update": seed})
        sent = []
        real = changes.make_change(self.store.path, [], "Demo User")
        projects = self.store.read("projects")            # read here: the store's connection belongs to this thread, and the server answers on another
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: projects, page_html=lambda: testpage.html(),
                    sneak=sneak.make_read(self.store.data_for), change=lambda req: (sent.append(req), self.refused() if refuse else real(req))[1],
                    undo=changes.make_undo(self.store.path, [], "Demo User"))
        if getattr(self, "with_activity", False): s.httpd.activity = activity_read.make_read(self.store.path, self.store.data_for)      # the Activity tab reads history (rows 1182, 1183)
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        if late:
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": self.HOLD}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#work&p={self.code}")}, sid)
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

    @staticmethod
    def refused():
        raise RuntimeError("test refusal")

    SHOWN = "[data-pk-latest] [data-rich=latest_update]"           # item 1005: the update drawn as text; a click opens the one rich editor in its place
    BOX = "#peek .ProseMirror"

    def open_box(self, cdp, sid):
        click(cdp, sid, self.SHOWN)
        self.assertTrue(wait(lambda: cdp.js("document.activeElement.classList.contains('ProseMirror')", sid), 15), "the editor opens with the focus in it")

    def type_in(self, cdp, sid, text):
        cdp.js(f"document.querySelector({json.dumps(self.BOX)}).cxed.editor.commands.insertContent({json.dumps(text)}); true", sid)

    def save_key(self, cdp, sid):
        mod = 4 if cdp.js("/Mac/.test(navigator.platform)", sid) else 2
        for kind in ("keyDown", "keyUp"):
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "modifiers": mod}, sid)

    def due(self, cdp, sid):
        return cdp.js("(d => d ? d.textContent.replace('Changed', '').trim() : '')(document.querySelector('#peek .pk-chips [data-row=due] .pkc-v') || document.querySelector('#peek [data-row=due] dd'))", sid)

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

    def test_the_box_saves_on_cmd_enter_and_leaves_the_text_on_escape(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, "Typed and abandoned")
                key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: cdp.js(f"!document.querySelector({json.dumps(self.BOX)}) && !!document.querySelector({json.dumps(self.SHOWN)})", sid)), "Esc closes the box only")
                self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "the peek stays")
                self.assertEqual(sent, [], "nothing was sent")
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, "Brand new words")
                self.save_key(cdp, sid)
                self.assertTrue(wait(lambda: "Brand new words" in cdp.js(f"(document.querySelector({json.dumps(self.SHOWN)}) || {{textContent: ''}}).textContent", sid)))
                self.assertEqual(len(sent), 1)
                self.assertIn("Brand new words", sent[0]["changes"]["latest_update"])
                self.assertTrue(sent[0]["changes"]["latest_update"].startswith("<p>"), "the editor's HTML is what is sent")

    def test_leaving_the_box_saves_it_once_and_one_undo_puts_the_old_text_back(self):
        """Item 1005 follow-up: the Latest update saves when the focus leaves it, like the At a glance Reason; Esc still saves nothing."""
        a = self.action(OVERDUE)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, " Blur saved.")
                # Settle on the editor's own state, not a sleep: the typed text is in the editor
                # and the label we click has the same place in two frames running.
                self.assertTrue(wait(lambda: cdp.js(f"document.querySelector({json.dumps(self.BOX)}).textContent.includes('Blur saved.')", sid), 10), "the editor holds the typed text")
                cdp.js("""window.__lab = null; (() => { const at = () => { const r = document.querySelector('#peek .pk-lab, #peek h2, #peek h3').getBoundingClientRect(); return r.x + ',' + r.y + ',' + r.height; }; let last = at(), n = 0; const tick = () => { const now = at(); n = now === last ? n + 1 : 0; last = now; if (n >= 2) { window.__lab = now; } else { requestAnimationFrame(tick); } }; requestAnimationFrame(tick); })(); true""", sid)
                self.assertTrue(wait(lambda: cdp.js("window.__lab !== null", sid), 10), "the page has settled")
                x, y = cdp.js("(() => { const r = document.querySelector('#peek .pk-lab, #peek h2, #peek h3').getBoundingClientRect(); return [r.x + 4, r.y + r.height / 2]; })()", sid)
                for kind in ("mousePressed", "mouseReleased"):
                    cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1}, sid)
                self.assertTrue(wait(lambda: cdp.js(f"!document.querySelector({json.dumps(self.BOX)})", sid), 10), "leaving the box closed it")
                self.assertTrue(wait(lambda: "Blur saved." in cdp.js(f"(document.querySelector({json.dumps(self.SHOWN)}) || {{textContent: ''}}).textContent", sid)))
                self.assertEqual(len(sent), 1, "one save, never two")
                self.assertIn("Blur saved.", sent[0]["changes"]["latest_update"])
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js(f"document.querySelector({json.dumps(self.SHOWN)}).textContent", sid) == a["latest_update"]), "one Undo")
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, " Not kept.")
                key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: cdp.js(f"!document.querySelector({json.dumps(self.BOX)})", sid)))
                self.assertEqual(len(sent), 1, "Esc after the Undo saved nothing")

    def test_a_legacy_plain_update_opens_in_the_editor_as_paragraphs_and_is_not_saved_by_looking(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE, seed='Line one: a < b & "c"\nLine two')
            self.assertEqual(cdp.js(f"[...document.querySelectorAll({json.dumps(self.SHOWN + ' p')})].map(p => p.textContent)", sid), ['Line one: a < b & "c"', "Line two"])
            self.assertEqual(cdp.js(f"document.querySelectorAll({json.dumps(self.SHOWN + ' b, ' + self.SHOWN + ' script')}).length", sid), 0, "the < is text, never markup")
            self.open_box(cdp, sid)
            self.assertEqual(cdp.js(f"[...document.querySelectorAll({json.dumps(self.BOX + ' p')})].map(p => p.textContent)", sid), ['Line one: a < b & "c"', "Line two"])
            key(cdp, sid, "Escape")
            self.assertEqual(sent, [], "opening and leaving saved nothing, so the old row is as it was")

    def test_the_box_has_the_focus_as_it_is_drawn_not_a_frame_later(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE, late=True)
            click(cdp, sid, self.SHOWN)
            self.assertTrue(cdp.js("!!document.querySelector('#peek .ProseMirror')", sid), "the click opened the editor")
            self.assertTrue(cdp.js("document.activeElement.classList.contains('ProseMirror')", sid), "the editor has the focus with no frame in between")

    def test_a_too_long_update_is_refused_by_clark_in_words_and_the_box_stays(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, "x" * 1001)
            self.save_key(cdp, sid)
            self.assertTrue(wait(lambda: "1000 characters" in self.toast(cdp, sid)), "clark says the update is too long: " + self.toast(cdp, sid))
            self.assertEqual(len(sent), 1)
            self.assertTrue(cdp.js(f"!!document.querySelector({json.dumps(self.BOX)})", sid), "the editor keeps what was typed")
            self.assertEqual(cdp.js(f"document.querySelector({json.dumps(self.BOX)}).textContent.replace(/[^x]/g, '').length", sid), 1001)

    def test_a_hidden_character_is_refused_by_clark_in_words_and_the_box_keeps_the_text(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, "Pasted\u200bwith a zero-width space")
            self.save_key(cdp, sid)
            self.assertTrue(wait(lambda: "hidden character" in self.toast(cdp, sid)), "clark says the character is hidden: " + self.toast(cdp, sid))
            self.assertEqual(len(sent), 1)
            self.assertIn("Pasted", cdp.js(f"(document.querySelector({json.dumps(self.BOX)}) || {{textContent: ''}}).textContent", sid), "the editor keeps what was typed")

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
                self.open_box(cdp, sid)                                   # row 1077: a save through the box moves the stamp (Draft is gone)
                self.type_in(cdp, sid, " Stamp moves.")
                self.save_key(cdp, sid)
                self.assertTrue(wait(lambda: len(sent) == 1), "one save")
                self.assertTrue(wait(lambda: got() != want), "the stamp is the one clark wrote")

    def test_a_risk_shows_the_stamp_but_no_latest_update(self):
        risk = self.data["raid"][0]["id"]
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, risk)
            self.assertTrue(cdp.js("!!document.querySelector('[data-pk-last]')", sid))
            self.assertFalse(cdp.js("!!document.querySelector('[data-rich=latest_update]')", sid))

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
                click(cdp, sid, self.SHOWN)                                               # still there while the box is open
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .ProseMirror')", sid)))
                self.assertEqual(cdp.js(probe, sid), "Shown to the client")
            with self.subTest(width=width, item="internal"), chrome() as cdp:
                sent, sid = self.load(cdp, width, internal)
                self.assertTrue(cdp.js("!!document.querySelector('[data-pk-latest] [data-rich=latest_update]')", sid))
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
                box = self.look(cdp, sid, "[data-pk-latest] [data-rich=latest_update] .sec-body")
                self.assertTrue(box["shown"])
                self.assertIn(self.action(OVERDUE)["latest_update"], box["text"])
                self.assertEqual(box["ink"], self.want(cdp, sid, "--text"))
                self.assertGreaterEqual(box["ratio"], 4.5, box)
                lab = self.look(cdp, sid, '[id^="pk-latest-lab-"]')
                ident = cdp.js("document.querySelector('[id^=\"pk-latest-lab-\"]').id.slice('pk-latest-lab-'.length)", sid)
                self.assertEqual(cdp.js("(e => [e.id, e.getAttribute('aria-labelledby')])(document.querySelector('[data-pk-latest] [data-rich=latest_update]'))", sid),
                                 ["pk-latest-txt-" + ident, "pk-latest-lab-%s pk-latest-txt-%s" % (ident, ident)], "row 550: the ids carry the item id, and the text is named by its label and itself")
                self.assertEqual(lab["text"], "Latest update")
                self.assertGreaterEqual(lab["ratio"], 4.5, lab)
                stamp = self.look(cdp, sid, "[data-pk-last]")
                self.assertTrue(stamp["shown"] and stamp["text"].startswith("Last updated "), stamp)
                self.assertEqual(stamp["ink"], self.want(cdp, sid, "--text-muted"))
                self.assertGreaterEqual(stamp["ratio"], 4.5, stamp)
                self.assertTrue(self.inside(cdp, sid, "[data-pk-last]"))
                self.open_box(cdp, sid)                                                           # the open editor is dark too
                typing = self.look(cdp, sid, "#peek .rt-host")
                self.assertEqual(typing["ink"], self.want(cdp, sid, "--text"))
                self.assertGreaterEqual(typing["ratio"], 4.5, typing)
                hint = self.look(cdp, sid, "#peek .rt-keys")
                self.assertGreaterEqual(hint["ratio"], 4.5, hint)
                key(cdp, sid, "Escape")
                self.assertEqual(sent, [], "looking sends nothing")

    def test_view_has_all_of_it_on_work_items(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE, edit=False)
                self.assertTrue(cdp.js("!!document.querySelector('[data-pk-warn],[data-pk-latest],[data-pk-last]')", sid), "Work items have no mode: View has the warning and Latest update too (row 824)")


if __name__ == "__main__":
    unittest.main()
