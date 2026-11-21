"""Row 1251: the six sample pictures are shipped files (src/clark/page/sample-pictures/), made by clark, pinned, inlined in the editing
page only. Run: python3 dev/run_tests.py test_sample_pictures_1251 (no browser). Fictional data only.
"""
import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, TOOLS  # noqa: F401  (puts src/ and dev/tools/ on the path)
import build_page
from clark import sample_images

FOLDER = ROOT / "src" / "clark" / "page" / "sample-pictures"
PAGE = ROOT / "src" / "clark" / "page"


def uri(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


class Shipped(unittest.TestCase):
    def test_six_files_each_what_clark_draws_and_all_different(self):
        files = [(FOLDER / f"sample-{i}.png").read_bytes() for i in range(1, 7)]
        self.assertEqual(files, [sample_images.sample_png(640, 360, i) for i in range(6)])
        self.assertEqual(len(set(files)), 6)
        self.assertEqual(sample_images.VARIANTS, 6)

    def test_no_other_file_is_in_the_folder_and_each_is_small(self):
        self.assertEqual(sorted(p.name for p in FOLDER.iterdir()), [f"sample-{i}.png" for i in range(1, 7)])
        self.assertLess(sum(p.stat().st_size for p in FOLDER.iterdir()), 100 * 1024)

    def test_the_first_variant_is_the_one_picture_unchanged(self):
        self.assertEqual(sample_images.sample_png(), sample_images.sample_png(variant=0))

    def test_the_pins_match(self):
        pins = json.loads((TOOLS / "sample_pins.json").read_text(encoding="utf-8"))
        self.assertEqual(pins, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in FOLDER.iterdir()})


class Build(unittest.TestCase):
    def test_the_editing_build_gets_six_and_the_published_build_none(self):
        got = json.loads(build_page.sample_pictures_path(True).read_text(encoding="utf-8").removeprefix("export default ").rstrip().rstrip(";"))
        self.assertEqual(got, [uri((FOLDER / f"sample-{i}.png").read_bytes()) for i in range(1, 7)])
        self.assertEqual(build_page.sample_pictures_path(False).read_text(encoding="utf-8").strip(), "export default [];")

    def test_a_wrong_pin_or_a_missing_file_refuses_the_build(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for i in range(1, 7):
                (d / f"sample-{i}.png").write_bytes((FOLDER / f"sample-{i}.png").read_bytes())
            pins = d / "pins.json"
            pins.write_text(json.dumps({f"sample-{i}.png": "0" * 64 for i in range(1, 7)}), encoding="utf-8")
            with self.assertRaises(build_page.PictureError):
                build_page.sample_pictures_path(True, d, pins)
            (d / "sample-3.png").unlink()
            with self.assertRaises(build_page.PictureError):
                build_page.sample_pictures_path(True, d, pins)

    def test_the_editing_page_carries_each_picture_and_the_published_page_none(self):
        edit = (PAGE / "page.html").read_text(encoding="utf-8")
        view = (PAGE / "page-view.html").read_text(encoding="utf-8")
        for i in range(1, 7):
            b64 = base64.b64encode((FOLDER / f"sample-{i}.png").read_bytes()).decode("ascii")
            self.assertIn(b64, edit)
            self.assertNotIn(b64, view)


if __name__ == "__main__":
    unittest.main()
