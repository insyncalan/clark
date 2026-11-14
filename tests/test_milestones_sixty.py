"""Sixty milestones in one week on the Milestones strip: no label overlap, every label inside the strip, the box tall enough, and the
arrow keys scroll the focused box sideways, at 1400 and 900 px.

Run: python3 dev/run_tests.py test_milestones_sixty
"""
import shutil
import tempfile
import time
import unittest

from _demo import USER
from _editor_checks import for_url
from clark import page
from test_milestones_crowded import BOXES
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

SIXTY = [(f"Milestone number {n:02d} for the same week", f"2026-11-{9 + n % 5:02d}", f"2026-11-{16 + n % 4:02d}" if n % 2 else None) for n in range(60)]


class Sixty(unittest.TestCase):
    def test_sixty_in_one_week(self):
        store, folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(folder), True)
        self.addCleanup(store.close)
        with store.step("dashboard", USER) as step:
            for name, base, fc in SIXTY:
                step.create("milestones", {"project": "TUL", "name": name, "baseline_date": base, "forecast_date": fc, "client_visible": 1, "source": "demo"})
        s = Running(data_for=store.data_for, projects=lambda archived=False: store.read("projects"), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = page_target(cdp)
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#milestones&p=TUL")}, sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-mk').length", sid) >= len(SIXTY) and cdp.js("document.querySelectorAll('.mv-lab').length", sid) >= 1))   # row 1159: a name with no room is hidden
                time.sleep(0.5)
                got = cdp.js(BOXES, sid)
                self.assertEqual(got["pairs"], [], f"{width}px: no two labels overlap")
                self.assertEqual(got["laneClash"], [], f"{width}px: lanes clear")
                self.assertTrue(got["fits"], f"{width}px: box fits lanes (lowest {got['lowest']}, strip {got['stripHeight']})")
                self.assertEqual(got["todayHits"], [], f"{width}px: Today label clear")
                self.assertTrue(got["inside"], width)
                cdp.js("(() => { const w = document.querySelector('.mv-wrap'); w.scrollLeft = 0; w.focus(); })()", sid)
                self.assertTrue(cdp.js("document.activeElement.classList.contains('mv-wrap')", sid))
                for _ in range(3):
                    cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39}, sid)
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39}, sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('.mv-wrap').scrollLeft", sid) > 0), f"{width}px: ArrowRight scrolls the strip")


if __name__ == "__main__":
    unittest.main()
