"""#637: the image licence list. Pure parts with made-up data; the compose file's image line and the docker folder are checked
as text. No Docker is run. Run: python3 dev/run_tests.py test_image_licences
"""
import json
import os
import re
import shutil
import unittest

from _paths import ROOT
import image_licences as il

DPKG = "libc6:amd64\t2.36-9\tglibc\nbash\t5.2.15-2\tbash\nbad line\n\tx\ty\nzlib1g:amd64\t1:1.2.13\t\n"
COPYRIGHT = "Format: x\n\nFiles: *\nCopyright: a\nLicense: GPL-2+\n\nFiles: b\nLicense: LGPL-2.1+\n\nLicense: GPL-2+\n Text here\n"


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class ParseTests(unittest.TestCase):
    def test_dpkg_rows_sorted_and_bad_lines_skipped(self):
        self.assertEqual(il.parse_dpkg(DPKG), [("bash", "5.2.15-2", "bash"), ("libc6:amd64", "2.36-9", "glibc"),
                                               ("zlib1g:amd64", "1:1.2.13", "zlib1g:amd64")])

    def test_pip_rows_sorted_and_junk_gives_nothing(self):
        self.assertEqual(il.parse_pip(json.dumps([{"name": "wheel", "version": "1"}, {"name": "Pip", "version": "2"}, 5, {"name": "x"}])),
                         [("Pip", "2"), ("wheel", "1")])
        self.assertEqual(il.parse_pip("not json"), [])
        self.assertEqual(il.parse_pip("{}"), [])

    def test_copyright_licences_in_order_without_repeats(self):
        self.assertEqual(il.copyright_licences(COPYRIGHT), ["GPL-2+", "LGPL-2.1+"])
        self.assertEqual(il.copyright_licences("Free text, no stanza."), [])

    def test_copyleft_detection(self):
        for yes in (["GPL-2+"], ["LGPL-2.1+"], ["MIT", "AGPL-3"]):
            self.assertTrue(il.is_copyleft(yes), yes)
        for no in ([], ["MIT"], ["Expat", "BSD-3-clause"]):
            self.assertFalse(il.is_copyleft(no), no)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.deb = il.parse_dpkg(DPKG)
        self.text = il.render_text("img:1", self.deb, [("pip", "24.0")], {"bash": ["GPL-3+"], "libc6:amd64": ["MIT"]})

    def test_lists_every_package_once(self):
        for line in ("bash 5.2.15-2 (source package bash): GPL-3+", "libc6:amd64 2.36-9 (source package glibc): MIT", "pip 24.0"):
            self.assertEqual(self.text.count(line), 1, line)

    def test_unreadable_licence_points_at_the_copyright_file_and_needs_source(self):
        self.assertIn("see /usr/share/doc/zlib1g:amd64/copyright in the image", self.text)
        tail = self.text.split("## Source packages")[1]
        self.assertIn("bash", tail)
        self.assertIn("zlib1g:amd64", tail)
        self.assertNotIn("glibc", tail)       # MIT, readable: no source duty listed

    def test_packages_txt_is_sorted_lines(self):
        self.assertEqual(il.packages_txt(self.deb, [("pip", "24.0")]),
                         "deb bash 5.2.15-2\ndeb libc6:amd64 2.36-9\ndeb zlib1g:amd64 1:1.2.13\npip pip 24.0\n")

    def test_json_round_trips(self):
        d = json.loads(il.packages_json("img:1", self.deb, [("pip", "24.0")]))
        self.assertEqual((d["image"], len(d["debian"]), d["pip"][0]["name"]), ("img:1", 3, "pip"))

    def test_main_refuses_without_an_image(self):
        self.assertEqual(il.main([]), 2)
        self.assertEqual(il.main(["--bogus"]), 2)


class ComposeImageTests(unittest.TestCase):
    """The plan's static checks: the shipped image is one exact tag, and nothing in docker/ installs anything."""

    def test_image_is_an_exact_pinned_slim_tag(self):
        images = re.findall(r"^\s*image:\s*(\S+)\s*$", read("docker", "compose.yaml"), re.M)
        self.assertEqual(len(images), 1)
        self.assertRegex(images[0], r"^python:\d+\.\d+\.\d+-slim-bookworm(@sha256:[0-9a-f]{64})?$")

    def test_no_install_step_and_no_build_in_docker_folder(self):
        for name in os.listdir(os.path.join(ROOT, "docker")):
            text = read("docker", name)
            self.assertNotRegex(text, r"\b(?:apt(?:-get)?|pip3?)\s+install\b", name)
            self.assertNotRegex(text, r"(?m)^\s*build:", name)
            self.assertNotRegex(text, r"(?m)^FROM\s+\S+:latest", name)

    def test_licence_and_notice_travel_in_the_zip(self):
        import package
        self.assertIn("LICENSE", package.SHARED)
        self.assertIn("NOTICE.md", package.SHARED)


class ImageMatchesListTests(unittest.TestCase):
    """docker/image-packages.txt against the real image. Skipped without Docker, without the image, or without the list file."""

    def test_list_file_matches_the_image(self):
        path = os.path.join(ROOT, "docker", "image-packages.txt")
        if not shutil.which("docker"):
            self.skipTest("Docker is not installed")
        if not os.path.exists(path):
            self.skipTest("docker/image-packages.txt does not exist yet")
        image = re.search(r"^\s*image:\s*(\S+)\s*$", read("docker", "compose.yaml"), re.M).group(1)
        try:
            debian = il.parse_dpkg(il._docker(image, "dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${source:Package}\n"))
            pip = il.parse_pip(il._docker(image, "python3", "-m", "pip", "list", "--format=json"))
        except (OSError, RuntimeError) as e:
            self.skipTest(f"the image could not be read: {e}")
        self.assertEqual(read("docker", "image-packages.txt"), il.packages_txt(debian, pip))


if __name__ == "__main__":
    unittest.main()
