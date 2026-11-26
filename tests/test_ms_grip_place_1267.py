"""Row 1267 (gap on PR 1830): the grip zoom is kept for each place.

Run: python3 dev/run_tests.py test_ms_grip_place_1267
Chrome launches at 1400 and 900 px.
"""
import unittest

import test_ms_header_1230 as H
from _new_page import reload_to_new_page_cdp
from test_server import chrome, wait

PCT = "document.querySelector('[data-place] .mv-wrap').dataset.zoomPct"

STORED = "Object.fromEntries(Object.keys(localStorage).filter((k) => k.startsWith('clark.tlZoom.')).map((k) => [k, localStorage.getItem(k)]))"


class ZoomPerPlace(H.Base):
    """The grip zoom (tlZoom.<place>, not the Week/Month/Quarter scale tlScale.<place>): the Milestones page and the Dashboard section keep their own."""

    def drag_grip(self, cdp, sid, scope, dy):
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid), 10))
        cdp.js(f"document.querySelector('{scope} [data-grip]').scrollIntoView({{block: 'center', behavior: 'instant'}})", sid)
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid), 10))
        read = f"""(() => {{ const g = document.querySelector('{scope} [data-grip]'); const r = g.getBoundingClientRect();
            const x = r.left + r.width / 2, y = r.top + r.height / 2, hit = document.elementFromPoint(x, y);
            return [x, y, !!hit && hit.closest('[data-grip]') === g]; }})()"""
        seen = []

        def settled():
            now = cdp.js(read, sid)
            seen.append(now)
            return now[2] and len(seen) > 1 and seen[-2] == now
        self.assertTrue(wait(settled, 10), f"{scope}: the grip is under its own point and has not moved between two reads: {seen[-2:]}")
        x, y = seen[-1][:2]
        mouse = lambda kind, py, **kw: cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": py, **kw}, sid)
        mouse("mousePressed", y, button="left", clickCount=1)
        for i in range(1, 7):
            mouse("mouseMoved", y + dy * i // 6, button="left", buttons=1)
        mouse("mouseReleased", y + dy, button="left", clickCount=1)

    def pct(self, cdp, sid, scope):
        return cdp.js(f"document.querySelector('{scope} .mv-wrap').dataset.zoomPct", sid)

    def stored(self, cdp, sid):
        return cdp.js(STORED, sid)

    def test_a_dragged_zoom_comes_back_for_that_place_and_the_other_place_is_not_touched(self):
        PAGE, SEC = ".msv[data-place=page]", ".msv[data-place^=sec-]"
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, "#milestones&p=ABC", width, False, f"{PAGE} .mv-wrap")
                self.assertEqual(self.pct(cdp, sid, PAGE), "100")
                self.drag_grip(cdp, sid, PAGE, 100)
                self.assertTrue(wait(lambda: int(self.pct(cdp, sid, PAGE)) > 130), f"{width}: dragged down to a bigger zoom")
                page_zoom = self.pct(cdp, sid, PAGE)
                self.assertTrue(wait(lambda: list(self.stored(cdp, sid)) == ["clark.tlZoom.page"]), f"{width}: only the page's own key is written: {self.stored(cdp, sid)}")
                kept = self.stored(cdp, sid)["clark.tlZoom.page"]
                self.assertEqual(round(float(kept) * 100), int(page_zoom), f"{width}: the number kept is the zoom shown")
                reload_to_new_page_cdp(cdp, sid, f"!!document.querySelector('{PAGE} .mv-wrap')", f"{width}: redrawn")
                self.assertEqual(self.pct(cdp, sid, PAGE), page_zoom, f"{width}: after a reload the page zoom is back")
                cdp.js("location.hash = '#dashboard&p=ABC'", sid)
                self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{SEC} .mv-wrap')", sid), 10), f"{width}: the Dashboard section drew")
                self.assertEqual(self.pct(cdp, sid, SEC), "100", f"{width}: the section does not take the page's zoom")
                self.drag_grip(cdp, sid, SEC, 60)
                self.assertTrue(wait(lambda: int(self.pct(cdp, sid, SEC)) > 100), f"{width}: the section zooms on its own")
                sec_zoom = self.pct(cdp, sid, SEC)
                self.assertTrue(wait(lambda: len(self.stored(cdp, sid)) == 2), f"{width}: the section keeps its own key: {self.stored(cdp, sid)}")
                stored = self.stored(cdp, sid)
                self.assertEqual(stored["clark.tlZoom.page"], kept, f"{width}: the page's kept zoom is not changed by the section")
                cdp.js("location.hash = '#milestones&p=ABC'", sid)
                self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{PAGE} .mv-wrap')", sid), 10))
                self.assertEqual(self.pct(cdp, sid, PAGE), page_zoom, f"{width}: back on the page, its own zoom")
                cdp.js("location.hash = '#dashboard&p=ABC'", sid)
                self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{SEC} .mv-wrap')", sid), 10))
                self.assertEqual(self.pct(cdp, sid, SEC), sec_zoom, f"{width}: back on the Dashboard, the section's own zoom")

    def test_the_scale_and_the_grip_zoom_are_two_keys(self):
        PAGE = ".msv[data-place=page]"
        with chrome() as cdp:
            sid = self.visit(cdp, "#milestones&p=ABC", 1400, False, f"{PAGE} .mv-wrap")
            cdp.js(f"document.querySelector('{PAGE} [data-scale-b=week]').click()", sid)
            self.assertTrue(wait(lambda: sorted(cdp.js("Object.keys(localStorage).filter((k) => k.startsWith('clark.tl'))", sid)) == ["clark.tlScale.page"]))
            self.assertEqual(self.pct(cdp, sid, PAGE), "100", "a changed scale leaves the grip zoom at 100%")
