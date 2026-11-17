"""Row 1214: glide.js, without a browser: no glide under reduced motion (either way it is asked for), none for a section that moved less
than a pixel, one for a section that moved a pixel or more on either line, and the note is used once. Run: python3 dev/run_tests.py test_glide_node
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "glide_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}

# A page of sections whose places are set by the probe: R.now is where each is now, R.was where it was when noteRects ran.
STUBS = """
globalThis.addEventListener = () => {}; globalThis.window = globalThis;
const R = { was: {}, now: {}, media: false, calls: [] };
const mk = (id) => { const el = { dataset: { id }, animate(k, o) { R.calls.push({ id, from: k[0].transform, to: k[1].transform, ms: o.duration, easing: o.easing }); },
  getBoundingClientRect() { return R.cur[id]; } }; if (R.noAnimate) delete el.animate; return el; };
const root = { querySelectorAll: (sel) => sel === ":scope > .sec[data-id]" ? Object.keys(R.cur).map(mk) : [] };
globalThis.document = { documentElement: { dataset: {} }, querySelector: (sel) => (sel === ".secs" && !R.nullRoot ? root : null) };
globalThis.matchMedia = () => ({ matches: R.media });
function run(was, now, o = {}) {
  R.calls = []; R.media = !!o.media; R.noAnimate = !!o.noAnimate; R.nullRoot = !!o.nullRoot; document.documentElement.dataset = o.attr ? { motion: "reduce" } : {};
  R.cur = was; if (!o.skipNote) G.noteRects();
  R.cur = now; G.glide(o.noRoot ? null : root);
  return R.calls;
}
"""


def run(probe):
    node = shutil.which("node")
    assert node, "node is needed"
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "glide.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=G", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"], cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(_BUNDLE["code"] + "\n" + STUBS + "\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def at(left, top):
    return {"left": left, "top": top}


class Glide(unittest.TestCase):
    def go(self, was, now, opts=""):
        return run(f"run({json.dumps(was)}, {json.dumps(now)}{', ' + opts if opts else ''})")

    def test_a_section_that_moved_glides_from_where_it_was_for_160_ms(self):
        got = self.go({"a": at(10, 100)}, {"a": at(10, 40)})
        self.assertEqual(got, [{"id": "a", "from": "translate(0px, 60px)", "to": "none", "ms": 160, "easing": "ease-out"}])

    def test_a_move_along_either_line_alone_glides(self):
        self.assertEqual([g["from"] for g in self.go({"a": at(50, 40)}, {"a": at(10, 40)})], ["translate(40px, 0px)"], "sideways only")
        self.assertEqual([g["from"] for g in self.go({"a": at(10, 100)}, {"a": at(10, 40)})], ["translate(0px, 60px)"], "up or down only")

    def test_less_than_a_pixel_is_no_move_and_a_pixel_is(self):
        self.assertEqual(self.go({"a": at(10.4, 40.4)}, {"a": at(10, 40)}), [], "0.4 px each way: still")
        self.assertEqual(self.go({"a": at(10.9, 40.9)}, {"a": at(10, 40)}), [], "0.9 px each way: still")
        self.assertEqual(self.go({"a": at(10, 41)}, {"a": at(10, 40)}), [{"id": "a", "from": "translate(0px, 1px)", "to": "none", "ms": 160, "easing": "ease-out"}], "exactly 1 px: glides")
        self.assertEqual(self.go({"a": at(9, 40)}, {"a": at(10, 40)}), [{"id": "a", "from": "translate(-1px, 0px)", "to": "none", "ms": 160, "easing": "ease-out"}], "1 px to the left: glides")
        self.assertEqual(len(self.go({"a": at(10, 39.2)}, {"a": at(10, 40)}, "{}")), 0, "-0.8 px: still")

    def test_nothing_glides_when_motion_is_reduced_by_the_computer_or_by_clark(self):
        was, now = {"a": at(10, 100)}, {"a": at(10, 40)}
        self.assertEqual(self.go(was, now, "{media: true}"), [], "the computer asked for reduced motion")
        self.assertEqual(self.go(was, now, "{attr: true}"), [], "clark's own setting is reduce")
        self.assertEqual(len(self.go(was, now, "{}")), 1, "and with neither it glides")

    def test_a_section_that_was_not_there_before_or_a_missing_note_or_root_does_not_glide(self):
        self.assertEqual(self.go({"a": at(0, 0)}, {"a": at(0, 0), "n": at(5, 90)}), [], "n is new, a did not move")
        self.assertEqual(self.go({"a": at(10, 100)}, {"a": at(10, 40)}, "{skipNote: true}"), [], "noteRects was not called")
        self.assertEqual(self.go({"a": at(10, 100)}, {"a": at(10, 40)}, "{noRoot: true}"), [], "no root")

    def test_a_section_moved_down_glides_from_above_where_it_is(self):
        got = self.go({"a": at(10, 40)}, {"a": at(10, 100)})
        self.assertEqual(got, [{"id": "a", "from": "translate(0px, -60px)", "to": "none", "ms": 160, "easing": "ease-out"}])

    def test_the_glide_eases_out(self):
        got = self.go({"a": at(10, 100)}, {"a": at(10, 40)})
        self.assertEqual([g["easing"] for g in got], ["ease-out"])

    def test_an_element_without_animate_is_left_alone(self):
        self.assertEqual(self.go({"a": at(10, 100)}, {"a": at(10, 40)}, "{noAnimate: true}"), [], "no animate: no call and no throw")

    def test_no_sections_box_when_the_note_is_taken_means_no_glide_and_no_throw(self):
        self.assertEqual(self.go({"a": at(10, 100)}, {"a": at(10, 40)}, "{nullRoot: true}"), [], "the box was missing at noteRects")

    def test_the_note_is_used_once(self):
        got = run("(() => { run({a: {left: 0, top: 90}}, {a: {left: 0, top: 40}}); R.calls = []; G.glide(root); return R.calls; })()")
        self.assertEqual(got, [], "a second glide with no new note does nothing")


if __name__ == "__main__":
    unittest.main()
