"""Row 1571 (DoD-2): the left-out line is drawn on the page, in the Classic theme, light and dark, at 1400 and 900. A real browser, the real page, the real
service; the answer comes from a STUB provider (nothing calls a model) and the project data says how many rows were read and left out.
Fictional data only.

Run: python3 dev/run_tests.py test_ask_left_out_page_1571
"""
import re
import unittest
from dataclasses import replace
from unittest import mock

from test_ask_change_page import Card
from test_server import chrome
from clark import ask, ask_data

SENTENCE = "A higher size of one question in Settings reads more."
OLD = "Left out to keep this question under the size limit"
CUT = (("actions", 30, 50), ("milestones", 5, 5), ("use_cases", 2, 4))      # 37 read, 22 left out
LEFT = 4                                                                    # 4 passages offered, MAX_PASSAGES 2: all 4 are counted as left out
FULL = (("actions", 4, 4), ("milestones", 2, 2))
LINES = "[...document.querySelectorAll('#ask-panel [data-ask-notes] li')].map(e => e.textContent)"
SEEN = """[...document.querySelectorAll('#ask-panel [data-ask-notes] li')].map(e => { const c = getComputedStyle(e), r = e.getBoundingClientRect(), q = document.querySelector('#ask-panel').getBoundingClientRect();
  return {on: e.offsetParent !== null, w: r.width, h: r.height, display: c.display, visibility: c.visibility, opacity: c.opacity, clip: c.textOverflow, space: c.whiteSpace,
          shown: e.innerText.replace(/\\s+/g, ' ').trim(), text: e.textContent.replace(/\\s+/g, ' ').trim(), scroll: e.scrollWidth, client: e.clientWidth,
          inside: r.left >= q.left - 1 && r.right <= q.right + 1}; })"""


class LeftOut(Card):
    THEME = "prototype-2.0"

    def counted(self, counts, passages=0):
        real = ask_data.project_data
        patch = mock.patch.object(ask_data, "project_data", lambda *a, **k: replace(real(*a, **k), counts=counts))
        patch.start()
        self.addCleanup(patch.stop)
        files = ()
        if passages:
            files = tuple(ask.Passage(f"f{i}.md", f"plan number {i}") for i in range(passages))
            cap = mock.patch.object(ask, "MAX_PASSAGES", 2)
            cap.start()
            self.addCleanup(cap.stop)
        self.says("Fine.", files=files)

    def drawn(self, rows, old, left=None):
        """rows: the exact rows sentence or None; old: whether the passages sentence shows; left: how many passages it says were left out."""
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p, "What is the state of the plan?")
            p.until("!!document.querySelector('[data-ask-notes]')" if (rows or old) else "!!document.querySelector('.ask-turn.assistant')", "the answer")
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for theme in ("light", "dark"):
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    where = f"{width} {theme}"
                    lines = p.js(LINES)
                    self.assertEqual([n for n in lines if SENTENCE in n], [rows] if rows else [], f"{where}: rows line in {lines}")
                    olds = [n for n in lines if n.startswith(OLD)]
                    self.assertEqual(len(olds), 1 if old else 0, f"{where}: passages line in {lines}")
                    if old:
                        self.assertEqual(olds[0], f"{OLD}: {left} passage{'' if left == 1 else 's'}.", f"{where}: the passages sentence with its own count")
                        self.assertEqual(re.findall(r"\d[\d,]*", olds[0]), [str(left)], f"{where}: only its own count")
                    if rows:
                        self.assertEqual(re.findall(r"\d[\d,]*", rows), ["37", "22"])
                        self.assertNotIn("passage", rows)
                        self.assertEqual(sum(n.count("items read") for n in lines), 1, f"{where}: the rows count is said once")
                    if rows or old:
                        box = p.js("(() => { const n = document.querySelector('#ask-panel [data-ask-notes]'), r = n.getBoundingClientRect(), q = document.querySelector('#ask-panel').getBoundingClientRect();"
                                   " return {w: r.width, h: r.height, inside: r.left >= q.left - 1 && r.right <= q.right + 1, scroll: document.documentElement.scrollWidth <= window.innerWidth}; })()")
                        self.assertTrue(box["w"] > 0 and box["h"] > 0, f"{where}: drawn {box}")
                        self.assertTrue(box["inside"], f"{where}: inside the panel {box}")
                        self.assertTrue(box["scroll"], f"{where}: no sideways scroll")
                        for k, seen in enumerate(p.js(SEEN)):
                            self.assertTrue(seen["on"] and seen["w"] > 0 and seen["h"] > 0, f"{where}: line {k} is drawn {seen}")
                            self.assertEqual((seen["display"], seen["visibility"]), ("list-item", "visible"), f"{where}: line {k} {seen}")
                            self.assertGreater(float(seen["opacity"]), 0.5, f"{where}: line {k} is not faded out {seen}")
                            self.assertNotEqual(seen["clip"], "ellipsis", f"{where}: line {k} is not cut with dots {seen}")
                            self.assertNotEqual(seen["space"], "nowrap", f"{where}: line {k} wraps {seen}")
                            self.assertEqual(seen["shown"], seen["text"], f"{where}: line {k} shows all its words {seen}")
                            self.assertLessEqual(seen["scroll"], seen["client"] + 1, f"{where}: line {k} is not clipped {seen}")
                            self.assertTrue(seen["inside"], f"{where}: line {k} inside the panel {seen}")

    def test_the_rows_line_is_drawn_at_1400_and_900(self):
        self.counted(CUT)
        self.drawn(f"37 items read, 22 left out. {SENTENCE}", False)

    def test_a_mixed_cut_draws_each_line_once_at_1400_and_900(self):
        self.counted(CUT, passages=4)
        self.drawn(f"37 items read, 22 left out. {SENTENCE}", True, LEFT)

    def test_a_passages_cut_draws_only_the_old_line_at_1400_and_900(self):
        self.counted(FULL, passages=4)
        self.drawn(None, True, LEFT)

    def test_no_cut_draws_no_left_out_line_at_1400_and_900(self):
        self.counted(FULL)
        self.drawn(None, False)


if __name__ == "__main__":
    unittest.main()
