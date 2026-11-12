"""Row 756: pressing E (or V) on the Dashboard must not move the section being read (nor the top bar). Run: python3 dev/run_tests.py test_e_key_no_shift

Real browser. The page is scrolled to each section in turn, E is pressed (then V) and the section nearest the top is measured before and
after (within 1 px). On the committed test page and on the first-run demo data, with and without the demo banner, with a long project
name, at 1400 and 900 px, light and dark.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401
from clark import __main__ as launcher, demo_seed, page, store as clark_store
from test_report_editor import Base, Pg, tearDownModule  # noqa: F401
from test_server import Running, chrome

NEAREST = """(() => {
  const line = document.querySelector('.top').getBoundingClientRect().bottom;
  let best = null, most = 0;
  for (const e of document.querySelectorAll('.secs > .sec:not(.is-hidden)')) {
    const r = e.getBoundingClientRect(); const seen = Math.min(r.bottom, innerHeight) - Math.max(r.top, line);
    if (seen >= 64) return e.dataset.id;
    if (seen > most) { most = seen; best = e.dataset.id; }
  }
  return best;
})()"""

MEASURE = """((id) => {
  const top = (e) => e ? Math.round(e.getBoundingClientRect().top * 10) / 10 : null;
  return {id: id, title: (document.querySelector('.secs > .sec[data-id="' + id + '"] .sec-h') || {}).textContent, sec: top(document.querySelector('.secs > .sec[data-id="' + id + '"]')), top: top(document.querySelector('.top')), y: window.scrollY, h: document.documentElement.scrollHeight};
})"""

LONG = "A very long project name for the rehearsal programme " * 3


class DemoSeam:
    """Stands in for the demo seam: GET /api/demo says demo data is on show."""
    def status(self):
        return 200, {"ok": True, "demo": True}

    def remove(self, req=None):
        return 200, {"ok": True, "removed": 0}


class Walk:
    def watched(self, p, sid):
        """The first section with a real strip of itself under the top bar, and the one scrolled to just under the top bar."""
        ids = [p.js(NEAREST)]
        if sid and p.js("(() => { const e = document.querySelector('.secs > .sec[data-id=' + JSON.stringify(%s) + ']'); return !!e && e.getBoundingClientRect().top < 100; })()" % json.dumps(sid)):
            ids.append(sid)
        return list(dict.fromkeys(ids))

    def walk(self, width, dark, banner, long_name):
        """[(section, key, before, after)] for E then V with each section scrolled to the top of the screen in turn."""
        out = []
        with chrome() as cdp:
            p = self.start(cdp, banner, long_name)
            cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 450, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            if dark:
                p.js("document.documentElement.dataset.theme = 'dark'")
            if banner:
                p.until("!!document.querySelector('#demo-banner')", "the demo banner")
            else:
                self.assertEqual(p.js("!!document.querySelector('#demo-banner')"), False)
            p.js("document.fonts && document.fonts.ready")
            for sid in [None] + p.ids():
                if sid is None:
                    p.js("window.scrollTo(0, 0)")
                else:
                    p.js(f"window.scrollTo(0, window.scrollY + document.querySelector('.secs > .sec[data-id=\"{sid}\"]').getBoundingClientRect().top - 85)")
                p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                for key, mode in (("e", "edit"), ("v", "view")):
                    near = [json.dumps(n) for n in self.watched(p, sid)]
                    before = [p.js(f"({MEASURE})({n})") for n in near]
                    p.js("document.activeElement && document.activeElement.blur()")
                    p.key(key)
                    p.until(f"document.querySelector('#report').dataset.mode === '{mode}'", mode)
                    p.js("new Promise(r => setTimeout(r, 400))")
                    for n, b in zip(near, before):
                        out.append((sid, key, b, p.js(f"({MEASURE})({n})")))
        return out

    def check(self, width, dark, banner, long_name):
        bad = []
        for sid, key, before, after in self.walk(width, dark, banner, long_name):
            moved = {k: round(after[k] - before[k], 1) for k in ("sec", "top") if before[k] is not None and after[k] is not None and after[k] != before[k]}
            if any(abs(v) > 1 for v in moved.values()):
                bad.append(f"at {sid}, pressing {key} moved {moved} ({before} to {after})")
        self.assertEqual(bad, [])

    def test_e_and_v_move_nothing_at_every_width_in_light_and_dark(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark):
                    self.check(width, dark, False, False)

    def test_e_and_v_move_nothing_with_the_demo_banner_up(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark):
                    self.check(width, dark, True, False)

    def test_e_and_v_move_nothing_with_a_long_project_name(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.check(width, False, True, True)


class OnTheTestPage(Walk, Base):
    def start(self, cdp, banner, long_name):
        self.s.httpd.demo = DemoSeam() if banner else None
        if long_name:
            self.store.con.execute("UPDATE projects SET name = ? WHERE code = 'ABC'", (LONG,))
            self.store.con.commit()
        return self.visit(cdp)


class OnFirstRunDemoData(Walk, unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.store = demo_seed.load_if_fresh(clark_store.open_store(self.folder / "clark.db", onedrive_roots=[]), [])
        self.addCleanup(self.store.close)
        self.s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp()),
                         projects=launcher.projects_of(self.folder / "clark.db", []))
        self.s.httpd.demo = demo_seed.Demo(self.folder / "clark.db", [])
        self.addCleanup(self.s.close)

    def start(self, cdp, banner, long_name):
        if not banner:
            self.s.httpd.demo = None
        if long_name:
            self.store.con.execute("UPDATE projects SET name = ?", (LONG,))
            self.store.con.commit()
        p = Pg.at(self, cdp, self.s.port, "#dashboard&p=TUL")
        p.ready()
        return p


if __name__ == "__main__":
    unittest.main()
