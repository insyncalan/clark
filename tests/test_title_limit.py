"""#942: a work item's title limit has ONE source, changes.ITEM_TITLE_MAX; the page gets it from the build, not from a number of its own.

Run: python3 dev/run_tests.py test_title_limit
Part 1 is the server: a title of ITEM_TITLE_MAX characters is saved, one more is refused, nothing is written. Part 2 is the page source and
build: PeekTitle.jsx holds no number (it reads the name the build defines), the build writes changes.ITEM_TITLE_MAX under that name, and
a different value in the build gives a different limit in the built page, so the two cannot drift. Part 3 runs the page's own check
(titleProblem, bundled with the pinned esbuild, run in node; no browser) at the built limit: the limit itself passes, one more is refused.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

import build_page  # noqa: E402
import esbuild  # noqa: E402
from clark import changes  # noqa: E402
from test_work_items import load_demo  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"
PEEK_TITLE = SRC / "edit" / "PeekTitle.jsx"
NAME = "__CLARK_ITEM_TITLE_MAX__"
ACTION = "TUL-A-002"                    # a demo action


def bundle(entry_text, tmp, limits=None, name="t.cjs"):
    """A node-run bundle of entry_text (a module living in the page's source folder) with the build's flags; `limits` stands in for
    build_page.page_limits for this one build."""
    entry = tmp / "entry.js"
    entry.write_text(entry_text, encoding="utf-8")
    out = tmp / name
    real = build_page.page_limits
    if limits is not None:
        build_page.page_limits = lambda: limits
    try:
        done = esbuild.run(["--bundle", "--format=cjs", "--platform=node", "--tsconfig-raw={}", *build_page.preact_flags(),
                            f"--alias:@src={SRC}", str(entry), f"--outfile={out}"], cwd=str(tmp), capture_output=True, text=True)
    finally:
        build_page.page_limits = real
    assert done.returncode == 0, done.stderr
    return out


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.code = next(iter(cls.ids))
        cls.change = staticmethod(changes.make_change(cls.store.path, [], "Demo User"))

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def title(self):
        return next(a for a in self.store.data_for(self.code)["actions"] if a["id"] == ACTION)["description"]

    def send(self, text):
        return self.change({"project": self.code, "kind": "actions", "op": "update", "id": ACTION, "changes": {"description": text}, "place": "peek"})

    def test_a_title_of_the_limit_is_saved_and_one_more_is_refused(self):
        was = self.title()
        code, body = self.send("t" * changes.ITEM_TITLE_MAX)
        self.assertEqual((code, body.get("ok")), (200, True), body)
        self.assertEqual(len(self.title()), changes.ITEM_TITLE_MAX)
        code, body = self.send("t" * (changes.ITEM_TITLE_MAX + 1))
        self.assertNotEqual(code, 200, "one character over the limit is refused")
        self.assertEqual(len(self.title()), changes.ITEM_TITLE_MAX, "nothing was written by the refused change")
        self.send(was)


class Source(unittest.TestCase):
    def test_peek_title_holds_no_number_of_its_own(self):
        text = PEEK_TITLE.read_text(encoding="utf-8")
        line = next(x for x in text.splitlines() if "export const TITLE_ITEM_MAX" in x)
        self.assertIn(NAME, line, "the limit is read from the name the build defines")
        code = re.sub(r"//.*", "", text)                       # comments may quote the number
        self.assertEqual(re.findall(r"(?<![\w.])\d{2,}(?![\w.])", code), [], "no number of two digits or more is written in PeekTitle.jsx")

    def test_the_build_writes_the_servers_constant_under_that_name(self):
        self.assertEqual(build_page.page_limits(), {NAME: changes.ITEM_TITLE_MAX})
        self.assertIn(f"--define:{NAME}={changes.ITEM_TITLE_MAX}", build_page.preact_flags())


@unittest.skipUnless(shutil.which("node"), "no node")
class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark-title-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.tmp), ignore_errors=True)

    def test_a_different_value_in_the_build_is_a_different_limit_in_the_built_page(self):
        for n in (changes.ITEM_TITLE_MAX, 77):
            out = bundle('export { TITLE_ITEM_MAX } from "@src/edit/PeekTitle.jsx";', self.tmp, {NAME: n}, f"max{n}.cjs")
            built = out.read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"TITLE_ITEM_MAX\s*=\s*(\d+)", built), [str(n)], "the built page holds the limit the build was given")
            self.assertNotIn(NAME, built, "nothing is left to read at run time")

    def test_the_pages_own_check_passes_the_limit_and_refuses_one_more(self):
        out = bundle('export { titleProblem } from "@src/edit/actions.js";'
                     f'export const MAX = {changes.ITEM_TITLE_MAX};', self.tmp, None, "check.cjs")
        # the page's check at the limit the server holds (PeekTitle.jsx passes TITLE_ITEM_MAX to it, the one number above)
        stand_in = ("globalThis.addEventListener = () => {}; globalThis.removeEventListener = () => {}; globalThis.window = globalThis;"
                    "globalThis.location = { search: '', hash: '', pathname: '/', href: 'http://x/' };"
                    "globalThis.document = { addEventListener() {}, querySelector() { return null; }, documentElement: { dataset: {} } };"
                    "const kept = {}; globalThis.localStorage = { getItem: k => kept[k] ?? null, setItem: (k, v) => { kept[k] = v; }, removeItem: k => { delete kept[k]; } };")
        js = (stand_in + "const m = require(process.argv[1]);"
              "const n = " + str(changes.ITEM_TITLE_MAX) + ";"
              "console.log(JSON.stringify([m.titleProblem('t'.repeat(n), n), m.titleProblem('t'.repeat(n + 1), n)]));")
        done = subprocess.run(["node", "-e", js, str(out)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        ok, over = json.loads(done.stdout)
        self.assertEqual(ok, "", "a title of the limit is allowed")
        self.assertIn(str(changes.ITEM_TITLE_MAX), over)
        self.assertIn("at most", over, "one more is refused with the page's own sentence")


if __name__ == "__main__":
    unittest.main()
