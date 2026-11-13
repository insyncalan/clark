"""A brand pack unzipped straight into system/branding (a top pack), and the Downloads pick (src/clark/brands.py).

Pins: remove and undo only ever touch a real installed folder; the listing says when a brand has no folder of its own; local-brand
keeps resolving beside a top pack with its own id; a folder brand beats a top pack of the same id; the Downloads pick needs a
manifest that parses with a plain id, and obeys the size caps and does not follow links. Temp folders only.

Run: python3 dev/run_tests.py test_brands_top_pack
"""
import contextlib
import json
import os
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import _brand_zips as bz
from _brand_rig import branding, make_dirs, write_zip

from clark import brands


def top_pack(root, brand_id="fabrikam", name="Fabrikam", version="2.1.0"):
    top = branding(root)
    (top / "tokens.css").write_text(":root { --brand-ink: #000000; }\n", encoding="utf-8")
    (top / "clark-brand.json").write_text(json.dumps({"id": brand_id, "name": name, "version": version, "files": []}), encoding="utf-8")


def zip_with(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, body in members.items():
            zf.writestr(name, body)
    return Path(path)


class Base(unittest.TestCase):
    def setUp(self):
        self.root, self.data, self.scratch = make_dirs(self)


class Removal(Base):
    def test_remove_refuses_a_folder_that_is_not_an_installed_brand_even_when_the_top_pack_has_its_id(self):
        top_pack(self.root)
        mine = branding(self.root) / "fabrikam"
        mine.mkdir()
        (mine / "notes.txt").write_text("my own files", encoding="utf-8")
        with self.assertRaises(brands.BrandError):
            brands.remove("fabrikam", self.root, self.data)
        self.assertEqual((mine / "notes.txt").read_text(encoding="utf-8"), "my own files")

    def test_remove_refuses_a_top_pack_that_has_no_folder_of_its_own(self):
        top_pack(self.root)
        with self.assertRaises(brands.BrandError):
            brands.remove("fabrikam", self.root, self.data)
        self.assertTrue((branding(self.root) / "tokens.css").exists())

    def test_undo_of_an_install_leaves_a_folder_that_is_not_an_installed_brand(self):
        mine = branding(self.root) / "fabrikam"
        mine.mkdir()
        (mine / "notes.txt").write_text("my own files", encoding="utf-8")
        (self.data / brands.JOURNAL).write_text(json.dumps({"kind": "install", "id": "fabrikam"}), encoding="utf-8")
        with self.assertRaises(brands.BrandError):
            brands.undo(self.root, self.data)
        self.assertTrue((mine / "notes.txt").exists())


class Listing(Base):
    def test_a_top_pack_is_listed_with_no_folder_of_its_own_and_says_local_brand_still_works(self):
        top_pack(self.root)
        got = brands.installed(self.root)
        self.assertEqual([(x["id"], x["name"], x["own_folder"], x["alias"]) for x in got], [("fabrikam", "Fabrikam", False, "local-brand")])
        self.assertEqual(brands.folder(self.root, "local-brand"), branding(self.root))
        self.assertEqual(brands.folder(self.root, "fabrikam"), branding(self.root))

    def test_a_folder_brand_listed_has_no_alias_and_has_its_own_folder(self):
        review = brands.review(write_zip(self.scratch, bz.valid()), self.root)
        brands.install(review["review_id"], self.root, self.data)
        got = brands.installed(self.root)
        self.assertEqual([(x["id"], x.get("own_folder", True), "alias" in x) for x in got], [(bz.BRAND_ID, True, False)])

    def test_a_folder_brand_wins_over_a_top_pack_of_the_same_id(self):
        review = brands.review(write_zip(self.scratch, bz.valid()), self.root)
        brands.install(review["review_id"], self.root, self.data)
        top_pack(self.root, brand_id=bz.BRAND_ID, name="Top Name")
        got = [x for x in brands.installed(self.root) if x["id"] == bz.BRAND_ID]
        self.assertEqual([x["name"] for x in got], ["Example Brand"])
        self.assertEqual(brands.folder(self.root, bz.BRAND_ID), branding(self.root) / bz.BRAND_ID)

    def test_folder_answers_the_top_pack_only_for_its_own_id(self):
        top_pack(self.root)
        for other in ("other-brand", "generic", "assets"):
            self.assertIs(brands.folder(self.root, other), brands.GENERIC, other)

    def test_a_top_pack_whose_id_is_not_plain_or_is_kept_for_clark_is_local_brand_under_its_name(self):
        for bad in ("Bad_ID", "assets", "design-system", "generic", "local-brand", "x" * 41, ""):
            with self.subTest(bad):
                top_pack(self.root, brand_id=bad)
                got = brands.installed(self.root)
                self.assertEqual([(x["id"], x["name"]) for x in got], [("local-brand", "Fabrikam")])

    def test_a_top_pack_with_a_plain_id_but_a_bad_version_or_name_is_the_bare_local_brand_entry(self):
        for field, bad in (("version", "one"), ("version", 2), ("name", ""), ("name", " Fabrikam"), ("name", 7)):
            with self.subTest(field, bad=bad):
                top = branding(self.root)
                (top / "tokens.css").write_text(":root { --brand-ink: #000000; }\n", encoding="utf-8")
                doc = {"id": "fabrikam", "name": "Fabrikam", "version": "2.1.0", "files": []}
                doc[field] = bad
                (top / "clark-brand.json").write_text(json.dumps(doc), encoding="utf-8")
                got = brands.installed(self.root)
                self.assertEqual([(x["id"], x["name"], x["version"], x["own_folder"]) for x in got], [("local-brand", "local-brand", "", False)])

    def test_a_bare_top_tokens_file_is_local_brand_with_no_folder_of_its_own(self):
        (branding(self.root) / "tokens.css").write_text(":root { --brand-ink: #000000; }\n", encoding="utf-8")
        got = brands.installed(self.root)
        self.assertEqual([(x["id"], x["name"], x["version"], x["own_folder"]) for x in got], [("local-brand", "local-brand", "", False)])

    def test_a_top_pack_with_a_non_text_id_is_local_brand(self):
        top_pack(self.root, brand_id=5)
        self.assertEqual([x["id"] for x in brands.installed(self.root)], ["local-brand"])


class DownloadsPick(Base):
    def test_a_zip_whose_manifest_is_not_json_does_not_count(self):
        zip_with(self.scratch / "a.zip", {"kit/clark-brand.json": "not json at all"})
        self.assertFalse(brands.has_manifest(self.scratch / "a.zip"))
        self.assertIsNone(brands.newest_brand_zip(self.scratch))

    def test_a_zip_whose_manifest_has_no_plain_id_does_not_count(self):
        for doc in ({"name": "x"}, {"id": "Bad_ID"}, {"id": 5}, [1], {"id": "assets"}):
            with self.subTest(doc):
                zip_with(self.scratch / "a.zip", {"kit/clark-brand.json": json.dumps(doc)})
                self.assertFalse(brands.has_manifest(self.scratch / "a.zip"))

    def test_a_manifest_in_the_wrong_place_does_not_count(self):
        zip_with(self.scratch / "a.zip", {"clark-brand.json": json.dumps({"id": "kit"}), "a/b/clark-brand.json": json.dumps({"id": "kit"})})
        self.assertFalse(brands.has_manifest(self.scratch / "a.zip"))

    def test_a_good_zip_counts(self):
        zip_with(self.scratch / "a.zip", {"kit/clark-brand.json": json.dumps({"id": "kit"})})
        self.assertTrue(brands.has_manifest(self.scratch / "a.zip"))

    def test_a_non_brand_zip_does_not_beat_an_older_brand_zip(self):
        old = zip_with(self.scratch / "old.zip", {"kit/clark-brand.json": json.dumps({"id": "kit"})})
        os.utime(old, (100, 100))
        new = zip_with(self.scratch / "new.zip", {"kit/clark-brand.json": "{nope"})
        os.utime(new, (900, 900))
        self.assertEqual(brands.newest_brand_zip(self.scratch), old)

    def test_the_newest_brand_zip_is_found_in_a_huge_folder(self):
        # 600 zips; the newest (a brand) lists last in directory order, so a cap on the listing would miss it
        for i in range(600):
            p = zip_with(self.scratch / f"a{i:04d}.zip", {"readme.txt": "not a brand"})
            os.utime(p, (1000 + i, 1000 + i))
        newest = zip_with(self.scratch / "zzz-brand.zip", {"kit/clark-brand.json": json.dumps({"id": "kit"})})
        os.utime(newest, (99999, 99999))
        real_scandir = os.scandir
        def name_order(path):
            with real_scandir(path) as it:
                entries = sorted(it, key=lambda e: e.name)
            return contextlib.nullcontext(iter(entries))
        opened = []
        real_has = brands.has_manifest
        def counting(path):
            opened.append(path)
            return real_has(path)
        with mock.patch.object(os, "scandir", name_order), mock.patch.object(brands, "has_manifest", counting):
            found = brands.newest_brand_zip(self.scratch)
        self.assertEqual(found, newest)
        self.assertLessEqual(len(opened), brands.LOOK_AT)

    def test_only_the_newest_few_zips_are_looked_into(self):
        # the cutoff that keeps a Settings listing cheap: LOOK_AT zips are opened at most; a brand zip older than all of them is not found
        old = zip_with(self.scratch / "old-brand.zip", {"kit/clark-brand.json": json.dumps({"id": "kit"})})
        os.utime(old, (100, 100))
        for i in range(brands.LOOK_AT):
            other = zip_with(self.scratch / ("other%d.zip" % i), {"readme.txt": "not a brand"})
            os.utime(other, (501 + i, 501 + i))
        self.assertIsNone(brands.newest_brand_zip(self.scratch))
        (self.scratch / "other0.zip").unlink()       # now only LOOK_AT-1 zips are newer than the brand zip
        newer = zip_with(self.scratch / "edge.zip", {"kit/clark-brand.json": json.dumps({"id": "kit"})})
        os.utime(newer, (500, 500))                   # the LOOK_AT-th newest, no two zips share a time: still looked into
        self.assertEqual(brands.newest_brand_zip(self.scratch), newer)

    def test_a_zip_over_the_size_cap_is_not_looked_into(self):
        zip_with(self.scratch / "a.zip", {"kit/clark-brand.json": json.dumps({"id": "kit"})})
        with mock.patch.object(brands, "ZIP_CAP", 10):
            self.assertFalse(brands.has_manifest(self.scratch / "a.zip"))

    def test_a_zip_with_too_many_entries_is_not_looked_into(self):
        members = {"kit/f%d.txt" % i: "x" for i in range(brands.FILE_CAP + 1)}
        members["kit/clark-brand.json"] = json.dumps({"id": "kit"})
        zip_with(self.scratch / "a.zip", members)
        self.assertFalse(brands.has_manifest(self.scratch / "a.zip"))

    def test_a_manifest_over_its_cap_does_not_count(self):
        zip_with(self.scratch / "a.zip", {"kit/clark-brand.json": json.dumps({"id": "kit", "pad": "x" * (brands.MANIFEST_CAP + 1)})})
        self.assertFalse(brands.has_manifest(self.scratch / "a.zip"))

    def test_a_link_to_a_brand_zip_is_not_followed(self):
        real = zip_with(self.scratch / "real.zip", {"kit/clark-brand.json": json.dumps({"id": "kit"})})
        downloads = self.scratch / "dl"
        downloads.mkdir()
        os.symlink(real, downloads / "link.zip")
        self.assertIsNone(brands.newest_brand_zip(downloads))


if __name__ == "__main__":
    unittest.main()
