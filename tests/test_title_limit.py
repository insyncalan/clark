"""#942: a work item's title limit has ONE source, changes.ITEM_TITLE_MAX; the page gets it from the build, not from a number of its own.

Run: python3 dev/run_tests.py test_title_limit
Part 1 is the server: a title of ITEM_TITLE_MAX characters is saved, one more is refused, nothing is written. Part 2 is the page source and
build: PeekTitle.jsx holds no number (it reads the name the build defines), the build writes changes.ITEM_TITLE_MAX under that name, and
a different value in the build gives a different limit in the built page, so the two cannot drift. Part 3 runs the page's own check
(titleProblem, bundled with the pinned esbuild, run in node; no browser) at the built limit: the limit itself passes, one more is refused.
"""
import contextlib
import io
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
from clark import changes, page  # noqa: E402
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


class TextFields(unittest.TestCase):
    """#942 follow-up: a work item's other text fields (decision, client wording, workstream, ...) are held to the SAME number as the title,
    read from changes.ITEM_TITLE_MAX, so there is one 200 in changes.py and the two limits cannot drift."""
    FIELDS = ("description", "decision", "client_message", "workstream")

    def test_a_text_field_of_the_limit_is_accepted_and_one_more_is_refused(self):
        for field in self.FIELDS:
            with self.subTest(field=field):
                got = changes._checked_item_changes({field: "t" * changes.ITEM_TITLE_MAX}, blank_clears=("client_message",))
                self.assertEqual(len(got[field]), changes.ITEM_TITLE_MAX)
                with self.assertRaises(changes.Refused):
                    changes._checked_item_changes({field: "t" * (changes.ITEM_TITLE_MAX + 1)}, blank_clears=("client_message",))

    def test_changes_py_holds_the_number_once_for_these_limits(self):
        lim = (ROOT / "src" / "clark" / "limits.py").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"^ITEM_TITLE_MAX\s*=\s*200\b", lim, re.M)), 1, "the one literal, in limits.py")
        src = (ROOT / "src" / "clark" / "changes.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^ITEM_TITLE_MAX\s*=", src, re.M), [], "changes.py imports it, it holds no number of its own")
        self.assertEqual(re.findall(r"len\([^)]*\)\s*>\s*200\b", src), [], "a length limit written as a bare 200; use changes.ITEM_TITLE_MAX")

    def test_the_page_files_that_count_a_title_read_the_build_not_a_200(self):
        for name in ("movementWords.js", "ItemRowsEdit.jsx"):
            text = (SRC / "edit" / name).read_text(encoding="utf-8")
            self.assertEqual(len(re.findall(r"^export const (?:TITLE_MAX|WORDS_MAX) = " + NAME + r";", text, re.M)), 1, f"{name} reads {NAME}")
            self.assertEqual(re.findall(r"^export const (?:TITLE_MAX|WORDS_MAX) = \d", text, re.M), [], f"{name} holds no number of its own")


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


class Stamp(unittest.TestCase):
    """The pages are stale when the source stamp differs from the committed one, so every file the build reads must be in the stamp.
    limits.py supplies the title limit the build writes into the page: if it were left out, a new number would leave stale pages."""

    def test_limits_py_is_a_build_input(self):
        self.assertIn(ROOT / "src" / "clark" / "limits.py", page.build_inputs())

    def test_the_stamp_changes_when_the_limit_changes(self):
        import pathlib
        from unittest import mock
        lim = ROOT / "src" / "clark" / "limits.py"
        real = pathlib.Path.read_bytes
        before = page.source_stamp()

        def other(self):
            return real(self) + (b"\nITEM_TITLE_MAX = 201\n" if self == lim else b"")
        with mock.patch.object(pathlib.Path, "read_bytes", other):
            self.assertNotEqual(page.source_stamp(), before, "a different limit gives a different stamp")
        self.assertEqual(page.source_stamp(), before)

    def test_the_served_page_was_built_with_the_servers_limit(self):
        """What build_page.py --check does, so a stale page.html fails by name: the page the server serves equals a fresh build."""
        page.ensure_built()
        self.assertEqual(page.PAGE.read_text(encoding="utf-8"), build_page.build(build_page.ENTRY))
        for p in (page.PAGE, page.VIEW_PAGE):
            self.assertNotIn(NAME, p.read_text(encoding="utf-8"), p.name)

    def test_page_limits_refuses_a_value_that_is_not_a_whole_number_of_at_least_one(self):
        import types
        real = build_page.limits
        self.addCleanup(setattr, build_page, "limits", real)
        for bad in (None, "x", 0, -1, True):
            with self.subTest(bad=bad):
                build_page.limits = types.SimpleNamespace(ITEM_TITLE_MAX=bad)
                with self.assertRaises(build_page.BuildError) as got:
                    build_page.page_limits()
                self.assertIn("ITEM_TITLE_MAX", str(got.exception))
        build_page.limits = types.SimpleNamespace(ITEM_TITLE_MAX=1)
        self.assertEqual(build_page.page_limits(), {NAME: 1}, "1 is the smallest limit the build takes")

    def test_page_limits_raises_and_never_defaults(self):
        import types
        real = build_page.limits
        build_page.limits = types.SimpleNamespace()      # a limits module without the number
        self.addCleanup(setattr, build_page, "limits", real)
        with self.assertRaises(AttributeError):
            build_page.page_limits()


class MissingDefine(unittest.TestCase):
    """The page reads the limit under a name only the build defines. If the build stops defining it, the name stays in the page as a bare
    identifier and the page throws when it runs: so the BUILD refuses, naming it, instead of writing that page."""

    def with_limits(self, limits):
        real = build_page.page_limits
        build_page.page_limits = lambda: limits
        self.addCleanup(setattr, build_page, "page_limits", real)

    def test_a_build_that_does_not_define_the_limit_is_refused_naming_it(self):
        self.with_limits({})
        with self.assertRaises(build_page.BuildError) as got:
            build_page.preact_flags()
        self.assertIn(NAME, str(got.exception), "the refusal names the missing definition")

    def test_the_build_command_stops_with_a_refusal_and_writes_nothing(self):
        self.with_limits({})
        before = [(f, f.read_bytes() if f.exists() else None) for f in (build_page.OUT, build_page.OUT_VIEW)]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            done = build_page.main([])
        self.assertEqual(done, 1, "build_page exits with 1")
        self.assertIn(NAME, err.getvalue(), "and says which definition is missing")
        self.assertEqual(before, [(f, f.read_bytes() if f.exists() else None) for f in (build_page.OUT, build_page.OUT_VIEW)], "no page was written")

    def test_a_name_left_in_the_built_script_is_refused(self):
        real = build_page.preact_flags
        build_page.preact_flags = lambda held=True, inline_pictures=False: [f for f in real(held, inline_pictures) if not f.startswith("--define:")]
        self.addCleanup(setattr, build_page, "preact_flags", real)
        with self.assertRaises(build_page.BuildError) as got:
            build_page.bundle(build_page.ENTRY)      # the editing page: PeekTitle is in it, not in the published page
        self.assertIn(NAME, str(got.exception), "the refusal names the identifier left in the script")

    def test_a_clean_build_of_every_page_has_no_name_left(self):
        for entry in (build_page.ENTRY, build_page.ENTRY_VIEW):
            self.assertNotIn(NAME, build_page.build(entry), f"{entry} carries a number, not the name")


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
