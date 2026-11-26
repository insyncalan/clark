"""Row 1533: the Work items board in a published report, read only, shown to the client only when the author's switch is on.

Run: python3 -m unittest test_published_board_1533   (from tests/)
Two files are published from the test plant: one with the board switch off (the project's show_board_client is 0, the default) and one with it
on. The switch is the project's `show_board_client`; the file carries it as project.board (1 or absent). Both are opened from disk in headless
Chrome at 1400 and 900 px, light and dark.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT  # noqa: F401  (puts src/ on the path)
import _publish_fixture as fx

from clark import publish
from clark.store import open_store
from test_client_page_filters import page_target, EMPTY_BRANDING, INTERNAL, HIDDEN_OWNER, HIDDEN_WS, TODAY, VARIANTS, open_page, plant
from test_publish_route import Rig, WANTED
from test_server import chrome, wait
from test_work_filters import need_chrome

TYPES = ["action", "risk", "decision"]      # the type chips; issues sit inside "Risks and issues" (filters.js:15-16), so AP2's 4 kinds are these 3 chips plus the issue rows in the risk chip
ISSUE_ID = "PUB-003"
SIZE_BEFORE = 848970       # page-view.html on origin/main d5ad8db2d, bytes, built by dev/tools/build_page.py
WRITE_WORDS = ["changeItem", "stores/changes", "/api/", "fetch("]
MOVE_CODE = ["Move to", "data-move", "onDragStart"]      # strings only the editor board ships (edit/Board.jsx: the Move to menu, its button and the drag start); the CSS keeps its class names


# Runs before the page's own scripts: any call a page could use to reach the network is recorded in window.__net.
WATCH = """window.__net = [];
for (const [o, n] of [[window, 'fetch'], [XMLHttpRequest.prototype, 'send'], [navigator, 'sendBeacon']]) {
  const real = o[n]; if (!real) continue;
  o[n] = function () { window.__net.push(n); return real.apply(this, arguments); };
}
for (const n of ['WebSocket', 'EventSource']) { const R = window[n]; window[n] = function () { window.__net.push(n); return new R(...arguments); }; }"""


def open_watched(cdp, url, width):
    sid = page_target(cdp)
    cdp.call("Page.enable", {}, sid)
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
    cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": WATCH}, sid)
    cdp.call("Page.navigate", {"url": url}, sid)
    return sid


def plant_with_issue():
    """The shared plant plus one client-visible issue, so AP2's four kinds (actions, risks, issues, decisions) are all on the page."""
    p = plant()
    p["data"]["raid"].append(dict(p["data"]["raid"][0], id=ISSUE_ID, type="Issue", description="Crane access is blocked", workstream=None))
    return p


def publish_with(store, out, switch):
    real = publish.read_inputs

    def read(*a, **k):
        inputs = real(*a, **k)
        inputs["data"]["project"]["show_board_client"] = switch
        return inputs
    with mock.patch.object(publish, "read_inputs", read):
        return Path(publish.publish(store, "PUB", out, by_user="Demo User", now=TODAY, branding=EMPTY_BRANDING)["path"])


def ids_of(cdp, sid, sel):
    return cdp.js(f"[...document.querySelectorAll({sel!r})].map(x => x.dataset.id)", sid)


class PublishedBoard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark-pb-"))
        cls.store = open_store(fx.build_db(cls.tmp / "c.db", plant_with_issue()), onedrive_roots=[])
        (cls.tmp / "off").mkdir()
        (cls.tmp / "on").mkdir()
        cls.off = publish_with(cls.store, cls.tmp / "off", 0)
        cls.on = publish_with(cls.store, cls.tmp / "on", 1)

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(cls.tmp, True)

    def page(self, cdp, which, width=1400, scheme="light"):
        sid = open_page(cdp, which.as_uri() + "#work", width, scheme)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work-list')", sid)), "the Work items tab drew")
        return sid

    def to_board(self, cdp, sid):
        cdp.js("document.querySelector('[data-layout=board]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work-board')", sid)), "the board drew")

    def test_published_board_switch_off_has_no_board(self):
        text = self.off.read_text(encoding="utf-8")
        self.assertNotIn('"board":1', text.replace(" ", ""))
        for w, s in VARIANTS:
            with chrome() as cdp:
                sid = self.page(cdp, self.off, w, s)
                self.assertEqual(cdp.js("document.querySelectorAll('[data-layout], #layout-seg, #work-board').length", sid), 0, f"{w} {s}: no Board choice, no board")
                self.assertGreater(cdp.js("document.querySelectorAll('#work-list tr[data-id]').length", sid), 0, "the list stays")

    def test_published_board_only_the_whole_number_1_turns_it_on(self):
        for i, bad in enumerate((True, 1.0, "1", 2, -1, None, [1], 0)):
            out = self.tmp / f"bad{i}"
            out.mkdir()
            text = publish_with(self.store, out, bad).read_text(encoding="utf-8").replace(" ", "")
            self.assertNotIn('"board":1', text, f"{bad!r} draws no board")

    def test_published_board_switch_on_offers_list_and_board_list_first(self):
        for w, s in VARIANTS:
            with chrome() as cdp:
                sid = self.page(cdp, self.on, w, s)
                self.assertEqual(cdp.js("[...document.querySelectorAll('#layout-seg button')].map(b => b.textContent + ':' + b.getAttribute('aria-pressed'))", sid),
                                 ["List:true", "Board:false"], f"{w} {s}: List first and the default")
                self.assertEqual(cdp.js("document.querySelectorAll('#work-board').length", sid), 0)
                self.to_board(cdp, sid)
                self.assertEqual(cdp.js("document.querySelectorAll('#work-list table').length", sid), 0, "the table is not drawn under the board")

    def test_published_board_same_items_as_list(self):
        with chrome() as cdp:
            sid = self.page(cdp, self.on)
            cdp.js("document.querySelector('[data-show=all]').click()", sid)
            for kind in ["all"] + TYPES:
                cdp.js(f"document.querySelector('[data-type={kind}]').click()", sid)
                cdp.js("document.querySelector('[data-layout=table]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work-list tr[data-id]').length", sid) > 0), kind)
                rows = sorted(ids_of(cdp, sid, "#work-list tr[data-id]"))
                self.to_board(cdp, sid)
                cards = sorted(ids_of(cdp, sid, "#work-board article[data-id]"))
                self.assertEqual(cards, rows, f"{kind}: the board's cards are the list's rows")
                if kind in ("all", "risk"):
                    self.assertIn(ISSUE_ID, cards, f"{kind}: the issue is a card, as it is a row")
                if kind == "all":
                    cdp.js("document.querySelector('[data-layout=table]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work-list tr[data-id]').length", sid) > 0))
                    kinds = set(cdp.js("[...document.querySelectorAll('#work-list tr[data-id]')].map(r => r.dataset.kind)", sid))
                    self.assertTrue({"action", "risk", "issue", "decision"} <= kinds, f"AP2's four kinds are all on the page: {sorted(kinds)}")
                    self.to_board(cdp, sid)
                self.assertNotIn(INTERNAL, cdp.js("document.getElementById('work').textContent", sid))

    def test_published_board_client_output(self):
        text = self.on.read_text(encoding="utf-8")
        for secret in (INTERNAL, HIDDEN_OWNER, HIDDEN_WS):
            self.assertNotIn(secret, text, "a row that is not the client's is not in the file")
        with chrome() as cdp:
            sid = self.page(cdp, self.on)
            cdp.js("document.querySelector('[data-show=all]').click()", sid)
            self.to_board(cdp, sid)
            for g in ("owner", "workstream", "status"):
                cdp.js(f"document.querySelector('#group-by').click()", sid)
                cdp.js(f"[...document.querySelectorAll('[role^=menuitem]')].find(x => x.textContent.toLowerCase().includes({g!r})).click()", sid)
                body = cdp.js("document.getElementById('work-board').textContent", sid)
                for secret in (INTERNAL, HIDDEN_OWNER, HIDDEN_WS):
                    self.assertNotIn(secret, body, g)

    def test_published_board_cannot_change_data(self):
        for w, s in VARIANTS:
            with chrome() as cdp:
                sid = self.page(cdp, self.on, w, s)
                self.to_board(cdp, sid)
                for part in (".bc-move", "[data-move]", ".bmv", ".eye", "[data-eye]", ".bulk", ".selbar", "[data-select]", "input[type=checkbox]", "#add", ".newtile"):
                    self.assertEqual(cdp.js(f"document.querySelectorAll('#work {part}').length", sid), 0, f"{w} {s}: no {part}")
                before = ids_of(cdp, sid, "#work-board article[data-id]")
                cdp.js("""(() => { const c = document.querySelector('#work-board article'); const r = c.getBoundingClientRect();
                  c.parentElement.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, button: 0, clientX: r.x + 10, clientY: r.y + 10}));
                  document.dispatchEvent(new PointerEvent('pointermove', {bubbles: true, clientX: r.x + 400, clientY: r.y + 10}));
                  document.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, clientX: r.x + 400, clientY: r.y + 10})); })()""", sid)
                self.assertEqual(ids_of(cdp, sid, "#work-board article[data-id]"), before, "a drag changes nothing")
                self.assertEqual(cdp.js("document.querySelectorAll('#work-board .bghost, #work-board .dpick').length", sid), 0)
                self.assertEqual(cdp.js("document.querySelectorAll('#work-board article[draggable]').length", sid), 0)
        text = self.on.read_text(encoding="utf-8")
        for code in MOVE_CODE:
            self.assertNotIn(code, text, f"the published file holds none of the editor board's move code: {code}")
        for word in WRITE_WORDS[:2]:
            self.assertNotIn(word, text, f"the file holds no {word}")

    def test_published_page_carries_no_drag_attribute_on_any_element(self):
        """Row 1534: the column drag of the editor's Work items headings (data-colmove) and the board's Move button (data-move) are editor-only. The published
        page, with the board switch on or off, has no ELEMENT that carries either attribute, in the list and on the board, so the guard does not depend on a name."""
        for which in ("on", "off"):
            for w in (1400, 900):
                with chrome() as cdp:
                    sid = self.page(cdp, getattr(self, which), w, "light")
                    self.assertGreater(cdp.js("document.querySelectorAll('#work th').length", sid), 0, f"{which} {w}: the list headings are there")
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-colmove], [data-move]').length", sid), 0, f"{which} {w} list: no drag attribute")
                    if which == "on":
                        self.to_board(cdp, sid)
                        self.assertEqual(cdp.js("document.querySelectorAll('[data-colmove], [data-move]').length", sid), 0, f"{which} {w} board: no drag attribute")

    def test_published_board_card_opens_the_peek(self):
        with chrome() as cdp:
            sid = self.page(cdp, self.on)
            self.to_board(cdp, sid)
            cdp.js("document.querySelector('#work-board article .bc-main').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-peek]')", sid)), "the card opens the peek")

    def test_published_board_keyboard_and_full_screen(self):
        for w, s in VARIANTS:
            with chrome() as cdp:
                sid = self.page(cdp, self.on, w, s)
                self.to_board(cdp, sid)
                first = cdp.js("document.querySelector('#work-board .bc-main[tabindex=\"0\"]').dataset.cursor", sid)
                cdp.js("document.querySelector('#work-board .bc-main[tabindex=\"0\"]').focus()", sid)
                key = "(k) => document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: k, bubbles: true, cancelable: true}))"
                for k in ("ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft"):
                    cdp.js(f"({key})({k!r})", sid)
                cdp.js(f"({key})('Enter')", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-peek]')", sid)), f"{w} {s}: Enter opens the peek")
                cdp.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}))", sid)
                self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[data-peek]')", sid)), "Esc closes the peek")
                self.assertTrue(first)
                cdp.js("document.querySelector('#board-full').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.body.classList.contains('board-full')", sid)), "full screen on")
                cdp.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}))", sid)
                self.assertTrue(wait(lambda: not cdp.js("document.body.classList.contains('board-full')", sid)), "Esc leaves full screen")
                handle = "document.querySelector('#work-board [data-resize]')"
                w0 = cdp.js(f"{handle}.getAttribute('aria-valuenow')", sid)
                cdp.js(f"{handle}.dispatchEvent(new KeyboardEvent('keydown', {{key: 'ArrowRight', bubbles: true, cancelable: true}}))", sid)
                self.assertTrue(wait(lambda: cdp.js(f"{handle}.getAttribute('aria-valuenow')", sid) != w0), "a width changes")
                self.assertEqual(cdp.js("localStorage.getItem('clark.work.v1')", sid), None, "a width is the viewer's own, kept in memory, never the editor's key")
                cdp.js("document.querySelector('#work-board [data-toggle]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work-board .col.shut').length", sid) == 1), "a column collapses")

    def test_published_board_due_words_match_the_list(self):
        pick = "[...document.querySelectorAll({sel!r})].map(x => [x.dataset.id, ((x.querySelector('.due-l') || {{}}).textContent || ''), ((x.querySelector('.due-l') || {{}}).className || '')])"
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.page(cdp, self.on, width)
                cdp.js("document.querySelector('[data-show=all]').click()", sid)
                cdp.js("document.querySelector('[data-layout=table]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work-list tr[data-id]').length", sid) > 0), "the list drew")
                listed = {r[0]: r[1:] for r in cdp.js(pick.format(sel="#work-list tr[data-id]"), sid)}
                self.to_board(cdp, sid)
                carded = {r[0]: r[1:] for r in cdp.js(pick.format(sel="#work-board article[data-id]"), sid)}
                words = [v[0] for v in listed.values()]
                self.assertTrue(any(w.endswith(" late") for w in words), f"{width}: the list shows an overdue row's words")
                self.assertTrue(any(w.startswith("In ") for w in words), f"{width}: the list shows a coming row's words")
                self.assertTrue(any(not w for w in words), f"{width}: a row with no due words shows none on both")
                self.assertGreater(len({v[1] for v in listed.values()}), 1, f"{width}: the list tones the words (more than one look)")
                self.assertEqual(carded, listed, f"{width}: each card shows its row's due words and tone, and no row is missing")

    def test_published_board_filters_search_empty(self):
        with chrome() as cdp:
            sid = self.page(cdp, self.on)
            cdp.js("document.querySelector('[data-show=all]').click()", sid)
            self.to_board(cdp, sid)
            cdp.js("document.querySelector('[data-type=decision]').click()", sid)
            self.assertTrue(wait(lambda: all(i.startswith("PUB-D") for i in ids_of(cdp, sid, "#work-board article[data-id]"))), "the type filter applies")
            cdp.js("""(() => { const q = document.getElementById('q'); q.value = 'zzzz-no-such'; q.dispatchEvent(new Event('input', {bubbles: true})); })()""", sid)
            self.assertTrue(wait(lambda: "No items match these filters" in cdp.js("document.getElementById('work-list').textContent", sid)), "the empty words")
            self.assertEqual(cdp.js("document.querySelectorAll('#work-board').length", sid), 0)

    def test_published_board_group_by_fields_in_file(self):
        with chrome() as cdp:
            sid = self.page(cdp, self.on)
            self.to_board(cdp, sid)
            cdp.js("document.querySelector('#group-by').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[role=menu]')", sid)))
            names = cdp.js("[...document.querySelectorAll('[role=menu] [role^=menuitem]')].map(x => x.textContent.replace('\u2713', '').trim())", sid)
            self.assertEqual(names[:7], ["Workstream", "Status", "Due", "Owner", "Priority", "Milestone", "Type"], "the table's choices, no Nothing on a board")
            self.assertEqual(names[7:], ["No lanes", "Type lanes"], "the editor's own Swimlanes words (Workstream is the Group by, so it is not a lane), no others")
            cdp.js("[...document.querySelectorAll('[role^=menuitem]')].find(x => x.textContent.replace('\u2713', '').trim() === 'Owner').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#work-board .col[data-col]') && [...document.querySelectorAll('#work-board .col')].some(c => /Ana Lopez/.test(c.getAttribute('aria-label')))", sid)), "columns follow Group by")
            cdp.js("document.querySelector('#group-by').click()", sid)
            cdp.js("[...document.querySelectorAll('[role^=menuitem]')].find(x => x.textContent.replace('\u2713', '').trim() === 'Type lanes').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.getElementById('work-live').textContent", sid) == "Type lanes."), "the editor's announcement")
            self.assertEqual(cdp.js("document.getElementById('group-by').getAttribute('aria-label')", sid), "Group by: Owner, type lanes")
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work-board .lane-h').length", sid) > 0), "swimlanes draw")


    def test_published_board_picking_the_lane_as_group_clears_the_lane_and_none_says_no_lanes(self):
        def pick(cdp, sid, name):
            cdp.js("document.querySelector('#group-by').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[role=menu]')", sid)))
            cdp.js(f"[...document.querySelectorAll('[role^=menuitem]')].find(x => x.textContent.replace('\\u2713', '').trim() === {name!r}).click()", sid)

        def label(cdp, sid):
            return cdp.js("document.getElementById('group-by').getAttribute('aria-label')", sid)
        with chrome() as cdp:
            sid = self.page(cdp, self.on)
            self.to_board(cdp, sid)
            pick(cdp, sid, "Type lanes")
            self.assertTrue(wait(lambda: label(cdp, sid) == "Group by: Workstream, type lanes"))
            pick(cdp, sid, "Type")      # the lane becomes the group: the lane is dropped, not kept for later
            self.assertTrue(wait(lambda: label(cdp, sid) == "Group by: Type"))
            self.assertEqual(cdp.js("document.getElementById('work-live').textContent", sid), "Grouped by Type.")
            pick(cdp, sid, "Workstream")
            self.assertTrue(wait(lambda: label(cdp, sid) == "Group by: Workstream"), "no lane comes back")
            pick(cdp, sid, "Type lanes")
            self.assertTrue(wait(lambda: label(cdp, sid) == "Group by: Workstream, type lanes"))
            pick(cdp, sid, "No lanes")
            self.assertTrue(wait(lambda: label(cdp, sid) == "Group by: Workstream"), "No lanes clears the lane")
            self.assertEqual(cdp.js("document.getElementById('work-live').textContent", sid), "No lanes.")
            self.assertEqual(cdp.js("document.querySelectorAll('#work-board .lane-h').length", sid), 0, "no lane rows are drawn")
            self.assertGreater(cdp.js("document.querySelectorAll('#work-board article[data-id]').length", sid), 0, "the cards are still there")
            pick(cdp, sid, "Type")
            pick(cdp, sid, "Workstream")
            self.assertTrue(wait(lambda: label(cdp, sid) == "Group by: Workstream"), "the cleared lane stayed cleared")

    def test_published_board_print_follows_table(self):
        with chrome() as cdp:
            sid = self.page(cdp, self.on)
            self.to_board(cdp, sid)
            cdp.js("window.dispatchEvent(new Event('beforeprint'))", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.print-tab #work-board').length === 0 && document.querySelectorAll('.print-tab #work-list tr[data-id]').length > 0", sid)), "printing draws the list")
            cdp.js("window.dispatchEvent(new Event('afterprint'))", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work-board')", sid)), "the board is back after printing")


    def test_published_board_to_client_mode_carries_the_switch(self):
        """Local publishing and the To client route both start from publish.build (#43): the switch reaches both the same way."""
        real = publish.read_inputs

        def read(on):
            def f(*a, **k):
                inputs = real(*a, **k)
                inputs["data"]["project"]["show_board_client"] = on
                return inputs
            return f
        for on in (0, 1):
            with mock.patch.object(publish, "read_inputs", read(on)):
                body = publish.build(self.store, "PUB", TODAY, EMPTY_BRANDING)["body"]
            self.assertEqual(b'"board":1' in body.replace(b" ", b""), bool(on), f"switch {on}")

    def test_published_file_stays_self_contained(self):
        text = self.on.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(src|href)=[\"']https?://")
        self.assertNotIn("XMLHttpRequest", text)
        view = (ROOT / "src" / "clark" / "page" / "page-view.html").stat().st_size
        print(f"\npage-view.html bytes: before {SIZE_BEFORE}, after {view}")
        self.assertGreater(view, SIZE_BEFORE)
        with chrome() as cdp:
            sid = open_watched(cdp, self.on.as_uri() + "#work", 1400)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work-list')", sid)), "the Work items tab drew")
            self.to_board(cdp, sid)
            cdp.js("document.querySelector('[data-layout=table]').click(); document.querySelector('[data-layout=board]').click()", sid)
            self.assertEqual(cdp.js("window.__net", sid), [], "AP8: 0 network requests: fetch(, XMLHttpRequest, sendBeacon, WebSocket and EventSource were never called while the list and the board drew")
            self.assertEqual(cdp.js("performance.getEntriesByType('resource').filter(r => !r.name.startsWith('file:') && !r.name.startsWith('data:')).length", sid), 0, "no network request")

    def test_published_board_in_a_to_client_file_opens_in_chrome(self):
        """AP7: the file the To client route really writes (POST /api/publish with to_client, the dialogs answered by the Rig, no osascript) is opened in Chrome."""
        rig = Rig(self)
        with rig.store.step("dashboard", "Sam Carter") as st:
            st.update("projects", "PUB", {"show_board_client": 1})
        status, got = rig.publish(to_client=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        client = rig.client / WANTED
        for w in (1400, 900):
            with chrome() as cdp:
                sid = self.page(cdp, client, w)
                self.assertEqual(cdp.js("[...document.querySelectorAll('#layout-seg button')].map(b => b.textContent)", sid), ["List", "Board"], f"{w}: the client copy offers List and Board")
                rows = sorted(ids_of(cdp, sid, "#work-list tr[data-id]"))
                self.to_board(cdp, sid)
                self.assertEqual(sorted(ids_of(cdp, sid, "#work-board article[data-id]")), rows, f"{w}: the board shows the list's rows")
                cdp.js("window.dispatchEvent(new Event('beforeprint'))", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.print-tab #work-board').length === 0 && document.querySelectorAll('.print-tab #work-list tr[data-id]').length > 0", sid)), f"{w}: print is the list")


if __name__ == "__main__":
    unittest.main()
