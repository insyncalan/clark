"""#642 step 5: the Help pictures (src/clark/page/help-pictures/), checked without a browser.

Run: python3 dev/run_tests.py test_help_pictures
Covers the size budget (3 MB in all), that the shots list (dev/tools/help_shots.json) and the folder name the same pictures, that no
picture is dark, that neither built page holds the folder (a published file has no Help), that the Help content only names listed
pictures, that the shots list is well formed, and that the script refuses any data folder that is not the demo data. The retake
itself (python3 dev/tools/help_pictures.py, and --check) needs the browser and is a separate, documented step.
"""
import json
import importlib
import re
import subprocess
import time
import types
from unittest import mock
import struct
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stderr
from datetime import datetime
from io import StringIO
from pathlib import Path

from _paths import ROOT, TOOLS  # noqa: F401  (puts src/, dev/tools/ and vendor/ on the path)
from _demo import DemoStore
from clark import page

sys.path.insert(0, str(ROOT / "dev"))
import demo_data  # noqa: E402
import help_pictures as hp  # noqa: E402

FOLDER = ROOT / "src" / "clark" / "page" / "help-pictures"
CONTENT = ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"
BUDGET = 3 * 1024 * 1024


def listed():
    return hp.shot_ids()


def brightness(data, rows=40):
    """How bright the lightest quarter of the top `rows` rows of a plain 8-bit PNG is (0 to 255): a light picture has a good deal of
    white in it (the page's own background round the control), a dark one has none. Only those rows are decoded."""
    pos, ihdr, idat = 8, None, []
    while pos < len(data):
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + size]
        pos += 12 + size
        if kind == b"IHDR":
            ihdr = body
        elif kind == b"IDAT":
            idat.append(body)
    width, height, depth, ctype, _c, _f, interlace = struct.unpack(">IIBBBBB", ihdr)
    assert depth == 8 and interlace == 0 and ctype in (2, 6), "an 8-bit RGB or RGBA picture"
    bpp, stride = (3 if ctype == 2 else 4), width * (3 if ctype == 2 else 4)
    raw = zlib.decompress(b"".join(idat))
    prev, values = bytearray(stride), []
    for r in range(min(rows, height)):
        ftype, row = raw[r * (stride + 1)], bytearray(raw[r * (stride + 1) + 1:(r + 1) * (stride + 1)])
        for i in range(stride):
            a = row[i - bpp] if i >= bpp else 0
            b, c = prev[i], (prev[i - bpp] if i >= bpp else 0)
            if ftype == 1:
                row[i] = (row[i] + a) & 255
            elif ftype == 2:
                row[i] = (row[i] + b) & 255
            elif ftype == 3:
                row[i] = (row[i] + (a + b) // 2) & 255
            elif ftype == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        values += [sum(row[i:i + 3]) / 3 for i in range(0, stride, bpp)]
        prev = row
    return sorted(values)[len(values) * 3 // 4]


class Folder(unittest.TestCase):
    def test_every_listed_picture_has_a_file_and_every_file_is_listed(self):
        files = {p.stem for p in FOLDER.glob("*.png")}
        self.assertEqual(set(listed()), files)
        self.assertEqual([p.name for p in FOLDER.iterdir() if p.suffix != ".png"], [], "only pictures are in the folder")

    def test_the_pictures_are_within_the_budget(self):
        total = sum(p.stat().st_size for p in FOLDER.glob("*.png"))
        self.assertLessEqual(total, BUDGET, f"{total / 1024:.0f} KB in all; the owner's budget is 3 MB")

    def test_every_file_is_a_png_and_none_is_dark(self):
        for p in FOLDER.glob("*.png"):
            data = p.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", p.name)
            self.assertGreater(brightness(data), 200, f"{p.name} looks dark: pictures are light only")

    def test_a_picture_is_taken_at_scale_one(self):
        self.assertEqual((hp.WIDTH, hp.SCALE), (1400, 1))

    def test_the_built_pages_do_not_carry_the_folder(self):
        page.ensure_built()
        for built in (page.PAGE, page.VIEW_PAGE):
            self.assertNotIn("help-pictures", built.read_text(encoding="utf-8"), f"{built.name} must carry no Help picture")

    def test_the_content_only_names_listed_pictures(self):
        content = json.loads(CONTENT.read_text(encoding="utf-8"))
        self.assertLessEqual(set(content.get("pictures", [])), set(listed()))


class Shots(unittest.TestCase):
    def test_the_list_is_well_formed_and_every_guide_has_two_shots(self):
        by_guide = {}
        for s in hp.load_shots():
            by_guide.setdefault(s["guide"], []).append(s["id"])
        self.assertEqual(set(by_guide), {"templates", "arrange", "excel-in", "excel-out", "publish"})
        for guide, ids in by_guide.items():
            self.assertGreaterEqual(len(ids), 2, guide)

    def test_a_shot_has_no_theme_choice(self):
        text = (ROOT / "dev" / "tools" / "help_shots.json").read_text(encoding="utf-8")
        self.assertNotIn("dark", text.lower())

    def test_every_name_in_a_selector_is_in_the_page_code(self):
        """Not the browser's check (--check is), but a quick one: each id, class and data attribute in a selector is written in the source."""
        src = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "clark" / "page").rglob("*")
                        if p.suffix in (".jsx", ".js", ".css") and "help-pictures" not in str(p))
        for s in hp.load_shots():
            sels = hp.crop_list(s) + [m["ring"] for m in s.get("marks", [])] + [v for st in s.get("steps", []) for k, v in st.items() if k not in ("mode", "away")]
            for sel in sels:
                names = re.findall(r"[#.]([A-Za-z][\w-]*)|\[(data-[\w-]+)", sel)
                self.assertTrue(names, sel)
                for name in [a or b for a, b in names]:
                    self.assertIn(name, src, f"{s['id']}: {name} in {sel} is not in the page code")

    def test_a_bad_list_is_refused_plainly(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "shots.json"
            f.write_text(json.dumps({"shots": [{"id": "Bad Id", "screen": "#x", "crop": "a"}]}), encoding="utf-8")
            with self.assertRaisesRegex(hp.Refused, "no usable id"):
                hp.load_shots(f)

    def test_the_optimiser_keeps_the_pixels(self):
        for p in list(FOLDER.glob("*.png"))[:3]:
            data = p.read_bytes()
            again = hp.optimise_png(data)
            self.assertLessEqual(len(again), len(data))
            self.assertEqual(brightness(again), brightness(data))


class OnlyDemoData(unittest.TestCase):
    def test_an_empty_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            err = StringIO()
            with redirect_stderr(err):
                self.assertEqual(hp.main(["--check", "--data", d]), 1)
            self.assertIn("does not hold the fictional demo data", err.getvalue())

    def test_a_folder_with_other_data_is_refused(self):
        with DemoStore() as store:
            err = StringIO()
            with redirect_stderr(err):
                self.assertEqual(hp.main(["--check", "--data", str(store.path.parent)]), 1)
            self.assertIn("does not hold the fictional demo data", err.getvalue())

    def test_the_demo_folder_is_let_through(self):
        with tempfile.TemporaryDirectory() as d:
            demo_data.build(Path(d) / "clark.db", datetime(2026, 10, 28, 9, 0), onedrive_roots=[])
            self.assertEqual(hp.check_demo_folder(d), Path(d))


def small_png(level=0):
    """A 40 x 40 grey PNG whose pixel data is packed weakly, so packing it again makes it smaller."""
    raw = b"".join(b"\x00" + bytes([200]) * 40 for _ in range(40))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return (hp.PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", 40, 40, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, level))
            + chunk(b"IEND", b"")), raw


class Optimiser(unittest.TestCase):
    def test_a_weakly_packed_picture_gets_smaller_with_the_same_pixels(self):
        data, raw = small_png()
        out = hp.optimise_png(data)
        self.assertLess(len(out), len(data))
        self.assertEqual(zlib.decompress(b"".join(b for k, b in hp._chunks(out) if k == b"IDAT")), raw)

    def test_a_wrong_check_value_in_the_input_leaves_it_as_it_was(self):
        data, _ = small_png()
        bad = bytearray(data)
        bad[-17] ^= 1                                    # the last byte of the pixel data's check value (before the 12-byte IEND)
        self.assertEqual(hp.optimise_png(bytes(bad)), bytes(bad))
        self.assertEqual(hp.optimise_png(data[:-20]), data[:-20], "cut short")

    def test_an_output_that_does_not_decode_to_the_same_pixels_is_not_used(self):
        data, _ = small_png()
        with mock.patch.object(hp, "_deflate", return_value=b"x"):      # smaller than anything real, and not a valid stream
            self.assertEqual(hp.optimise_png(data), data)


class Pins(unittest.TestCase):
    def test_a_missing_unpinned_changed_or_stray_picture_is_named(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            for name, body in (("a", b"1"), ("b", b"2"), ("c", b"3")):
                (Path(d) / f"{name}.png").write_bytes(body)
            pins = {"a.png": hashlib.sha256(b"1").hexdigest(), "b.png": hashlib.sha256(b"other").hexdigest(), "z.png": "0"}
            found = hp.pin_problems(d, pins, ["a", "b", "c", "m"])
            self.assertEqual(found, ["b.png does not match its pin in help_pins.json.", "c.png has no pin in help_pins.json.",
                                     "m.png is missing.", "z.png is pinned but no shot makes it."])
            self.assertEqual(hp.pin_problems(d, {"a.png": pins["a.png"]}, ["a"]), [])

    def test_the_pins_are_written_sorted_and_read_back(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "pins.json"
            hp.write_pins({"b.png": "2", "a.png": "1"}, f)
            self.assertEqual(list(hp.read_pins(f)), ["a.png", "b.png"])
            self.assertEqual(hp.read_pins(Path(d) / "none.json"), {})


class ClarkOutput(unittest.TestCase):
    def clark_with(self, code, seconds):
        c = hp.Clark.__new__(hp.Clark)
        c.port = 4321
        c.LISTEN_SECONDS = seconds
        c.proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.addCleanup(c.stop)
        return c

    def test_a_quiet_clark_is_given_up_on_at_the_limit(self):
        c = self.clark_with("import time; time.sleep(30)", 1)         # prints nothing: a blocking read would wait the 30 s
        t0 = time.monotonic()
        with self.assertRaisesRegex(hp.Refused, "did not start"):
            c.wait_listening()
        self.assertLess(time.monotonic() - t0, 10)

    def test_the_output_is_read_on_after_the_address_so_the_pipe_never_fills(self):
        code = ("import sys\nprint('Open http://127.0.0.1:4321/', flush=True)\n"
                "for _ in range(5000): sys.stdout.write('y' * 1000 + '\\n')\nsys.stdout.flush()")
        c = self.clark_with(code, 20)
        c.wait_listening()
        self.assertEqual(c.proc.wait(20), 0, "5 MB of output did not stop it")


def stub_run_support(start_fails=False):
    calls = []

    def start(command, to_r, from_w):
        if start_fails:
            raise OSError("no")
        calls.append("started")
        return "proc"
    names = {"chrome" + "_path": lambda: "/x", "chrome" + "_command": lambda path, profile: [path], "start" + "_chrome": start,
             "stop" + "_chrome": lambda proc: calls.append("stopped"), "remove" + "_profile": lambda p: calls.append("profile removed")}
    return types.SimpleNamespace(**names), calls


class BrowserCleanUp(unittest.TestCase):
    """The browser half is loaded by name, with the stand-in above for run_support: no browser is started."""

    def test_a_failure_after_the_start_stops_it_and_removes_the_profile(self):
        shoot = importlib.import_module("help_pictures_browser")
        stub, calls = stub_run_support()
        with mock.patch.object(shoot, "run_support", stub), mock.patch.object(shoot.Pipe, "call", side_effect=RuntimeError("closed")):
            with self.assertRaises(RuntimeError):
                shoot.Browser().__enter__()
        self.assertEqual(calls, ["started", "stopped", "profile removed"])

    def test_a_failure_to_start_removes_the_profile(self):
        shoot = importlib.import_module("help_pictures_browser")
        stub, calls = stub_run_support(start_fails=True)
        with mock.patch.object(shoot, "run_support", stub):
            with self.assertRaises(OSError):
                shoot.Browser().__enter__()
        self.assertEqual(calls, ["profile removed"])


if __name__ == "__main__":
    unittest.main()
