"""Keyboard and name pass on the Settings menu, the filter line and the saved-view tabs, at 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_a11y_settings_filter_tabs
Real keys (Tab, Shift+Tab, Arrow keys, Enter, Esc) go to the real page over the fictional demo data. Checked: every control is reached by Tab in the order it
is drawn and has a name; none has a tab stop above 0; each shows a focus ring (computed outline or shadow, not none) in both themes; the menus are role=menu
with named items; Esc closes the tab's menu with the focus back on its button; Move view works with the arrow keys; after Duplicate, Delete view, Move view and
removing a chip the focus is on a control, never on the body. Chrome is required.
"""
import json
import time
import unittest

import test_filter_line_keys as K
from test_filter_line_keys import tearDownModule  # noqa: F401
from test_server import chrome, wait

K.KEYS.setdefault("ArrowLeft", ("ArrowLeft", 37))
THEMES = ("light", "dark")

RING = r"""(() => { const a = document.activeElement; if (!a || a === document.body) return JSON.stringify({ body: true });
  const cs = getComputedStyle(a), field = a.tagName === 'INPUT' && !!a.closest('.fline');   // issue 1137: the filter field shows no focus mark by the ruling (see test_filter_line_focus_look.py)
  return JSON.stringify({ name: a.getAttribute('aria-label') || a.textContent.trim().slice(0, 30), id: a.id || '', visible: a.matches(':focus-visible'), inLine: !!a.closest('.fviews, .fline-wrap'),
    ring: field || (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 1) || (cs.boxShadow !== 'none' && cs.boxShadow !== '') }); })()"""
UNNAMED = r"""(() => { const out = [];
  for (const e of document.querySelectorAll('.fviews button, .fline button, .fline input, .vicons button, .set-bar button, .ddmenu [role^=menuitem]')) {
    if (!e.getClientRects().length) continue;
    const name = (e.getAttribute('aria-label') || e.textContent || '').trim();
    if (!name) out.push(e.outerHTML.slice(0, 80));
    if (e.tabIndex > 0) out.push('positive tab stop: ' + (name || e.id)); }
  return JSON.stringify(out); })()"""
VIEWS = "JSON.stringify([...document.querySelectorAll('.vtab')].map(e => e.dataset.viewId))"


class A11y(unittest.TestCase):
    setUp = K.Keys.setUp
    read = K.Keys.read
    open_page = K.Keys.open_page
    press = K.Keys.press
    who = K.Keys.who

    def theme(self, cdp, sid, mode):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": mode}]}, sid)

    def ring(self, cdp, sid):
        return json.loads(cdp.js(RING, sid))

    def keyboard_mode(self, cdp, sid):
        self.press(cdp, sid, "Tab")
        self.press(cdp, sid, "Tab", shift=True)

    def open_tab_menu(self, cdp, sid, where):
        time.sleep(0.3)      # the row scrolls the new open tab into view; a scroll closes a menu that is open, so let it finish first
        cdp.js("document.querySelector('#viewTabMenu').focus()", sid)
        self.press(cdp, sid, "Enter")
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewTabMenuList[role=menu]')", sid)), where + ": Enter opens the tab's menu (role=menu)")

    def pick(self, cdp, sid, name, where):
        """Arrow Down to the item with this name, then Enter."""
        for _ in range(12):
            if cdp.js("document.activeElement.textContent.trim()", sid) == name:
                break
            self.press(cdp, sid, "ArrowDown")
        self.assertEqual(cdp.js("document.activeElement.textContent.trim()", sid), name, where + ": the menu has " + name)
        self.press(cdp, sid, "Enter")

    def assert_focus_kept(self, cdp, sid, where):
        self.assertTrue(wait(lambda: not self.who(cdp, sid).get("body")), where + ": the focus is on a control, not lost to the page")

    def test_the_tabs_and_line_have_names_roles_rings_in_both_themes(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for mode in THEMES:
                    where = f"{width} px {mode}"
                    sid = self.open_page(cdp, width)
                    self.theme(cdp, sid, mode)
                    cdp.js("(() => { const i = document.querySelector('#fline-input'); i.focus(); document.execCommand('insertText', false, 'is:open '); })()", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-fx]')", sid)), where + ": a chip with its remove button")
                    self.assertEqual(json.loads(cdp.js(UNNAMED, sid)), [], where + ": every control has a name and no positive tab stop")
                    self.assertEqual(cdp.js("document.querySelector('.vtabs').getAttribute('role')", sid), "group", where)
                    self.assertTrue(cdp.js("!!document.querySelector('.vtabs').getAttribute('aria-label')", sid), where + ": the tabs are a named group")
                    self.assertTrue(cdp.js("[...document.querySelectorAll('.vtab')].every(b => b.hasAttribute('aria-pressed'))", sid), where + ": each tab says whether it is the chosen one")
                    self.assertEqual(cdp.js("(document.querySelector('#viewTabMenu') || {}).getAttribute('aria-haspopup')", sid), "menu", where)
                    self.assertEqual(cdp.js("document.querySelector('#fline-input').getAttribute('role')", sid), "combobox", where)
                    cdp.js("document.querySelector('.vtab').focus()", sid)
                    self.keyboard_mode(cdp, sid)
                    cdp.js("document.querySelector('.vtab').focus()", sid)
                    seen = []
                    for _ in range(60):
                        r = self.ring(cdp, sid)
                        if r.get("body") or not r["inLine"]:
                            break
                        self.assertTrue(r["visible"] and r["ring"], f"{where}: {r['name']} shows a focus ring")
                        seen.append(r["name"])
                        self.press(cdp, sid, "Tab")
                    self.assertTrue(any(n.startswith("Remove the") for n in seen), f"{where}: the chip's remove button is reached by Tab: {seen}")
                    self.assertTrue(any(n.startswith("Options for") for n in seen), f"{where}: the tab's options are reached by Tab: {seen}")
                    self.assertLess(next(i for i, n in enumerate(seen) if n.startswith("Options for")), seen.index("Filter work items"), where + ": tabs come before the line")
                    cdp.js("document.querySelector('[data-fx]').focus()", sid)
                    self.press(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: not cdp.js("document.querySelector('[data-fx]')", sid)), where + ": Enter removes the chip")
                    self.assertEqual(self.who(cdp, sid).get("id"), "fline-input", where + ": the focus goes to the box after a chip is removed")

    def test_the_tab_menu_has_roles_esc_returns_focus_and_every_action_keeps_the_focus(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for mode in THEMES:
                    where = f"{width} px {mode}"
                    sid = self.open_page(cdp, width)
                    self.theme(cdp, sid, mode)
                    self.keyboard_mode(cdp, sid)
                    self.open_tab_menu(cdp, sid, where)
                    items = json.loads(cdp.js("JSON.stringify([...document.querySelectorAll('#viewTabMenuList [role^=menuitem]')].map(e => e.textContent.trim()))", sid))
                    for want in ("Rename view", "Move view", "Duplicate view", "Delete view"):
                        self.assertIn(want, items, where)
                    self.assertTrue(cdp.js("!!document.querySelector('#viewTabMenuList').getAttribute('aria-label')", sid), where + ": the menu is named")
                    r = self.ring(cdp, sid)
                    self.assertTrue(r["visible"] and r["ring"], where + ": the first menu item shows a ring")
                    self.press(cdp, sid, "Escape")
                    self.assertTrue(wait(lambda: not cdp.js("document.querySelector('#viewTabMenuList[role=menu]')", sid)), where + ": Esc closes the menu")
                    self.assertEqual(self.who(cdp, sid).get("id"), "viewTabMenu", where + ": Esc returns the focus to the opener")
                    # Move view with the arrow keys
                    before = json.loads(cdp.js(VIEWS, sid))
                    self.assertGreater(len(before), 1, where)
                    cdp.js("document.querySelector('.vtab[aria-pressed=true]').click()", sid)
                    self.open_tab_menu(cdp, sid, where)
                    self.pick(cdp, sid, "Move view", where)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.vtab[data-moving]')", sid)), where + ": Move view picks the tab up")
                    self.assert_focus_kept(cdp, sid, where + " (Move view)")
                    time.sleep(0.2)      # the page hands the focus to the lifted tab a moment after Move view; a person never ends the move inside that time
                    moved = cdp.js("document.querySelector('.vtab[data-moving]').dataset.viewId", sid)
                    i = before.index(moved)
                    self.press(cdp, sid, "ArrowRight" if i < len(before) - 1 else "ArrowLeft")
                    self.assertTrue(wait(lambda: json.loads(cdp.js(VIEWS, sid)) != before), where + ": an arrow key moves the tab")
                    self.assert_focus_kept(cdp, sid, where + " (after an arrow move)")
                    self.press(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: not cdp.js("document.querySelector('.vtab[data-moving]')", sid)), where + ": Enter puts the tab down")
                    self.assert_focus_kept(cdp, sid, where + " (after Move view)")
                    # Duplicate, then Delete view
                    n = len(before)
                    self.open_tab_menu(cdp, sid, where)
                    ids = set(json.loads(cdp.js(VIEWS, sid)))
                    self.pick(cdp, sid, "Duplicate view", where)
                    self.assertTrue(wait(lambda: len(json.loads(cdp.js(VIEWS, sid))) == n + 1), where + ": Duplicate view adds a tab")
                    self.assert_focus_kept(cdp, sid, where + " (Duplicate view)")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.dataset.viewId", sid) not in ids | {None}), where + ": after Duplicate view the focus is on the copy's tab")
                    self.open_tab_menu(cdp, sid, where)
                    self.pick(cdp, sid, "Delete view", where)
                    self.assertTrue(wait(lambda: len(json.loads(cdp.js(VIEWS, sid))) == n), where + ": Delete view takes the tab away")
                    self.assert_focus_kept(cdp, sid, where + " (Delete view)")
                    cdp.js("document.querySelector('.vtab').click()", sid)
                    self.open_tab_menu(cdp, sid, where)
                    ids = set(json.loads(cdp.js(VIEWS, sid)))
                    self.pick(cdp, sid, "Save as a new view…", where)
                    self.assertTrue(wait(lambda: len(json.loads(cdp.js(VIEWS, sid))) == n + 1), where + ": Save as a new view adds a tab")
                    self.assert_focus_kept(cdp, sid, where + " (Save as a new view)")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.dataset.viewId", sid) not in ids | {None}), where + ": after Save as a new view the focus is on the new tab")
                    self.open_tab_menu(cdp, sid, where)      # leave the saved views as they were for the next width and theme
                    self.pick(cdp, sid, "Delete view", where)
                    self.assertTrue(wait(lambda: len(json.loads(cdp.js(VIEWS, sid))) == n), where + ": the extra tab is gone")

    def test_the_settings_menu_has_a_name_reaches_every_chip_by_tab_with_a_ring_and_keeps_the_focus(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for mode in THEMES:
                    where = f"{width} px {mode}"
                    sid = self.open_page(cdp, width)
                    self.theme(cdp, sid, mode)
                    cdp.js("location.hash = '#settings'", sid)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.set-chip').length > 2", sid)), where + ": Settings drew")
                    self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)))
                    self.assertTrue(cdp.js("!!document.querySelector('.set-bar').getAttribute('aria-label')", sid), where + ": the menu is named")
                    self.assertEqual(json.loads(cdp.js(UNNAMED, sid)), [], where)
                    names = json.loads(cdp.js("JSON.stringify([...document.querySelectorAll('.set-chip')].filter(e => e.getClientRects().length).map(e => e.textContent.trim()))", sid))
                    cdp.js("document.querySelector('.set-chip').focus()", sid)
                    self.keyboard_mode(cdp, sid)
                    cdp.js("document.querySelector('.set-chip').focus()", sid)
                    seen = []
                    for _ in range(len(names) + 1):
                        r = self.ring(cdp, sid)
                        if r.get("body") or r["name"] not in names:
                            break
                        self.assertTrue(r["visible"] and r["ring"], f"{where}: {r['name']} shows a focus ring")
                        seen.append(r["name"])
                        self.press(cdp, sid, "Tab")
                    self.assertEqual(seen, names, f"{where}: Tab reaches every entry in the drawn order")
                    cdp.js("document.querySelector('.set-chip').focus()", sid)
                    self.press(cdp, sid, "Enter")
                    self.assert_focus_kept(cdp, sid, where + " (a Settings entry chosen with Enter)")


if __name__ == "__main__":
    unittest.main()
