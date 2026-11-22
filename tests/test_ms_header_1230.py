"""Row 1230, part 2: the Dashboard's Milestones section gets the new header, toolbar and timeline. The Milestones page does not change.

Run: python3 dev/run_tests.py -j 1 test_ms_header_1230
The page runs from the real server over a real store (fictional data) in headless Chrome (required: it fails, never skips, without
Chrome). Dashboard section only (place sec-<id>): the Timeline / Calendar tabs on the section's heading row; Earlier, Later, Today and the
range on the left of the toolbar and Week, Month, Quarter on the right; the caption "Drag the grip below the timeline to zoom" at the bottom edge of
the box; every name shown, in up to four tiers (two above the line, two below) with a thin leader from each label to its mark; each label
two lines (name, then date and "+N days"); the Today marker a pill. No new word is added: every string is one the page already had.
The Milestones page (place page) keeps its markup. Widths 1400 and 900 only.
"""
import contextlib
import tempfile
import unittest
from unittest import mock

from _demo import USER, DemoStore

from clark import page, server as sv
from test_milestones_crowded import CROWDED
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, page_target

CASES = [(1400, False), (1400, True), (900, False), (900, True)]
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")

SEE = """(() => {
  const R = (e) => e.getBoundingClientRect(), box = document.querySelector('.msv[data-place^=sec-]');
  if (!box) return null;
  const sec = box.closest('.sec'), head = sec.querySelector('.sec-head'), sw = box.querySelector('.msv-sw'), bar = box.querySelector('.mv-bar'), wrap = box.querySelector('.mv-wrap');
  const strip = box.querySelector('.mv-strip'), caps = [...box.querySelectorAll('.mv-cap')], line = box.querySelector('.mv-line');
  const tabs = [...sw.querySelectorAll('button')], num = bar.querySelector('.num'), sc = bar.querySelector('.mv-txt'), prev = bar.querySelector('[data-mv="-1"]');
  const next = bar.querySelector('[data-mv="1"]'), tod = bar.querySelector('[data-mv="0"]');
  const labs = [...box.querySelectorAll('.mv-lab2')], marks = [...box.querySelectorAll('.mv-mk')], leads = [...box.querySelectorAll('.mv-lead')];
  const L = (e) => { const r = R(e); return {l: r.left, r: r.right, t: r.top, b: r.bottom}; };
  const hit = (a, b) => a.l < b.r - 1 && b.l < a.r - 1 && a.t < b.b - 1 && b.t < a.b - 1;
  const lrects = labs.map(L), ly = R(line).top + R(line).height / 2;
  const overlaps = [], crossings = [], joins = [];
  lrects.forEach((a, i) => lrects.slice(i + 1).forEach((b, j) => { if (hit(a, b)) overlaps.push([labs[i].dataset.lab, labs[i + 1 + j].dataset.lab]); }));
  const own = {};
  labs.forEach((e) => { own[e.dataset.lab.split(':')[0]] = e; });
  leads.forEach((d) => {
    const dr = R(d), id = d.dataset.lead, mk = marks.find((m) => m.dataset.ms === id), lab = own[id];
    const x = dr.left + dr.width / 2, mx = R(mk).left + R(mk).width / 2, lr = L(lab);
    const rect = {l: x - 0.5, r: x + 0.5, t: dr.top, b: dr.bottom};
    labs.forEach((o) => { if (o !== lab && hit(rect, L(o))) crossings.push([id, o.dataset.lab]); });
    const touches = lr.b <= ly ? Math.abs(dr.top - lr.b) : Math.abs(dr.bottom - lr.t);
    joins.push({id, dx: Math.abs(x - mx), touches, far: lr.b <= ly ? ly - dr.bottom : dr.top - ly});
  });
  const two = labs.map((e) => { const b = e.querySelector('b'), s = e.querySelector('span'); return {name: b && b.textContent, one: !!b && !!s && R(b).height < 24 && R(s).height < 24 && R(s).top >= R(b).bottom - 1,
                                                                                      text: s ? s.textContent.trim() : ''}; });
  const today = box.querySelectorAll('[data-today]'), pill = today[0] && today[0].querySelector('b'), cs = pill && getComputedStyle(pill);
  return {
    tabs: tabs.map((b) => b.textContent.trim()), cur: tabs.map((b) => b.getAttribute('aria-current')), swTop: R(sw).top, swBottom: R(sw).bottom, headTop: R(head).top, headBottom: R(head).bottom,
    order: [prev, next, tod, num, sc].map((e) => R(e).left), scRight: R(sc).right, wrapRight: R(wrap).right, scWords: [...sc.querySelectorAll('button')].map((b) => b.textContent.trim()),
    caps: caps.length, capText: caps[0] ? caps[0].textContent : '', capSibling: !!caps[0] && caps[0].parentElement === wrap.parentElement, capInBar: !!bar.querySelector('.mv-cap, .mv-zoom') || bar.textContent.includes('Drag the bottom'),
    capTop: caps[0] ? R(caps[0]).top : 0, wrapTop: R(wrap).top, wrapBottom: R(wrap).bottom,
    labs: labs.length, solid: marks.length, hid: box.querySelectorAll('[data-hid]').length, meas: box.querySelectorAll('.mv-meas').length, oldLab: box.querySelectorAll('.mv-lab').length,
    tops: [...new Set(lrects.map((r) => Math.round(r.t)))], ly, above: lrects.some((r) => r.b <= ly), below: lrects.some((r) => r.t >= ly), overlaps, crossings, joins, leads: leads.length, two,
    today: today.length, pillText: pill && pill.textContent, pillRadius: cs ? parseFloat(cs.borderTopLeftRadius) : 0, pillBg: cs ? cs.backgroundColor : '',
    stripInside: labs.every((e) => R(e).left >= R(strip).left - 1), noScroll: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
    boxScrolls: wrap.scrollWidth > wrap.clientWidth, swPos: getComputedStyle(sw).position};
})()"""

PAGE = """(() => {
  const box = document.querySelector('.msv[data-place=page]'), bar = box.querySelector('.mv-bar');
  return {sw: getComputedStyle(box.querySelector('.msv-sw')).position, zoomInBar: !!bar.querySelector('.mv-zoom'), capsOutside: box.querySelectorAll('.mv-cap').length, lab: box.querySelectorAll('.mv-lab').length,
          lab2: box.querySelectorAll('.mv-lab2').length, lead: box.querySelectorAll('.mv-lead').length, scale: !!bar.querySelector('.cal-sc'), barPad: parseFloat(getComputedStyle(bar).paddingRight)};
})()"""

CAL = """(() => {
  const R = (e) => e.getBoundingClientRect(), box = document.querySelector('.msv[data-place^=sec-]'), bar = box.querySelector('.cal-bar');
  const sc = bar.querySelector('.mv-txt'), t = bar.querySelector('.cal-t'), prev = bar.querySelector('[data-cal="-1"]'), tod = bar.querySelector('[data-cal="0"]');
  return {order: [prev, tod, t, sc].map((e) => R(e).left), scRight: R(sc).right, barRight: R(bar).right, scWords: [...sc.querySelectorAll('button')].map((b) => b.textContent.trim()),
          chips: box.querySelectorAll('.cal-ms').length, bars: box.querySelectorAll('.mv-bar').length};
})()"""


class Base(unittest.TestCase):
    ROWS = CROWDED

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        with self.store.step("dashboard", USER) as st:
            for name, base, fc in self.ROWS:
                  st.create("milestones", {"project": "ABC", "name": name, "baseline_date": base, "forecast_date": fc, "client_visible": 1, "source": "demo"})
        self.s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def visit(self, cdp, hash_, width, edit, ready=".msv"):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{hash_}"}, sid)
        self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{ready}')", sid), 10), "the block drew")
        if edit:
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-mode=edit]').getAttribute('aria-pressed') === 'true'", sid), 10), "Edit is on")
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid), 10))
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.msv .mv-mk').length >= 10", sid), 10), "the marks drew")
        return sid

    @contextlib.contextmanager
    def case(self, width, edit):
        with chrome() as cdp:
            sid = self.visit(cdp, "#dashboard&p=ABC", width, edit, ".msv .mv-wrap")
            wait(lambda: cdp.js("document.querySelectorAll('.msv .mv-lab2').length === document.querySelectorAll('.msv .mv-mk').length", sid), 5)
            yield cdp, sid, cdp.js(SEE, sid)

class Header(Base):
    def test_tabs_sit_on_the_heading_row_and_follow_the_click(self):
        for width, edit in CASES:
            with self.subTest(width=width, edit=edit), self.case(width, edit) as (cdp, sid, got):
                self.assertEqual(got["tabs"], ["Timeline", "Calendar"])
                self.assertEqual(got["cur"], ["true", "false"])
                self.assertGreaterEqual(got["swTop"], got["headTop"] - 4, "the tabs start inside the heading row")
                self.assertLessEqual(got["swBottom"], got["headBottom"] + 4, "the tabs end inside the heading row")
                cdp.js("document.querySelector('.msv[data-place^=sec-] [data-msvb=cal]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.msv[data-place^=sec-] .cal').length === 1", sid), 5), "the Calendar drew")
                self.assertEqual(cdp.js("[...document.querySelectorAll('.msv[data-place^=sec-] .msv-sw button')].map((b) => b.getAttribute('aria-current'))", sid), ["false", "true"])

    def test_toolbar_has_the_steps_and_range_on_the_left_and_the_scale_on_the_right(self):
        for width, edit in CASES:
            with self.subTest(width=width, edit=edit), self.case(width, edit) as (cdp, sid, got):
                self.assertEqual(got["order"], sorted(got["order"]), "Earlier, Later, Today, range, then the scale")
                self.assertEqual(len(set(got["order"])), 5)
                self.assertEqual(got["scWords"], ["Week", "Month", "Quarter"])
                self.assertLessEqual(abs(got["scRight"] - got["wrapRight"]), 2, "the scale ends at the box's right edge")
                cdp.js("document.querySelector('.msv[data-place^=sec-] [data-scale-b=week]').click()", sid)
                self.assertEqual(cdp.js("document.querySelector('.msv[data-place^=sec-] [data-scale-b=week]').getAttribute('aria-current')", sid), "true")

    def test_the_caption_is_at_the_bottom_edge_of_the_box_not_in_the_toolbar(self):
        for width, edit in CASES:
            with self.subTest(width=width, edit=edit), self.case(width, edit) as (cdp, sid, got):
                self.assertEqual(got["caps"], 1)
                self.assertIn("Drag the grip below the timeline to zoom", got["capText"])
                self.assertTrue(got["capSibling"], "a child of the box's wrapper, beside the scrolling line")
                self.assertFalse(got["capInBar"], "not in the toolbar")
                self.assertGreater(got["capTop"], got["wrapTop"] + (got["wrapBottom"] - got["wrapTop"]) / 2, "in the lower half")

    def test_a_label_is_two_lines_name_then_date_and_the_slip(self):
        for width, edit in CASES:
            with self.subTest(width=width, edit=edit), self.case(width, edit) as (cdp, sid, got):
                self.assertTrue(all(t["one"] for t in got["two"]), [t for t in got["two"] if not t["one"]])
                slipped = [t for t in got["two"] if "+" in t["text"]]
                self.assertTrue(slipped and all(" days" in t["text"] or " day" in t["text"] for t in slipped), "a slipped one says +N days on its date line")
                self.assertRegex(got["two"][0]["text"], r"^\d\d-\d\d-\d{4}")

    def test_today_is_a_pill_that_says_today(self):
        for width, edit in CASES:
            with self.subTest(width=width, edit=edit), self.case(width, edit) as (cdp, sid, got):
                self.assertEqual(got["today"], 1)
                self.assertEqual(got["pillText"], "Today")
                self.assertGreaterEqual(got["pillRadius"], 8)
                self.assertNotIn(got["pillBg"], ("rgba(0, 0, 0, 0)", "transparent"))

    def test_the_calendar_toolbar_has_its_scale_on_the_right(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                  sid = self.visit(cdp, "#dashboard&p=ABC", width, False, ".msv .mv-wrap")
                  cdp.js("document.querySelector('.msv[data-place^=sec-] [data-msvb=cal]').click()", sid)
                  self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.msv[data-place^=sec-] .cal').length === 1", sid), 5))
                  got = cdp.js(CAL, sid)
                  self.assertEqual(got["order"], sorted(got["order"]))
                  self.assertEqual(got["scWords"], ["Week", "Month", "Quarter"])
                  self.assertLessEqual(abs(got["scRight"] - got["barRight"]), 2, "the scale ends at the toolbar's right edge")
                  self.assertEqual(got["bars"], 0)

    def test_the_milestones_page_is_unchanged(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                  sid = self.visit(cdp, "#milestones&p=ABC", width, False, ".mv-wrap")
                  got = cdp.js(PAGE, sid)
                  self.assertTrue(got["zoomInBar"] and got["scale"], "the caption stays in the bar")
                  self.assertEqual((got["capsOutside"], got["lab2"], got["lead"]), (0, 0, 0))
                  self.assertGreaterEqual(got["lab"], 1)
                  if width == 1400:
                      self.assertEqual(got["sw"], "absolute")
                      self.assertGreaterEqual(got["barPad"], 200, "the bar still leaves room for the switch")


# Nine milestones about two weeks apart: the labels need tiers (this fixture fits in four; the code allows TIER_MAX, 12), and a leader can always stay clear of the other labels.


class Spread(Base):
    ROWS = [(f"Phase {n} sign-off", d, f) for n, (d, f) in enumerate([("2026-10-02", None), ("2026-10-18", "2026-11-02"), ("2026-11-03", None), ("2026-11-20", None),
                                                                      ("2026-12-08", "2026-12-22"), ("2026-12-26", None), ("2027-01-12", None), ("2027-01-30", None), ("2027-02-15", None)])]

    def test_nine_marks_about_two_weeks_apart_are_all_named_in_at_most_four_tiers_each_with_a_leader(self):
        for width, edit in CASES:
            with self.subTest(width=width, edit=edit), self.case(width, edit) as (cdp, sid, got):
                self.assertGreaterEqual(got["solid"], 9)
                self.assertEqual(got["labs"], got["solid"], "a label for every mark")
                self.assertEqual((got["hid"], got["meas"], got["oldLab"]), (0, 0, 0), "no name is hidden")
                self.assertLessEqual(len(got["tops"]), 4, f"up to four tiers: {got['tops']}")
                self.assertTrue(got["above"] and got["below"], "tiers on both sides of the line")
                self.assertEqual(got["overlaps"], [], "no two labels overlap")
                self.assertEqual(got["crossings"], [], "no leader crosses another label")
                self.assertEqual(got["leads"], got["labs"], "one leader for each label")
                for j in got["joins"]:
                    self.assertLessEqual(j["dx"], 2, f"{j['id']}: the leader is on its mark")
                    self.assertLessEqual(j["touches"], 2, f"{j['id']}: the leader starts at its label")
                    self.assertLessEqual(j["far"], 16 + 48 * 3, f"{j['id']}: the leader ends at the line")
                self.assertTrue(got["stripInside"])
                self.assertTrue(got["noScroll"] and got["boxScrolls"], "the page does not scroll sideways; the box does")


class Crowded(Base):
    """Ten milestones in two weeks, the hostile fixture of test_milestones_crowded: every name still shown, none on another, leaders may pass behind a nearer label."""

    def test_every_name_is_shown_and_no_two_labels_overlap(self):
        for width, edit in CASES:
            with self.subTest(width=width, edit=edit), self.case(width, edit) as (cdp, sid, got):
                self.assertEqual(got["labs"], got["solid"], "a label for every mark")
                self.assertEqual((got["hid"], got["meas"], got["oldLab"]), (0, 0, 0))
                self.assertLessEqual(len(got["tops"]), 12, f"at most twelve tiers (six a side): {got['tops']}")
                self.assertEqual(got["overlaps"], [], "no two labels overlap")
                self.assertTrue(got["noScroll"])


if __name__ == "__main__":
    unittest.main()
