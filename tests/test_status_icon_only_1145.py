"""Row 1145: a Work items list shows the tinted letter icon ALONE as its first column (no status words, no coloured pill), the design
the dashboard lists use (components/ItemRows.jsx). The status stays in the icon's tooltip and accessible name (colour is not the only signal),
and the icon is reachable from the keyboard.

Run: python3 dev/run_tests.py test_status_icon_only_1145
The Work items page, at 1400 and 900 px, light and dark.
"""
import unittest

from _paths import ROOT, SRC  # noqa: F401
import test_filter_line_page as _base  # noqa: E402
from test_server import chrome  # noqa: E402

ROWS = r"""[...document.querySelectorAll('#work tbody tr[data-id]')].map(r => {
  const td = r.firstElementChild, ico = td && td.querySelector('.ico');
  return {id: r.dataset.id, cls: td && td.className, pills: r.querySelectorAll('.pill').length, text: td ? td.textContent.trim() : '',
          has: !!ico, tip: (ico && ico.closest('[data-tip]') || {dataset: {}}).dataset.tip,
          name: ico && (ico.getAttribute('aria-label') || (ico.closest('button') || {getAttribute: () => ''}).getAttribute('aria-label')),
          tab: ico && (ico.closest('button, [tabindex]') || {tabIndex: 99}).tabIndex,
          letters: r.querySelectorAll('.kb').length, w: ico ? Math.round(ico.getBoundingClientRect().width) : 0};
})"""
HEAD = "[...document.querySelectorAll('#work thead th[class^=c-]')].map(h => h.className.split(' ')[0])"


class IconOnly(_base.Line):
    def test_work_items_status_is_the_icon_alone_and_first(self):
        s = self.serve()
        with chrome() as cdp:
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    sid = self.load(cdp, s.port, width=width, theme=theme)
                    if width == 1400:
                        self.assertEqual(cdp.js(HEAD, sid)[0], "c-status", "the Status column is first")
                    rows = cdp.js(ROWS, sid)
                    self.assertTrue(rows)
                    for r in rows:
                        where = f"{r['id']} {width} {theme}"
                        self.assertEqual(r["cls"], "c-status", where)
                        self.assertTrue(r["has"], where)
                        self.assertEqual(r["pills"], 0, f"no coloured pill with words: {where}")
                        self.assertEqual(len(r["text"]), 1, f"the icon holds its letter and no word: {where} {r['text']!r}")
                        self.assertEqual(r["letters"], 0, f"no second letter badge: {where}")
                        self.assertTrue(r["tip"] and " · " in r["tip"], f"tooltip carries the status: {where}")
                        self.assertTrue(r["name"], where)
                        self.assertIn(r["tab"], (0, -1), f"keyboard reachable (the row's arrow keys reach a button at -1): {where}")
                        self.assertEqual(r["w"], 24, where)


for _name in dir(_base.Line):             # only the test above runs here
    if _name.startswith("test_") and _name not in IconOnly.__dict__:
        setattr(IconOnly, _name, unittest.skip("inherited: runs in its own file")(lambda self: None))


if __name__ == "__main__":
    unittest.main()
