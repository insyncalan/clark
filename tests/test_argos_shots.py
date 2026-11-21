"""Argos step 1 (dev/tools/argos_shots.py): the cap, the file names, the widths, the Classic theme, the output folder and one small real run.

Run: python3 dev/run_tests.py test_argos_shots
The real run needs Chrome and is skipped without it."""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

sys.path.insert(0, str(ROOT / "dev" / "tools"))
import argos_shots as A  # noqa: E402
from test_server import CHROME  # noqa: E402

NAME = re.compile(r"^[0-9]+-[a-z0-9-]+-(1400|900)\.png$")
PNG = b"\x89PNG\r\n\x1a\n"


class Limit(unittest.TestCase):
    def test_more_than_the_cap_saves_exactly_the_cap_and_counts_the_rest(self):
        many = [(str(1000 + i), "screen", "#settings") for i in range(30)]       # 60 candidates
        with tempfile.TemporaryDirectory() as d:
            saved, dropped = A.save_all(d, lambda how, w: PNG, screens=many)
            self.assertEqual((len(saved), dropped, A.MAX_SHOTS), (40, 20, 40))
            self.assertEqual(len(list(Path(d).glob("*.png"))), 40)

    def test_under_the_cap_drops_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            saved, dropped = A.save_all(d, lambda how, w: PNG)
            self.assertEqual((len(saved), dropped), (len(A.SCREENS) * 2, 0))


class Options(unittest.TestCase):
    def test_width_1400_only_saves_1400_names(self):
        with tempfile.TemporaryDirectory() as d:
            saved, dropped = A.save_all(d, lambda how, w: PNG, widths=(1400,))
            self.assertEqual((len(saved), dropped), (len(A.SCREENS), 0))
            for n in saved:
                self.assertTrue(n.endswith("-1400.png"), n)
            self.assertEqual(sorted(p.name for p in Path(d).glob("*.png")), sorted(saved))

    def test_parse_widths_default_repeat_and_out(self):
        self.assertEqual(A.parse(["x"]), (Path("screenshots"), (1400, 900)))
        self.assertEqual(A.parse(["x", "--width", "1400"])[1], (1400,))
        self.assertEqual(A.parse(["x", "--width", "900", "--width", "1400"])[1], (900, 1400))
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(A.parse(["x", "--out", d, "--width", "1400"]), (Path(d), (1400,)))

    def test_width_700_exits_2_with_a_message(self):
        r = subprocess.run([sys.executable, str(ROOT / "dev" / "tools" / "argos_shots.py"), "--width", "700"],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2)
        self.assertIn("invalid choice", r.stderr)

    def test_out_directory_is_used(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "new" / "shots"
            A.save_all(out, lambda how, w: PNG, widths=(900,))
            self.assertEqual(len(list(out.glob("*-900.png"))), len(A.SCREENS))


class Table(unittest.TestCase):
    def test_every_name_matches_the_pattern(self):
        names = [n for n, _, _ in A.candidates()]
        self.assertTrue(names)
        for n in names:
            self.assertRegex(n, NAME)
        self.assertEqual(len(names), len(set(names)))

    def test_widths_are_only_1400_and_900(self):
        self.assertEqual(A.WIDTHS, (1400, 900))
        self.assertEqual({w for _, _, w in A.candidates()}, {1400, 900})

    def test_the_theme_is_classic(self):
        self.assertEqual(A.THEME, "prototype-2.0")
        self.assertIn("theme=THEME", (ROOT / "dev" / "tools" / "argos_shots.py").read_text(encoding="utf-8"))

    def test_screens_are_small_and_each_starts_at_a_fragment(self):
        self.assertLessEqual(len(A.SCREENS), 8)
        for t, s, how in A.SCREENS:
            self.assertTrue(how.startswith("#"))

    def test_the_output_folder_is_not_committed(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertTrue(any(l.strip().strip("/") == "screenshots" for l in lines))


@unittest.skipUnless(CHROME and Path(CHROME).is_file(), "Chrome is not available")
class RealRun(unittest.TestCase):
    def test_one_screen_is_saved_as_a_png_at_both_widths(self):
        with tempfile.TemporaryDirectory() as d:
            code = ("import sys; sys.path.insert(0, %r); import argos_shots as A; A.SCREENS[:] = A.SCREENS[:1]; sys.exit(A.main(['x', '--out', %r]))"
                    % (str(ROOT / "dev" / "tools"), d))
            r = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True, timeout=300)
            self.assertEqual(r.returncode, 0, r.stderr[-800:])
            files = sorted(p.name for p in Path(d).glob("*.png"))
            self.assertEqual(files, ["1299-projects-overview-1400.png", "1299-projects-overview-900.png"])
            for f in files:
                self.assertEqual((Path(d) / f).read_bytes()[:8], PNG)


if __name__ == "__main__":
    unittest.main()
