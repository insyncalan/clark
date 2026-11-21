"""Row 1046: the page-side loadNotices (src/clark/page/src/edit/noticesState.js) hands the bell the notices only on a good answer, and the
refresh timer starts once and stops. A fake fetch gives the answers: an off answer, a share that is away, a good one, a bad one.

Run: python3 dev/run_tests.py test_notices_load_node
Quick tier: no browser. Bundled by the pinned esbuild and run in node (skipped when node is not on the machine). Fixture data is made up.
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

ENTRY = ROOT / "tests" / "fixtures" / "notices_load_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}

SHIM = "globalThis.addEventListener = () => {};\nglobalThis.removeEventListener = () => {};\n"      # the page files listen for pagehide; node has no window

PROBE = r"""
const answers = %s;
let calls = 0;
globalThis.fetch = async (url) => {
  calls += 1;
  const a = answers.shift();
  if (a === "throw") throw new Error("offline");
  return { status: a.status, json: async () => a.body };
};
const timers = { set: [], cleared: [] };
globalThis.setInterval = (fn, ms) => { timers.set.push(ms); return timers.set.length; };
globalThis.clearInterval = (id) => { timers.cleared.push(id); };
const out = { steps: [] };
const note = (id) => ({ id, title: "T " + id, body: "One sentence.", date: new Date().toISOString().slice(0, 10) });
(async () => {
  NS.pushNotices([note("keep")]);
  const before = NS.pushed.value.map((n) => n.id);
  for (const _ of answers.slice()) {
    const status = await NS.loadNotices();
    out.steps.push({ status, shown: NS.shown.value.map((n) => n.id), pushed: NS.pushed.value.map((n) => n.id), calls });
  }
  out.before = before;
  const c0 = calls;
  NS.startNotices(); NS.startNotices();
  out.startCalls = calls - c0;
  await new Promise((r) => setTimeout(r, 0));
  out.afterStart = { set: timers.set.slice(), cleared: timers.cleared.length };
  NS.stopNotices(); NS.stopNotices();
  out.afterStop = { cleared: timers.cleared.length };
  NS.startNotices();
  out.afterRestart = { set: timers.set.length };
  NS.stopNotices();
  out.refresh = NS.REFRESH_MS;
  console.log(JSON.stringify(out));
})();
"""


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nl.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=NS", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def run(answers):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(SHIM + bundle() + ";\n" + PROBE % json.dumps(answers), encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout.strip().splitlines()[-1])


def ok(*ids, **extra):
    notes = [{"id": i, "title": "T " + i, "body": "One sentence.", "date": "2999-01-01"} for i in ids]
    return {"status": 200, "body": {"ok": True, "notices": notes, **extra}}


class LoadNotices(unittest.TestCase):
    def test_away_and_bad_answers_change_nothing_and_off_clears(self):
        got = run([
            ok("keep"),
            {"status": 200, "body": {"ok": True, "why": "away", "notices": []}},     # the share is away
            {"status": 500, "body": None},                                           # a bad answer
            {"status": 200, "body": {"ok": True, "notices": "no"}},                  # a bad body
            {"status": 200, "body": {"ok": False, "notices": []}},                   # not ok
            {"status": 500, "body": {"ok": True, "notices": [{"id": "x", "title": "T", "body": "B", "date": "2999-01-01"}]}},    # a good body on a bad status
            "throw",                                                                 # offline
            {"status": 200, "body": {"ok": True, "why": "off", "notices": []}},      # no place set in Settings: the bell empties
        ])
        self.assertEqual([s["pushed"] for s in got["steps"]], [["keep"]] * 7 + [[]])
        self.assertEqual([s["calls"] for s in got["steps"]], [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual([s["status"] for s in got["steps"]][:3], [200, 200, 500])

    def test_a_good_answer_replaces_the_notices_and_a_good_empty_one_clears_them(self):
        got = run([ok("a", "b"), ok()])
        self.assertEqual([s["status"] for s in got["steps"]], [200, 200])
        self.assertEqual([s["pushed"] for s in got["steps"]], [["a", "b"], []])

    def test_the_installed_version_from_the_answer_drives_a_notice_version_test(self):
        def with_test(**extra):
            r = ok("old", **extra)
            r["body"]["notices"][0]["test"] = {"installedBelow": "1.0.7"}
            return r
        for installed, shown in (("1.0.5", ["old"]), ("1.0.7", []), ("1.0.8", [])):
            got = run([with_test(installed=installed)])
            self.assertEqual(got["steps"][0]["shown"], shown, installed)

    def test_the_timer_starts_once_and_stops(self):
        got = run([ok("a")] * 3)
        self.assertEqual(got["afterStart"]["set"], [got["refresh"]])
        self.assertEqual(got["refresh"], 5 * 60 * 1000)
        self.assertEqual(got["startCalls"], 1, "starting reads once at once, and a second start reads nothing")
        self.assertEqual(got["afterStart"]["cleared"], 0)
        self.assertEqual(got["afterStop"]["cleared"], 1, "a second stop clears nothing")
        self.assertEqual(got["afterRestart"]["set"], 2, "after a stop a start sets the timer again")


if __name__ == "__main__":
    unittest.main()
