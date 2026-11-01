"""#456: the Work items table matches the prototype: a letter badge in the Item cell and no Type column, a Client-visible eye column,
each group its own bordered card. (This also ends the word "Dependency" breaking in a Type column at 900 px: there is none.)

Run: python3 dev/run_tests.py test_work_table_parity
Source part (no Chrome): the page's source holds no Type column, the stylesheet has the badge and the card, and the published
file's code carries none of the eye's words. Browser part (Chrome required, set CLARK_CHROME): the real page and a real server over
the fictional demo data, at 1400 and 900 px, light and dark, in View and in Edit: the badge letters, the columns, the cards, the
eye's state and its click with Undo, and no eye or client word in a published file. Prototype: system/prototype/views.js `listHtml`.
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER
from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import changes, page, server as sv  # noqa: E402
from clark.store import open_store  # noqa: E402
from test_inline_edits import click  # noqa: E402
from test_server import CHROME, Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, MODULE, bundled, load_demo, page_target  # noqa: E402

PAGE = SRC / "clark" / "page"
SHELL = PAGE / "shell.css"
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
LETTERS = {"action": "A", "risk": "R", "issue": "I", "assumption": "S", "dependency": "P", "decision": "D"}
WORDS = {"action": "Action", "risk": "Risk", "issue": "Issue", "assumption": "Assumption", "dependency": "Dependency", "decision": "Decision"}


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


class Source(unittest.TestCase):
    """No Chrome."""

    def test_the_table_has_no_type_column_and_the_stylesheet_has_the_badge_and_the_card(self):
        jsx = (PAGE / "src" / "components" / "WorkItems.jsx").read_text(encoding="utf-8")
        css = SHELL.read_text(encoding="utf-8")
        self.assertNotIn("c-type", jsx)
        self.assertNotIn("c-type", css.replace(".wil-c-type", ""), "the stylesheet keeps no Type column rule for this table")
        self.assertNotIn(">Type<", jsx)
        self.assertRegex(css, r"\.kb \{[^}]*width: 22px; height: 22px")
        card = re.search(r"\.wgroup \{([^}]*)\}", css)
        self.assertTrue(card and "border: 1px solid" in card.group(1) and "border-radius" in card.group(1), "each group is a bordered, rounded card")

    def test_the_published_file_carries_no_eye_and_none_of_its_words(self):
        view = (PAGE / "page-view.html").read_text(encoding="utf-8")
        for word in ("data-weye", "Client-visible", "hidden from the client.", "Select to show the client", "Not shown to the client"):
            self.assertNotIn(word, view, f"the published file holds the editor's eye: {word!r}")
        editor = (PAGE / "page.html").read_text(encoding="utf-8")
        self.assertIn("Client-visible", editor, "the page clark serves has the eye")
        self.assertIn("Select to show the client", editor)

    def test_the_eye_uses_the_routes_the_report_already_has_so_no_guarded_file_changed(self):
        eye = (PAGE / "src" / "edit" / "cells" / "Eye.jsx").read_text(encoding="utf-8")
        for op in ('op: "new"', 'op: "delete"', 'op: "pick"'):
            self.assertIn(op, eye)
        self.assertNotIn("client_visible:", eye, "the item's own flag is never written by the page directly")


class Letters(unittest.TestCase):
    """The badge letters, from the page's own function in Chrome."""

    def test_each_kind_has_its_own_letter(self):
        assert Path(CHROME).is_file(), f"Google Chrome is needed for the required browser tests ({CHROME}); set CLARK_CHROME"
        script = bundled(MODULE) + ";\n(" + "() => Object.fromEntries(Object.keys(WI.KIND_WORDS).map((k) => [k, WI.kindLetter(k)])))()"
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            self.assertNotIn("exceptionDetails", res, res)
            got = res["result"]["value"]
        self.assertEqual(got, LETTERS)
        self.assertEqual({got[k] for k in ("action", "risk", "issue", "decision")}, {"A", "R", "I", "D"}, "the prototype's four")
        self.assertEqual(len(set(got.values())), len(got), "no two kinds share a letter")


# The table as drawn: the columns, each card and its borders, each row's badge and eye.
MEASURE = r"""(() => {
  const heads = [...document.querySelectorAll('#work table.items th')].filter((t) => !t.closest('tr.grp')).map((t) => t.textContent.trim());
  const cards = [...document.querySelectorAll('#work .wgroup')].map((c) => { const s = getComputedStyle(c), t = c.querySelector('table.items');
    return { bw: s.borderTopWidth, radius: parseFloat(s.borderTopLeftRadius), tables: c.querySelectorAll('table.items').length, groups: c.querySelectorAll('tbody[data-group]').length,
             inside: !!t && t.getBoundingClientRect().right <= c.getBoundingClientRect().right + 1, head: !!c.querySelector('tr.grp .grp-b') }; });
  const rows = [...document.querySelectorAll('#work tr[data-id]')].map((r) => { const k = r.querySelector('.c-item .kb'), e = r.querySelector('.c-eye .weye'), b = k && k.getBoundingClientRect();
    return { id: r.dataset.id, kind: r.dataset.kind, letter: k ? k.textContent : null, label: k ? k.getAttribute('aria-label') : null, title: k ? k.getAttribute('title') : null,
             w: b ? Math.round(b.width) : 0, h: b ? Math.round(b.height) : 0, eye: e ? e.getAttribute('aria-pressed') : null, eyeLabel: e ? e.getAttribute('aria-label') : null,
             tag: !!r.querySelector('.tag.cl'), type: !!r.querySelector('.c-type') }; });
  const wide = [...document.querySelectorAll('#work table.items tbody td')].filter((e) => e.scrollWidth > e.clientWidth + 1).map((e) => e.className);
  return JSON.stringify({ heads, cards, rows, wide, sw: document.documentElement.scrollWidth, vw: innerWidth });
})()"""


class Table(unittest.TestCase):
    def setUp(self):
        assert Path(CHROME).is_file(), f"Google Chrome is needed for the required browser tests ({CHROME}); set CLARK_CHROME"
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.s = Running(data_for=self.read, projects=lambda: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(EMPTY_BRANDING),
                         change=changes.make_change(self.path, [], USER), undo=changes.make_undo(self.path, [], USER))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code)
        finally:
            st.close()

    def hidden(self):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return {r["item_id"] for r in st.con.execute("SELECT item_id FROM report_hidden")}
        finally:
            st.close()

    def open(self, cdp, width, mode="view", theme="light"):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#work&p=TUL&f=mode:all"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0), "the list drew")
        cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
        if mode == "edit":
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-cell]')", sid)), "Edit shows the cells' pickers")
        return sid

    def measure(self, cdp, sid):
        return json.loads(cdp.js(MEASURE, sid))

    def test_letter_badge_no_type_column_eye_column_and_a_card_per_group_in_both_modes_and_themes(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for mode in ("view", "edit"):
                    for theme in ("light", "dark"):
                        where = f"{width} px, {mode}, {theme}"
                        got = self.measure(cdp, self.open(cdp, width, mode, theme))
                        self.assertNotIn("Type", got["heads"], where + ": no Type column")
                        self.assertEqual(set(got["heads"]), {"Item", "Owner", "Due", "Priority", "Status", "Client-visible"}, where)
                        self.assertGreater(len(got["cards"]), 1, where + ": more than one group")
                        for c in got["cards"]:
                            self.assertEqual((c["bw"], c["tables"], c["groups"], c["head"], c["inside"]), ("1px", 1, 1, True, True), f"{where}: a group is a card of its own")
                            self.assertGreaterEqual(c["radius"], 8, where + ": the card is rounded")
                        kinds = set()
                        for r in got["rows"]:
                            kinds.add(r["kind"])
                            self.assertEqual((r["letter"], r["label"], r["title"]), (LETTERS[r["kind"]], WORDS[r["kind"]], WORDS[r["kind"]]), f"{where}: {r['id']}")
                            self.assertEqual((r["w"], r["h"]), (22, 22), f"{where}: {r['id']} badge is one 22 px square, never a broken word")
                            self.assertIn(r["eye"], ("true", "false"), f"{where}: {r['id']} has its eye")
                            self.assertFalse(r["tag"] or r["type"], f"{where}: {r['id']} has no 'Shown to client' tag and no Type cell")
                        self.assertIn("dependency", kinds, where + ": the longest old Type word is on the page")
                        self.assertEqual(got["wide"], [], where + ": a cell has text wider than its box")
                        self.assertLessEqual(got["sw"], got["vw"], where + ": the page scrolls sideways")

    def test_the_eye_shows_who_the_client_sees(self):
        with chrome() as cdp:
            got = {r["id"]: r for r in self.measure(cdp, self.open(cdp, 1400))["rows"]}
        self.assertEqual((got["TUL-A-002"]["eye"], got["TUL-A-004"]["eye"]), ("true", "false"), "A-002 is shown to the client, A-004 is not")
        self.assertEqual(got["TUL-A-001"]["eye"], "false", "A-001 has the client flag on but carries the Sensitive label, so a publish leaves it out and the eye says so")
        self.assertTrue(got["TUL-A-002"]["eyeLabel"].startswith("Shown to the client: "))
        self.assertTrue(got["TUL-A-004"]["eyeLabel"].startswith("Not shown to the client: "))

    def test_the_eye_turns_an_item_off_and_on_with_a_toast_and_undo_in_view(self):
        ref, eye = "TUL-A-002", "tr[data-id='TUL-A-002'] .weye"
        with chrome() as cdp:
            sid = self.open(cdp, 1400)
            self.assertEqual(self.hidden(), set())
            click(cdp, sid, eye)
            self.assertTrue(wait(lambda: cdp.js(f"document.querySelector({json.dumps(eye)}).getAttribute('aria-pressed') === 'false'", sid)), "the eye turned off")
            self.assertEqual(self.hidden(), {ref}, "the item is hidden from the report, in the store")
            self.assertEqual(cdp.js("document.querySelector('.toast-text').textContent", sid), f"{ref} hidden from the client.")
            self.assertEqual(cdp.js("document.querySelector('#peek') ? 1 : 0", sid), 0, "a click on the eye does not open the peek")
            click(cdp, sid, "[data-undo]")
            self.assertTrue(wait(lambda: cdp.js(f"document.querySelector({json.dumps(eye)}).getAttribute('aria-pressed') === 'true'", sid)), "Undo turned it on again")
            self.assertEqual(self.hidden(), set())
            click(cdp, sid, eye)
            self.assertTrue(wait(lambda: self.hidden() == {ref}), "hidden again")
            click(cdp, sid, eye)
            self.assertTrue(wait(lambda: cdp.js(f"document.querySelector({json.dumps(eye)}).getAttribute('aria-pressed') === 'true'", sid)), "the eye turned it on")
            self.assertEqual(self.hidden(), set())
            self.assertEqual(cdp.js("document.querySelector('.toast-text').textContent", sid), f"{ref} shown to the client.")

    def test_the_eye_turns_an_item_on_by_its_own_flag_and_refuses_a_sensitive_one_in_words(self):
        eye = "tr[data-id='TUL-A-004'] .weye"
        with chrome() as cdp:
            sid = self.open(cdp, 1400)
            click(cdp, sid, eye)
            self.assertTrue(wait(lambda: cdp.js(f"document.querySelector({json.dumps(eye)}).getAttribute('aria-pressed') === 'true'", sid)), "the eye turned on")
            mine = {r["id"]: r for r in self.read("TUL")["actions"]}
            self.assertEqual(mine["TUL-A-004"]["client_visible"], 1, "the item's own flag is on")
            click(cdp, sid, "tr[data-id='TUL-A-001'] .weye")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.toast-text') && /ensitive/.test(document.querySelector('.toast-text').textContent)", sid)),
                            "a Sensitive item is refused in plain words")
            self.assertEqual(cdp.js("document.querySelector(\"tr[data-id='TUL-A-001'] .weye\").getAttribute('aria-pressed')", sid), "false")

    def test_the_arrow_keys_reach_the_eye_and_the_table_stays_one_tab_stop(self):
        with chrome() as cdp:
            sid = self.open(cdp, 1400)
            stops = cdp.js("[...document.querySelectorAll('#work table.items *')].filter(e => e.tabIndex >= 0 && !e.disabled && !e.closest('tr.grp')).length", sid)
            self.assertEqual(stops, 1, "one tab stop")
            cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
            cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39}, sid)
            cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39}, sid)
            self.assertEqual(cdp.js("document.activeElement.className", sid), "ib weye", "Right from a row, in View, reaches the eye")

    def test_a_published_file_has_no_eye_and_no_client_column(self):
        import _publish_fixture as fx
        from clark import publish
        from test_client_page_filters import plant
        tmp = Path(tempfile.mkdtemp(prefix="clark-pub-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        store = open_store(fx.build_db(tmp / "c.db", plant()), onedrive_roots=[])
        self.addCleanup(store.close)
        out = tmp / "out"
        out.mkdir()
        path = Path(publish.publish(store, "PUB", out, by_user="Demo User", now="2026-10-28", branding=EMPTY_BRANDING)["path"])
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": path.as_uri() + "#work"}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tr[data-id]').length", sid) > 0), "the list drew")
            got = self.measure(cdp, sid)
            self.assertNotIn("Client-visible", got["heads"])
            self.assertNotIn("Type", got["heads"])
            self.assertEqual([r["eye"] for r in got["rows"] if r["eye"]], [], "no eye on any row")
            self.assertTrue(all(r["letter"] for r in got["rows"]), "the badge is there")
            self.assertFalse(cdp.js("!!document.querySelector('.weye, .c-eye, .tag.cl')", sid))
            self.assertGreater(len(got["cards"]), 0)
            html = path.read_text(encoding="utf-8")
            self.assertNotIn("data-weye", html)
            self.assertNotIn("Client-visible", html)


if __name__ == "__main__":
    unittest.main()
