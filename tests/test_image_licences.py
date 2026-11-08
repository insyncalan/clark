"""#637: the licence papers for the container image (dev/tools/image_licences.py, development only).

Run: python3 dev/run_tests.py test_image_licences
Reads fixtures and the repo's own files; runs no Docker and downloads nothing.
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT
import image_licences as il

STATUS = """Package: bash
Status: install ok installed
Architecture: amd64
Version: 5.2.15-2+b7
Description: GNU Bourne Again SHell

Package: libc6
Status: install ok installed
Architecture: amd64
Source: glibc (2.36-9+deb12u10)
Version: 2.36-9+deb12u10
Description: GNU C Library

Package: libssl3
Status: install ok installed
Architecture: amd64
Source: openssl
Version: 3.0.17-1~deb12u2

Package: oldthing
Status: deinstall ok config-files
Architecture: amd64
Version: 1.0

Package: zlib1g
Status: install ok installed
Architecture: amd64
Source: zlib (1:1.2.13.dfsg-1)
Version: 1:1.2.13.dfsg-1
"""
COPYRIGHT = """@@@ /usr/share/doc/bash/copyright
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Files: *
License: GPL-3+

License: GPL-3+
 This program is free software.
@@@ /usr/share/doc/libc6/copyright
Files: *
License: LGPL-2.1+ and GPL-2+
@@@ /usr/share/doc/libssl3/copyright
Files: *
License: Apache-2.0
@@@ /usr/share/doc/zlib1g/copyright
Files: *
License: Zlib
"""


def described():
    return il.describe(il.parse_status(STATUS), il.split_copyright(COPYRIGHT))


class Parsing(unittest.TestCase):
    def test_only_installed_packages_with_their_source(self):
        by = {p["name"]: p for p in il.parse_status(STATUS)}
        self.assertEqual(["bash", "libc6", "libssl3", "zlib1g"], sorted(by))        # oldthing was removed
        self.assertEqual(("glibc", "2.36-9+deb12u10"), (by["libc6"]["source"], by["libc6"]["source_version"]))
        self.assertEqual(("bash", "5.2.15-2+b7"), (by["bash"]["source"], by["bash"]["source_version"]))
        self.assertEqual(("openssl", "3.0.17-1~deb12u2"), (by["libssl3"]["source"], by["libssl3"]["source_version"]))

    def test_copyright_files_are_split_by_package(self):
        self.assertEqual({"bash", "libc6", "libssl3", "zlib1g"}, set(il.split_copyright(COPYRIGHT)))

    def test_licences_are_read_from_license_lines(self):
        self.assertEqual(["GPL-2+", "LGPL-2.1+"], il.licences_of("Files: *\nLicense: LGPL-2.1+ and GPL-2+\n"))
        self.assertEqual(["Apache-2.0"], il.licences_of("see the Apache License, Version 2.0"))
        self.assertEqual([], il.licences_of(""))


class Copyleft(unittest.TestCase):
    def test_gpl_and_lgpl_in_every_spelling_need_source(self):
        for name in ("GPL-3+", "GPL-2", "LGPL-2.1+", "LGPL-3", "AGPL-3", "GPL-2.0-only", "GPL-3.0-or-later"):
            with self.subTest(name=name):
                self.assertTrue(il.needs_source([name]))

    def test_permissive_licences_do_not(self):
        for name in ("MIT", "Apache-2.0", "Zlib", "BSD-3-clause", "PSF-2.0", "ISC", "Expat"):
            with self.subTest(name=name):
                self.assertFalse(il.needs_source([name]))

    def test_a_mix_needs_source(self):
        self.assertTrue(il.needs_source(["MIT", "GPL-2+"]))

    def test_a_package_with_no_copyright_file_is_listed_not_dropped(self):
        rows = il.describe(il.parse_status(STATUS), {})
        self.assertTrue(all(p["copyleft"] for p in rows))
        self.assertTrue(il.render_source_list(rows))

    def test_the_source_list_holds_the_source_packages_of_copyleft_binaries_once(self):
        self.assertEqual([("bash", "5.2.15-2+b7"), ("glibc", "2.36-9+deb12u10")], il.source_packages(described()))
        self.assertNotIn("openssl", il.render_source_list(described()))
        self.assertNotIn("zlib", il.render_source_list(described()))


class Outputs(unittest.TestCase):
    def test_the_sbom_is_cyclonedx_with_every_package_and_purl(self):
        sbom = il.render_sbom(described(), [{"name": "pip", "version": "24.0"}], "python:3.12.12-slim-bookworm")
        self.assertEqual(("CycloneDX", "1.5"), (sbom["bomFormat"], sbom["specVersion"]))
        names = [c["name"] for c in sbom["components"]]
        self.assertEqual(["bash", "libc6", "libssl3", "zlib1g", "pip"], names)
        libc = sbom["components"][1]
        self.assertEqual("pkg:deb/debian/libc6@2.36-9+deb12u10?arch=amd64", libc["purl"])
        self.assertEqual({"LGPL-2.1+", "GPL-2+"}, {x["license"]["name"] for x in libc["licenses"]})
        self.assertEqual("pkg:pypi/pip@24.0", sbom["components"][-1]["purl"])
        json.dumps(sbom)

    def test_the_text_names_every_package_and_the_source_owed(self):
        text = il.render_third_party(described(), [], "python:3.12.12-slim-bookworm")
        for needle in ("python:3.12.12-slim-bookworm", "bash 5.2.15-2+b7: GPL-3+", "libssl3 3.0.17-1~deb12u2: Apache-2.0",
                       "whose source is owed (2)", "source package glibc 2.36-9+deb12u10", "image-source-packages.txt"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertNotIn("zlib1g 1:1.2.13.dfsg-1 (source package", text)         # not owed

    def test_the_command_line_writes_the_three_files_from_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "status").write_text(STATUS)
            (tmp / "copyright").write_text(COPYRIGHT)
            (tmp / "pip.json").write_text('[{"name": "pip", "version": "24.0"}]')
            code = il.main(["--status", str(tmp / "status"), "--copyright", str(tmp / "copyright"), "--pip", str(tmp / "pip.json"),
                            "--out", str(tmp / "out")])
            self.assertEqual(0, code)
            self.assertEqual(["THIRD-PARTY-IMAGE.txt", "image-sbom.cdx.json", "image-source-packages.txt"],
                             sorted(p.name for p in (tmp / "out").iterdir()))
            self.assertEqual("bash 5.2.15-2+b7\nglibc 2.36-9+deb12u10\n", (tmp / "out" / "image-source-packages.txt").read_text())

    def test_an_empty_status_is_an_error_not_an_empty_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "status").write_text("")
            self.assertEqual(1, il.main(["--status", str(Path(tmp, "status")), "--out", str(Path(tmp, "out"))]))

    def test_the_image_dump_stream_is_parsed(self):
        stream = STATUS + "@@@@@@STATUS-END\n" + COPYRIGHT + "\n@@@@@@COPYRIGHT-END\n[{\"name\": \"pip\", \"version\": \"24.0\"}]\n"
        status, copyrights, pip = il.parse_dump(stream)
        self.assertEqual(4, len(il.parse_status(status)))
        self.assertIn("libc6", copyrights)
        self.assertEqual([{"name": "pip", "version": "24.0"}], pip)


class RepoFiles(unittest.TestCase):
    def test_the_container_runs_only_a_pinned_stock_image_and_installs_nothing(self):
        compose = (ROOT / "docker" / "compose.yaml").read_text()
        images = re.findall(r"^\s*image:\s*(\S+)", compose, re.M)
        self.assertEqual(1, len(images))
        self.assertRegex(images[0], r"^python:\d+\.\d+\.\d+-slim-[a-z]+(@sha256:[0-9a-f]{64})?$")    # an exact version, never latest
        self.assertFalse((ROOT / "docker" / "Dockerfile").exists(), "a Dockerfile would make an image of ours: the paper list covers the stock one")
        self.assertNotRegex(compose, r"(?m)^\s*(build|pull_policy):")
        for line in compose.splitlines():
            if not line.lstrip().startswith("#"):
                self.assertNotRegex(line, r"apt(-get)? install|pip install")

    def test_notice_has_an_image_section_naming_the_base_and_the_source(self):
        notice = (ROOT / "NOTICE.md").read_text()
        self.assertIn("## The container image", notice)
        section = notice.split("## The container image", 1)[1].split("\n## ", 1)[0]
        image = re.search(r"^\s*image:\s*(\S+)", (ROOT / "docker" / "compose.yaml").read_text(), re.M).group(1).split("@")[0]
        for needle in (image, "THIRD-PARTY-IMAGE.txt", "image-sbom.cdx.json", "image-source", "PSF", "Apache", "GPL", "LGPL"):
            with self.subTest(needle=needle):
                self.assertIn(needle, section)


if __name__ == "__main__":
    unittest.main()
