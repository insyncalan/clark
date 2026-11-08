"""Plan #1022: in the item rows (Risks and issues, Open actions, Decisions) and in the RAID cards, an ID, a date and an owner
never wrap and never run over the line below; only the title is cut, with an ellipsis.

Run: python3 dev/run_tests.py test_row_ids_no_wrap
A real browser over a real store of fictional rows (project LONGPRJ: a 13-character ID, a very long title with spaces, a title
with no space in it, a long owner name). Each part is measured as drawn, at 360 and 1400 px: its box is one line high (a wrapped
flex item still has one client rect, so the height is measured, not the rect count), it ends inside its row or card, and the
rows and cards are not wider than the screen. The same is read on the page clark serves (View, Edit) and on the published file, which carries
shell.css inlined: so the file is the proof for any rule in that sheet.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import TOOLS

sys.path.insert(0, str(TOOLS))
from clark import changes, page, publish  # noqa: E402
from test_report_editor import EMPTY_BRANDING, Pg  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

CODE = "LONGPRJ"
LONG_OWNER = "Bartholomew Featherstone-Hall"
LONG_WORDS = ("Confirm the whole cut-over plan with every supplier, the hosting team and the steering group before the freeze "
              "and write down who signs off each step of the move, in order, with the dates they agreed to ") * 2
NO_SPACE = "Supercalifragilisticexpialidocious" * 5

# One line high: the height of the box less its own padding and border is at most 1.4 lines. A wrapped flex item is still one client
# rect, so the rect count says nothing.
ONE_LINE = """function oneLine(e) {
  var cs = getComputedStyle(e), r = e.getBoundingClientRect();
  var lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.3;
  var pad = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom) + parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth);
  return r.height - pad <= lh * 1.4;
}"""


def seed(store):
    with store.step("dashboard", USER) as st:
        st.create("projects", {"code": CODE, "name": "Long ids", "health": "On track"})
        a = st.create("actions", {"project": CODE, "description": LONG_WORDS, "owner": LONG_OWNER, "due_date": "2026-11-20",
                                  "raised": "2026-10-01", "client_message": LONG_WORDS, "source": "demo"})
        b = st.create("actions", {"project": CODE, "description": NO_SPACE, "owner": "Sara Khan", "due_date": "2026-11-21",
                                  "raised": "2026-10-01", "client_message": NO_SPACE, "source": "demo"})
        r = st.create("raid", {"project": CODE, "type": "Risk", "description": LONG_WORDS, "owner": LONG_OWNER, "due_date": "2026-11-22",
                               "impact": "High", "likelihood": "High", "raised": "2026-10-01", "client_message": LONG_WORDS, "source": "demo"})
        d = st.create("decisions", {"project": CODE, "decision": LONG_WORDS, "made_by": LONG_OWNER, "needed_by": "2026-11-23",
                                    "status": "Pending", "client_message": LONG_WORDS, "source": "demo"})
        for kind, n in (("raid3", 3), ("raid4", 4)):
            ref = st.create("report_sections", {"project": CODE, "type": kind, "title": "Fictional cards %d" % n, "sort_order": 990 + n})
            st.update("report_sections", ref, {"body": json.dumps({"v": 1, "cards": [{"id": i, "source": "client"} for i in (a, b, r, d)[:n]]})})


# (selector of the row or card, the parts that never wrap, the title)
ROWS = (".wl-row", ".wl-id, .wl-id .idl, .wl-meta > span", ".wl-title")
CARDS = (".raid-card", ".raid-id, .raid-meta .raid-bit", ".raid-title")


def check(test, js, surface, where, width):
    box, parts, title = surface
    n = js(f"document.querySelectorAll({box!r}).length")
    test.assertGreater(n, 0, f"{where}: {box} drawn")
    test.assertGreater(js(f"document.querySelectorAll({box!r} + ' ' + {parts.split(',')[-1].strip()!r}).length"), 0, f"{where}: {parts} drawn")
    bad = js("(function(){" + ONE_LINE + f"""
      var out = [];
      document.querySelectorAll({box!r}).forEach(function (row) {{
        var edge = row.getBoundingClientRect().right + 1;
        row.querySelectorAll({parts!r}).forEach(function (e) {{
          if (!e.classList.contains("wl-id") && e.scrollWidth > e.clientWidth + 1) out.push('is cut: ' + e.className + ' ' + e.textContent.slice(0, 30));
          if (!oneLine(e)) out.push('wraps: ' + e.className + ' ' + e.textContent.slice(0, 30));
          if (e.getBoundingClientRect().right > edge + (e.classList.contains('idl') ? 4 : 0)) out.push('runs over: ' + e.className + ' ' + e.textContent.slice(0, 30));
        }});
        var t = row.querySelector({title!r});
        if (!oneLine(t)) out.push('title wraps');
        var cut = [t].concat([].slice.call(t.querySelectorAll('*'))).filter(function (e) {{ return e.scrollWidth > e.clientWidth + 1; }});
        cut.forEach(function (e) {{
          var cs = getComputedStyle(e);
          if (cs.textOverflow !== 'ellipsis' || cs.overflowX !== 'hidden') out.push('title is cut without an ellipsis: ' + e.className);
        }});
        if (t.getBoundingClientRect().right > edge) out.push('title runs over');
      }});
      document.querySelectorAll({box!r}).forEach(function (row) {{
        if (row.getBoundingClientRect().right > document.documentElement.clientWidth + 1) out.push('a ' + {box!r} + ' is wider than the screen');
      }});
      return out;
    }})()""")
    test.assertEqual(bad, [], f"{where} at {width}: {bad}")


class RowIds(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        seed(self.store)

    def served(self):
        s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING),
                    change=changes.make_change(self.store.path, [], USER), undo=changes.make_undo(self.store.path, [], USER))
        self.addCleanup(s.close)
        return s

    def width(self, p, w):
        p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)

    def test_the_served_page_in_view_and_in_edit(self):
        s = self.served()
        with chrome() as cdp:
            p = Pg.at(self, cdp, s.port, f"#dashboard&p={CODE}")
            p.ready()
            for w in (360, 1400):
                self.width(p, w)
                p.until(f"document.documentElement.clientWidth === {w} || document.documentElement.clientWidth < {w}", "resized")
                check(self, p.js, ROWS, "View rows", w)
                check(self, p.js, CARDS, "View cards", w)
            p.edit()
            for w in (360, 1400):
                self.width(p, w)
                p.until("document.querySelectorAll('.item-rows-edit .wl-row').length > 0", "Edit rows")
                check(self, p.js, ROWS, "Edit rows", w)

    def test_the_published_file(self):
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(self.store, CODE, folder, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            p = Pg(self, cdp, sid)
            for w in (360, 1400):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.wl-row').length > 0 && document.querySelectorAll('.raid-card').length > 0", sid)),
                                "the file drew its rows and cards")
                check(self, p.js, ROWS, "File rows", w)
                check(self, p.js, CARDS, "File cards", w)
                self.assertEqual(p.js("document.querySelectorAll('.wl-id').length"), 0, "a file draws no item number in its rows")


if __name__ == "__main__":
    unittest.main()
