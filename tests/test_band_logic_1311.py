"""Row 1311 (ruling 19-11): src/clark/page/src/logic/banding.js, the class .band on every other VISIBLE section of the Classic dashboard.

Run: python3 dev/run_tests.py test_band_logic_1311
The pure function runs in headless Chrome (the repo has no Node) from the pinned esbuild bundle; the toggling test hides a section and reads the computed
style: the banding follows the section shown or hidden.
"""
import json
import tempfile
import time
import unittest
from pathlib import Path

from clark import page
from test_server import chrome
from test_theme_banding_1311 import bundle


def it(id, slot="full", hidden=False, summary=False):
    return {"id": id, "slot": slot, "hidden": hidden, "summary": summary}


def run(cdp, sid, expr):
    return cdp.js("(() => { const B = BD; return JSON.stringify(%s); })()" % expr, sid)


def target(cdp):
    html = page.page_html(branding=page.NO_BRAND, theme="prototype-2.0")
    path = Path(tempfile.mkdtemp(prefix="clark-test-")) / "p.html"
    path.write_text(html, encoding="utf-8")
    tid = cdp.call("Target.createTarget", {"url": "about:blank"})["targetId"]
    sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
    cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
    end = time.monotonic() + 20
    while cdp.js("document.readyState", sid) != "complete" and time.monotonic() < end:
        time.sleep(0.05)
    cdp.js(bundle(), sid)
    return sid, path


class Pure(unittest.TestCase):
    def ids(self, items):
        with chrome() as cdp:
            sid, path = target(cdp)
            self.addCleanup(lambda: (path.unlink(), path.parent.rmdir()))
            return json.loads(run(cdp, sid, "B.bandIds(%s)" % json.dumps(items)))

    def test_every_other_one_starting_with_the_first(self):
        self.assertEqual(self.ids([it(1), it(2), it(3), it(4), it(5)]), [1, 3, 5])

    def test_hidden_sections_do_not_count(self):
        self.assertEqual(self.ids([it(1), it(2, hidden=True), it(3), it(4)]), [1, 4])
        self.assertEqual(self.ids([it(1, hidden=True), it(2), it(3)]), [2])

    def test_the_summary_is_skipped_and_the_next_is_the_first(self):
        self.assertEqual(self.ids([it(1, summary=True), it(2), it(3), it(4)]), [2, 4])

    def test_a_pair_counts_and_bands_as_one(self):
        self.assertEqual(self.ids([it(1), it(2, "left"), it(3, "right"), it(4), it(5)]), [1, 4])      # the pair is the 2nd: plain, both halves

    def test_a_pair_on_a_banded_place_bands_both_halves(self):
        self.assertEqual(self.ids([it(1, "left"), it(2, "right"), it(3), it(4)]), [1, 2, 4])
        self.assertEqual(self.ids([it(1), it(2), it(3, "left"), it(4, "right")]), [1, 3, 4])      # the pair is the 3rd

    def test_a_hidden_section_between_the_halves_changes_nothing(self):
        self.assertEqual(self.ids([it(1, "left"), it(2, hidden=True), it(3, "right"), it(4)]), [1, 3])

    def test_a_left_half_with_no_right_is_one_section(self):
        self.assertEqual(self.ids([it(1, "left"), it(2), it(3)]), [1, 3])

    def test_a_summary_between_the_halves_splits_the_pair(self):
        # left, summary, right: the right half is its own section (the summary resets the pair state), here the 2nd: plain
        self.assertEqual(self.ids([it(1, "left"), it(2, summary=True), it(3, "right"), it(4)]), [1, 4])

    def test_a_right_half_after_a_full_section_is_its_own_section(self):
        self.assertEqual(self.ids([it(1), it(2, "right"), it(3)]), [1, 3])

    def test_a_second_right_half_does_not_join_the_first_pair(self):
        self.assertEqual(self.ids([it(1, "left"), it(2, "right"), it(3, "right"), it(4)]), [1, 2, 4])      # the 3rd right is the 2nd section: plain; 4 is the 3rd: banded

    def test_empty(self):
        self.assertEqual(self.ids([]), [])


class Follows(unittest.TestCase):
    def test_hiding_a_section_moves_the_banding(self):
        with chrome() as cdp:
            sid, path = target(cdp)
            self.addCleanup(lambda: (path.unlink(), path.parent.rmdir()))
            cdp.js("""(() => { document.documentElement.setAttribute('data-mode', 'view');
                const secs = document.createElement('div'); secs.className = 'secs';
                secs.innerHTML = ['current', 'text', 'text', 'text', 'text'].map((t, i) => '<div class="sec slot-full" data-type="' + t + '" id="s' + i + '"><div class="sec-head">S' + i + '</div></div>').join('');
                document.body.appendChild(secs); BD.applyBands(document); })()""", sid)
            fills = "[...document.querySelectorAll('.secs > .sec')].map((e) => getComputedStyle(e).backgroundColor !== 'rgba(0, 0, 0, 0)')"
            self.assertEqual(cdp.js(fills, sid), [False, True, False, True, False])      # the summary is plain, then every other one
            cdp.js("document.getElementById('s1').classList.add('is-hidden'); BD.applyBands(document)", sid)
            self.assertEqual(cdp.js(fills, sid), [False, False, True, False, True])      # S1 hidden: S2 is now the first
            cdp.js("document.getElementById('s1').classList.remove('is-hidden'); BD.applyBands(document)", sid)
            self.assertEqual(cdp.js(fills, sid), [False, True, False, True, False])
            # the border-top line: every visible section but the first has it
            lines = cdp.js("[...document.querySelectorAll('.secs > .sec')].map((e) => getComputedStyle(e).borderTopWidth)", sid)
            self.assertEqual(lines, ["0px", "1px", "1px", "1px", "1px"])

    def test_a_drag_slot_does_not_count(self):
        with chrome() as cdp:
            sid, path = target(cdp)
            self.addCleanup(lambda: (path.unlink(), path.parent.rmdir()))
            got = cdp.js("""(() => { const secs = document.createElement('div'); secs.className = 'secs';
                secs.innerHTML = '<div class="sec" data-type="text"></div><div class="sec drag-slot" data-type="text"></div><div class="sec" data-type="text"></div><div class="sec" data-type="text"></div>';
                document.body.appendChild(secs); BD.applyBands(document);
                return [...secs.children].map((e) => e.classList.contains('band')); })()""", sid)
            self.assertEqual(got, [True, False, False, True])      # the drag slot is skipped: the 3rd child is the 2nd counted (plain), the 4th the 3rd (banded)

    def test_only_direct_children_of_secs_are_banded(self):
        with chrome() as cdp:
            sid, path = target(cdp)
            self.addCleanup(lambda: (path.unlink(), path.parent.rmdir()))
            got = cdp.js("""(() => { const secs = document.createElement('div'); secs.className = 'secs';
                secs.innerHTML = '<div class="sec" data-type="text"><div class="sec" id="inner"></div></div><div class="sec" data-type="text"></div>';
                document.body.appendChild(secs); BD.applyBands(document);
                return [secs.children[0].classList.contains('band'), document.getElementById('inner').classList.contains('band'), secs.children[1].classList.contains('band')]; })()""", sid)
            self.assertEqual(got, [True, False, False])

    def test_at_a_glance_is_a_normal_banded_section_and_current_is_the_plain_summary(self):
        with chrome() as cdp:
            sid, path = target(cdp)
            self.addCleanup(lambda: (path.unlink(), path.parent.rmdir()))
            got = cdp.js("""(() => { const secs = document.createElement('div'); secs.className = 'secs';
                secs.innerHTML = ['current', 'glance', 'text', 'text'].map((t) => '<div class="sec" data-type="' + t + '"></div>').join('');
                document.body.appendChild(secs); BD.applyBands(document);
                return [...secs.children].map((e) => e.classList.contains('band')); })()""", sid)
            self.assertEqual(got, [False, True, False, True])      # type current is the plain summary; At a glance is the first counted section, banded

    def test_hiding_needs_no_manual_call_in_the_page_wiring(self):
        """Dashboard.jsx wires applyBands on render and a class or type change, Classic only, no address or history touched (read from the source: Chrome's page has no dashboard data here)."""
        src = (Path(__file__).resolve().parents[1] / "src" / "clark" / "page" / "src" / "components" / "Dashboard.jsx").read_text(encoding="utf-8")
        for part in ("applyBands(document)", 'classicTheme() && ', "MutationObserver", 'attributeFilter: ["class", "data-type"]'):
            self.assertIn(part, src)


if __name__ == "__main__":
    unittest.main()
