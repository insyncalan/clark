"""Row 799, the Weekly snapshot (the published file's client report): the owner's initials stay inside the small circle in
'Risks, delays and items to watch', and the red 'behind plan' chip is drawn only beside a figure (an empty Achieved, a dash, has none).

Run: python3 dev/run_tests.py test_snapshot_avatar_chip
Measured at 1400 and 900 px, light and dark, on the published file made from the demo database. The snapshot is drawn only in a
published file (the served page does not offer it), so there is no Edit mode of it; Edit is not a variant here.
"""
import json
import unittest

import test_client_report as cr

OWNERS = ["Priya Nair", "Wendy Mwangi", "Mary Jo Smith"]      # wide letters, and a name with three words (two initials are drawn)

# One entry per initials circle in the risks section: the circle's size and the width of its letters.
MEASURE = """(function () {
  return JSON.stringify([].slice.call(document.querySelectorAll('#cr-raid .av')).map(function (a) {
    var r = document.createRange(); r.selectNodeContents(a);
    var t = r.getBoundingClientRect(), b = a.getBoundingClientRect(), fs = parseFloat(getComputedStyle(a).fontSize);
    var rad = b.width / 2, half = fs / 2;
    return { text: a.textContent, textW: t.width, w: b.width, h: b.height, chord: 2 * Math.sqrt(Math.max(0, rad * rad - half * half)), scroll: a.scrollWidth, client: a.clientWidth };
  }));
})()"""

CHIPS = """(function () {
  return JSON.stringify([].slice.call(document.querySelectorAll('#cr-plans [data-line]')).map(function (l) {
    var ac = l.querySelector('.c-ac'), v = ac.querySelector('b'), chip = ac.querySelector('.cr-behind');
    return { value: v ? v.textContent : '', chip: !!chip };
  }));
})()"""

# A work list's avatar (ItemRows.jsx draws <span class="wl-meta"><span class="av">) outside the snapshot, planted next to the real ones.
PLANT = """(function () {
  var h = document.createElement('div');
  h.innerHTML = '<span class="wl-meta"><span class="av">AB</span></span>';
  document.getElementById('main').appendChild(h);
  var a = h.querySelector('.av'), r = a.getBoundingClientRect();
  var spill = a.scrollWidth > a.clientWidth;
  h.remove();
  return JSON.stringify({h: r.height, spill: spill});
})()"""

INSIDE = """JSON.stringify([].slice.call(document.querySelectorAll('.cr-wl .wl-meta .av')).map(function (a) { return a.getBoundingClientRect().width; }))"""


class SnapshotAvatarChip(cr.Drawn):
    def serve_with(self, owners=True, percent=None):
        from clark import page, publish
        from pathlib import Path
        import tempfile
        from test_publish import EMPTY_BRANDING
        inputs = publish.read_inputs(self.store, "TUL", as_at="2026-10-28")
        pub = publish.select(inputs)
        data = dict(pub["data"])
        if owners:
            raid = [dict(r) for r in data["raid"]]
            open_risks = [r for r in raid if r.get("type") in ("Risk", "Issue") and r.get("status") == "Open"]
            while len(open_risks) < len(OWNERS):
                extra = dict(open_risks[0], id="TUL-9%02d" % len(open_risks), description="Another open risk %d" % len(open_risks))
                raid.append(extra)
                open_risks.append(extra)
            for r, name in zip(open_risks, OWNERS):
                r["owner"] = name
            data["raid"] = raid
        if percent is not None:
            data["milestones"] = [dict(m, percent_complete=percent) if m.get("status") == "Planned" else m for m in data["milestones"]]
        pub["data"] = data
        text = publish.render(pub, page.page_html(EMPTY_BRANDING), "2026-10-28", data["project"]["name"])
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "report.html"
        path.write_text(text, encoding="utf-8")
        return path.as_uri()

    def each_view(self, url, check):
        from test_server import chrome, wait
        with chrome() as cdp:
            sid = self.open_page(cdp, url)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                for theme in ("light", "dark"):
                    cdp.js("document.documentElement.dataset.theme = %s" % json.dumps(theme), sid)
                    self.assertTrue(wait(lambda: cdp.js("document.getAnimations().filter(a => a.effect.getComputedTiming().iterations !== Infinity).length === 0", sid)), "settled")
                    check(cdp, sid, "%dpx %s" % (width, theme))

    def test_the_initials_fit_inside_their_circle(self):
        seen = []

        def check(cdp, sid, where):
            circles = json.loads(cdp.js(MEASURE, sid))
            self.assertGreaterEqual(len(circles), 3, where + ": the three owners are drawn")
            for c in circles:
                seen.append(c["text"])
                self.assertLessEqual(c["textW"], c["chord"], "%s: %s fits the circle (letters %.1f px, room %.1f px)" % (where, c["text"], c["textW"], c["chord"]))
                self.assertEqual(c["scroll"], c["client"], where + ": " + c["text"] + " does not spill")
                self.assertAlmostEqual(c["w"], c["h"], delta=0.5, msg=where + ": it is still a circle")
        self.each_view(self.serve_with(), check)
        self.assertTrue({"PN", "WM", "MJ"} <= set(seen), seen)

    def test_the_work_lists_keep_their_small_avatar(self):
        """A read of PR 863 found: the bigger circle is the snapshot's only (.cr-wl); the work lists share the .wl-meta class and keep their usual circle (20 px high, as in the prototype; the snapshot gets 30)."""
        def check(cdp, sid, where):
            outside = json.loads(cdp.js(PLANT, sid))
            inside = json.loads(cdp.js(INSIDE, sid))
            self.assertTrue(inside and all(abs(w - 30) < 0.5 for w in inside), where + ": the snapshot circle is 30 px, got %r" % inside)
            self.assertAlmostEqual(outside["h"], 20, delta=0.5, msg=where + ": a work list avatar is the small 20 px one, got %r" % outside)
            self.assertFalse(outside["spill"], where + ": and two letters do not spill out of it")
        self.each_view(self.serve_with(), check)

    def test_the_chip_is_hidden_when_achieved_is_empty_and_shown_when_it_has_a_figure(self):
        def empty(cdp, sid, where):
            lines = json.loads(cdp.js(CHIPS, sid))
            self.assertTrue(any(not l["value"] for l in lines), where + ": a line with no Achieved figure")
            for l in lines:
                if not l["value"]:
                    self.assertFalse(l["chip"], where + ": no chip beside an empty Achieved")

        def figured(cdp, sid, where):
            lines = json.loads(cdp.js(CHIPS, sid))
            self.assertTrue(any(l["chip"] for l in lines), where + ": a line behind plan with a figure keeps its chip")
            for l in lines:
                if l["chip"]:
                    self.assertTrue(l["value"], where + ": the chip sits beside a figure")
        self.each_view(self.serve_with(owners=False), empty)
        self.each_view(self.serve_with(owners=False, percent=40), figured)


for _name in [n for n in dir(cr.Drawn) if n.startswith("test_")]:
    setattr(SnapshotAvatarChip, _name, None)       # the parent's own tests run in its own file, not twice


if __name__ == "__main__":
    unittest.main()
