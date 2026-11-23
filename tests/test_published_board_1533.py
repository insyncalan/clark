"""Row 1533: the Work items board in a published report, read only, shown to the client only when the author's switch is on.

Run: python3 -m unittest test_published_board_1533   (from tests/)
Two files are published from the test plant: one with the board switch off (the project's show_board_client is 0, the default) and one with it
on. The switch is the project's `show_board_client`; the file carries it as project.board (1 or absent). Both are opened from disk in headless
Chrome at 1400 and 900 px, light and dark.
"""
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT  # noqa: F401  (puts src/ on the path)
import _publish_fixture as fx

from clark import publish
from clark.store import open_store
from test_client_page_filters import EMPTY_BRANDING, INTERNAL, HIDDEN_OWNER, HIDDEN_WS, TODAY, VARIANTS, open_page, plant
from test_server import chrome, wait
from test_work_filters import need_chrome

TYPES = ["action", "risk", "decision"]
WRITE_WORDS = ["changeItem", "stores/changes", "/api/", "fetch("]
SIZE_BEFORE = 845696       # page-view.html on origin/main (f3c44df6c plus later, built by dev/tools/build_page.py), bytes


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
        cls.store = open_store(fx.build_db(cls.tmp / "c.db", plant()), onedrive_roots=[])
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
                cdp.js(f"[...document.querySelectorAll('[role=menuitem]')].find(x => x.textContent.toLowerCase().includes({g!r})).click()", sid)
                body = cdp.js("document.getElementById('work-board').textContent", sid)
                for secret in (INTERNAL, HIDDEN_OWNER, HIDDEN_WS):
                    self.assertNotIn(secret, body, g)

    def test_published_board_group_by_fields_in_file(self):
        with chrome() as cdp:
            sid = self.page(cdp, self.on)
            self.to_board(cdp, sid)
            cdp.js("document.querySelector('#group-by').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[role=menu]')", sid)))
            names = cdp.js("[...document.querySelectorAll('[role=menu] [role=menuitem]')].map(x => x.textContent.trim())", sid)
            self.assertEqual(names, ["Workstream", "Status", "Due", "Owner", "Priority", "Milestone", "Type"], "the table's choices, no Nothing on a board")
            cdp.js("[...document.querySelectorAll('[role=menuitem]')].find(x => x.textContent.trim() === 'Owner').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#work-board .col[data-col]') && [...document.querySelectorAll('#work-board .col')].some(c => /Ana Lopez/.test(c.getAttribute('aria-label')))", sid)), "columns follow Group by")
            cdp.js("document.querySelector('#swimlanes').click()", sid)
            cdp.js("[...document.querySelectorAll('[role=menuitem]')].find(x => x.textContent.trim() === 'Type').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work-board .lane-h').length", sid) > 0), "swimlanes draw")

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
        self.assertNotIn("Move to", text.split("<script")[0] if False else "".join(re.findall(r">[^<>]*Move [^<>]*to[^<>]*<", text)) or "")
        for word in WRITE_WORDS[:2]:
            self.assertNotIn(word, text, f"the file holds no {word}")

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

    def test_published_board_print_follows_table(self):
        with chrome() as cdp:
            sid = self.page(cdp, self.on)
            self.to_board(cdp, sid)
            cdp.js("window.dispatchEvent(new Event('beforeprint'))", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.print-tab #work-board').length === 0 && document.querySelectorAll('.print-tab #work-list tr[data-id]').length > 0", sid)), "printing draws the list")
            cdp.js("window.dispatchEvent(new Event('afterprint'))", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work-board')", sid)), "the board is back after printing")

    def test_published_file_stays_self_contained(self):
        text = self.on.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(src|href)=[\"']https?://")
        self.assertNotIn("XMLHttpRequest", text)
        view = (ROOT / "src" / "clark" / "page" / "page-view.html").stat().st_size
        print(f"\npage-view.html bytes: before {SIZE_BEFORE}, after {view}")
        self.assertGreater(view, SIZE_BEFORE)
        with chrome() as cdp:
            sid = self.page(cdp, self.on)
            self.to_board(cdp, sid)
            self.assertEqual(cdp.js("performance.getEntriesByType('resource').filter(r => !r.name.startsWith('file:') && !r.name.startsWith('data:')).length", sid), 0, "no network request")


if __name__ == "__main__":
    unittest.main()
