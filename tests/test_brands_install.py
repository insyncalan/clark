"""#944 T2: the installed list, the folder lookup, install, replace, remove, undo, crash recovery and the brand lock
(src/clark/brands.py). RED until brands.py exists. Temp folders only, never a real system/branding. See tests/_brand_rig.py for
the calls these tests expect.

Run: python3 dev/run_tests.py test_brands_install
"""
import json
import os
import stat
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

import _brand_zips as bz
from _brand_rig import HIDDEN_NEW, HIDDEN_OLD, branding, make_dirs, snapshot, write_zip

try:
    from clark import brands
    IMPORT_ERROR = None
except ImportError as e:                    # RED: src/clark/brands.py does not exist yet
    brands = None
    IMPORT_ERROR = e


class Base(unittest.TestCase):
    def setUp(self):
        self.assertIsNone(IMPORT_ERROR, "src/clark/brands.py is missing: %s" % IMPORT_ERROR)
        self.root, self.data, self.scratch = make_dirs(self)
        self.now = [1000.0]
        brands.clock = lambda: self.now[0]
        self.addCleanup(lambda: setattr(brands, "clock", __import__("time").time))
        self.addCleanup(lambda: setattr(brands, "after_write", None))

    def tick(self, seconds=3600):
        self.now[0] += seconds

    def put(self, zdata, brand_id=bz.BRAND_ID, version="1.0.0"):
        """Review and install a zip; returns the review."""
        review = brands.review(write_zip(self.scratch, zdata, brand_id, version), self.root)
        brands.install(review["review_id"], self.root, self.data)
        self.tick()
        return review

    def brand_dir(self, brand_id=bz.BRAND_ID):
        return branding(self.root) / brand_id

    def backups(self):
        folder = self.data / "brand-backups"
        return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []

    def hidden(self):
        return sorted(p.name for p in branding(self.root).iterdir() if p.name.startswith(".clark-brand-"))

    def second_brand(self, version="1.0.1"):
        """The valid brand with a different logo, no cover, and a new picture: for a replace."""
        m = {bz.TOKENS: bz.TOKENS_CSS, bz.LOGO: bz._png((1, 2, 3)), "assets/cover-new.png": bz.COVER_PNG}
        return bz.build(m, manifest=bz.manifest_for(m, version=version))


class Installed(Base):
    def test_lists_valid_only(self):
        self.put(bz.valid())
        b = branding(self.root)
        (b / "broken").mkdir()
        (b / "broken" / "clark-brand.json").write_text("{not json", encoding="utf-8")
        (b / "no-manifest").mkdir()
        (b / "no-manifest" / "tokens.css").write_text(":root{}", encoding="utf-8")
        (b / (HIDDEN_NEW + "x")).mkdir()
        (b / (HIDDEN_OLD + "y")).mkdir()
        (b / "assets").mkdir()
        (b / "design-system").mkdir()
        (b / "stray-file").write_text("x", encoding="utf-8")
        got = brands.installed(self.root)
        self.assertEqual([x["id"] for x in got], [bz.BRAND_ID])
        self.assertEqual(set(got[0]), {"id", "name", "version"})
        self.assertEqual((got[0]["name"], got[0]["version"]), ("Example Brand", "1.0.0"))

    def test_a_folder_whose_manifest_id_is_another_is_not_listed(self):
        self.put(bz.valid())
        os.rename(self.brand_dir(), branding(self.root) / "renamed")
        self.assertEqual(brands.installed(self.root), [])

    def test_local_brand_is_listed_only_with_a_top_level_tokens_css(self):
        self.assertEqual(brands.installed(self.root), [])
        (branding(self.root) / "tokens.css").write_text(":root { --brand-ink: #000000; }\n", encoding="utf-8")
        self.assertEqual([x["id"] for x in brands.installed(self.root)], ["local-brand"])

    def _top_pack(self, name="Fabrikam", brand_id="fabrikam"):
        import json
        top = branding(self.root)
        (top / "tokens.css").write_text(":root { --brand-ink: #000000; }\n", encoding="utf-8")
        (top / "clark-brand.json").write_text(json.dumps({"id": brand_id, "name": name, "version": "2.1.0", "files": []}), encoding="utf-8")

    def test_a_pack_unzipped_straight_into_the_branding_folder_shows_under_its_own_name(self):
        self._top_pack()
        got = brands.installed(self.root)
        self.assertEqual([(x["name"], x["version"]) for x in got], [("Fabrikam", "2.1.0")])
        self.assertNotEqual(got[0]["name"], "local-brand")

    def test_that_pack_applies_to_projects_through_its_listed_id(self):
        self._top_pack()
        listed = brands.installed(self.root)[0]["id"]
        self.assertEqual(brands.folder(self.root, listed), branding(self.root))

    def test_a_top_pack_with_a_broken_manifest_is_still_local_brand(self):
        self._top_pack()
        (branding(self.root) / "clark-brand.json").write_text("{nope", encoding="utf-8")
        self.assertEqual([(x["id"], x["name"]) for x in brands.installed(self.root)], [("local-brand", "local-brand")])

    def test_a_missing_library_folder_is_an_empty_list(self):
        os.rmdir(branding(self.root))
        self.assertEqual(brands.installed(self.root), [])

    def test_not_a_list_of_every_folder(self):
        self.put(bz.valid())
        for n in ("a", "b", "c"):
            (branding(self.root) / n).mkdir()
        self.assertEqual(len(brands.installed(self.root)), 1)


class Folder(Base):
    def test_generic_is_a_sentinel_never_none(self):
        self.put(bz.valid())
        self.assertIsNotNone(brands.GENERIC)
        for brand_id in ("generic", "no-such-brand"):
            self.assertIs(brands.folder(self.root, brand_id), brands.GENERIC, brand_id)

    def test_a_removed_brand_falls_back_to_generic(self):
        self.put(bz.valid())
        self.assertEqual(brands.folder(self.root, bz.BRAND_ID), self.brand_dir())
        brands.remove(bz.BRAND_ID, self.root, self.data)
        self.assertIs(brands.folder(self.root, bz.BRAND_ID), brands.GENERIC)

    def test_local_brand_is_the_top_folder_when_it_has_tokens(self):
        self.assertIs(brands.folder(self.root, "local-brand"), brands.GENERIC)
        (branding(self.root) / "tokens.css").write_text(":root{}", encoding="utf-8")
        self.assertEqual(brands.folder(self.root, "local-brand"), branding(self.root))

    def test_ids_with_path_parts_are_generic_and_never_touch_the_disk(self):
        self.put(bz.valid())
        touched = []

        def spy(real):
            def wrapper(path, *a, **k):
                touched.append(str(path))
                return real(path, *a, **k)
            return wrapper
        with ExitStack() as stack:
            for name in ("stat", "lstat", "scandir", "listdir"):
                stack.enter_context(mock.patch.object(os, name, spy(getattr(os, name))))
            for bad in ("..", "../x", "a/b", "x\\y", "", "../" + bz.BRAND_ID, "/etc", ".", bz.BRAND_ID + "/../..", None, 7):
                with self.subTest(repr(bad)):
                    self.assertIs(brands.folder(self.root, bad), brands.GENERIC)
        self.assertFalse([t for t in touched if ".." in Path(t).parts], touched)

    def test_the_id_is_looked_up_in_the_installed_list_not_joined(self):
        self.put(bz.valid())
        (branding(self.root) / "plain-folder").mkdir()          # a folder on disk that is not an installed brand
        self.assertIs(brands.folder(self.root, "plain-folder"), brands.GENERIC)


class Install(Base):
    def test_install_new(self):
        review = self.put(bz.valid())
        self.assertEqual(snapshot(self.brand_dir()).get("tokens.css"), bz.TOKENS_CSS)
        self.assertEqual(snapshot(self.brand_dir()).get("assets/cover.png"), bz.COVER_PNG)
        self.assertEqual([b["id"] for b in brands.installed(self.root)], [review["id"]])
        self.assertEqual(self.hidden(), [])

    def test_files_are_written_with_our_own_modes_and_no_links(self):
        self.put(bz.valid())
        for dirpath, dirs, files in os.walk(self.brand_dir()):
            for n in files:
                p = Path(dirpath) / n
                self.assertFalse(p.is_symlink())
                self.assertEqual(stat.S_IMODE(p.stat().st_mode) & 0o022, 0, "not writable by others: %s" % p)

    def test_replace_shows_removed(self):
        self.put(bz.valid())
        review = brands.review(write_zip(self.scratch, self.second_brand(), version="1.0.1"), self.root)
        self.assertEqual(set(review["removed"]), {bz.COVER})
        self.assertEqual(set(review["replaced"]) - {bz.MANIFEST}, {bz.TOKENS, bz.LOGO})
        self.assertEqual(set(review["added"]), {"assets/cover-new.png"})
        self.assertEqual(snapshot(self.brand_dir())["assets/cover.png"], bz.COVER_PNG, "reviewing changed nothing")
        brands.install(review["review_id"], self.root, self.data)
        files = snapshot(self.brand_dir())
        self.assertNotIn("assets/cover.png", files)
        self.assertIn("assets/cover-new.png", files)
        self.assertEqual(self.hidden(), [])

    def test_backup_is_outside_system_and_holds_the_old_files(self):
        self.put(bz.valid())
        self.put(self.second_brand(), version="1.0.1")
        names = self.backups()
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].endswith("-" + bz.BRAND_ID), names)
        held = snapshot(self.data / "brand-backups" / names[0])
        self.assertIn(bz.COVER_PNG, held.values())
        self.assertFalse(str(self.data).startswith(str(self.root / "system")))

    def test_the_last_five_backups_are_kept(self):
        self.put(bz.valid())
        for i in range(1, 8):
            self.put(self.second_brand(version="1.0.%d" % i), version="1.0.%d" % i)
        self.assertEqual(len(self.backups()), 5)

    def test_hash_recheck_after_write_aborts_and_keeps_the_old_folder(self):
        self.put(bz.valid())
        old = snapshot(self.brand_dir())
        review = brands.review(write_zip(self.scratch, self.second_brand(), version="1.0.1"), self.root)

        def tamper(staged):
            Path(staged, "tokens.css").write_bytes(b":root { --brand-ink: #ff0000; }\n")
        brands.after_write = tamper
        with self.assertRaises(brands.BrandError):
            brands.install(review["review_id"], self.root, self.data)
        self.assertEqual(snapshot(self.brand_dir()), old)
        self.assertEqual(self.hidden(), [], "the staged folder is removed")

    def test_the_staged_folder_is_private_and_a_leftover_one_is_cleared(self):
        leftover = branding(self.root) / (HIDDEN_NEW + bz.BRAND_ID)
        leftover.mkdir()
        (leftover / "tokens.css").write_text("left over", encoding="utf-8")
        seen = {}
        brands.after_write = lambda staged: seen.update(mode=stat.S_IMODE(os.stat(staged).st_mode), names=sorted(os.listdir(staged)))
        self.put(bz.valid())
        self.assertEqual(seen["mode"], 0o700)
        self.assertNotIn("left over", repr(snapshot(self.brand_dir())))
        self.assertEqual(snapshot(self.brand_dir())["tokens.css"], bz.TOKENS_CSS)

    def test_files_are_opened_exclusive(self):
        flags = []
        real = os.open

        def spy(path, fl, *a, **k):
            if HIDDEN_NEW in str(path):
                flags.append(fl)
            return real(path, fl, *a, **k)
        with mock.patch.object(os, "open", spy):
            self.put(bz.valid())
        written = [f for f in flags if f & (os.O_WRONLY | os.O_RDWR)]
        self.assertTrue(written)
        self.assertTrue(all(f & os.O_EXCL for f in written))

    def test_a_link_in_the_staged_tree_stops_the_install(self):
        self.put(bz.valid())
        old = snapshot(self.brand_dir())
        review = brands.review(write_zip(self.scratch, self.second_brand(), version="1.0.1"), self.root)

        def plant(staged):
            os.symlink("/etc/passwd", os.path.join(staged, "assets", "evil.png"))
        brands.after_write = plant
        with self.assertRaises(brands.BrandError):
            brands.install(review["review_id"], self.root, self.data)
        self.assertEqual(snapshot(self.brand_dir()), old)
        self.assertEqual(self.hidden(), [])

    def test_a_second_install_of_the_same_review_is_refused(self):
        review = self.put(bz.valid())
        with self.assertRaises(brands.BrandError) as cm:
            brands.install(review["review_id"], self.root, self.data)
        self.assertEqual(cm.exception.key, "expired")


class RemoveAndUndo(Base):
    def test_remove(self):
        self.put(bz.valid())
        old = snapshot(self.brand_dir())
        brands.remove(bz.BRAND_ID, self.root, self.data)
        self.assertFalse(self.brand_dir().exists())
        self.assertEqual(brands.installed(self.root), [])
        self.assertEqual(self.hidden(), [])
        held = snapshot(self.data / "brand-backups" / self.backups()[-1])
        self.assertEqual(sorted(held.values(), key=repr), sorted(old.values(), key=repr))

    def test_remove_refuses_what_is_not_installed(self):
        for bad in ("generic", "local-brand", "nope", "..", "a/b"):
            with self.subTest(bad):
                with self.assertRaises(brands.BrandError):
                    brands.remove(bad, self.root, self.data)

    def test_undo_a_remove_puts_back_the_same_bytes(self):
        self.put(bz.valid())
        old = snapshot(self.brand_dir())
        brands.remove(bz.BRAND_ID, self.root, self.data)
        brands.undo(self.root, self.data)
        self.assertEqual(snapshot(self.brand_dir()), old)
        self.assertEqual(self.hidden(), [])

    def test_undo_a_replace_puts_back_the_old_files(self):
        self.put(bz.valid())
        old = snapshot(self.brand_dir())
        self.put(self.second_brand(), version="1.0.1")
        brands.undo(self.root, self.data)
        self.assertEqual(snapshot(self.brand_dir()), old)

    def test_undo_a_first_install_removes_it(self):
        self.put(bz.valid())
        brands.undo(self.root, self.data)
        self.assertFalse(self.brand_dir().exists())

    def test_undo_is_one_level(self):
        self.put(bz.valid())
        brands.remove(bz.BRAND_ID, self.root, self.data)
        brands.undo(self.root, self.data)
        with self.assertRaises(brands.BrandError):
            brands.undo(self.root, self.data)

    def test_undo_with_nothing_to_undo(self):
        with self.assertRaises(brands.BrandError):
            brands.undo(self.root, self.data)


class Crash(Base):
    def test_a_crash_between_the_renames_is_rolled_back(self):
        self.put(bz.valid())
        old = snapshot(self.brand_dir())
        review = brands.review(write_zip(self.scratch, self.second_brand(), version="1.0.1"), self.root)
        real, calls = os.rename, []

        def flaky(src, dst, *a, **k):
            calls.append((src, dst))
            if len(calls) in (2, 3):         # #944: the power goes for good: the second rename fails and so does the old folder's way back
                raise OSError("the power went")
            return real(src, dst, *a, **k)
        with mock.patch.object(brands.os, "rename", flaky):
            with self.assertRaises(Exception):
                brands.install(review["review_id"], self.root, self.data)
        self.assertEqual(len(calls), 3, "the second rename failed and the old folder's way back was tried")
        self.assertFalse(self.brand_dir().exists(), "the crash left the brand missing")
        self.assertTrue(any(h.startswith(HIDDEN_OLD) for h in self.hidden()))
        self.assertEqual([b["id"] for b in brands.installed(self.root)], [], "hidden folders are never listed")
        brands.recover(self.root)
        self.assertEqual(snapshot(self.brand_dir()), old)
        self.assertEqual(self.hidden(), [])

    def test_a_failed_second_rename_puts_the_old_folder_back_at_once(self):       # #944 (957's follow-up): no wait for the next brand action
        self.put(bz.valid())
        old = snapshot(self.brand_dir())
        before = (self.data / brands.JOURNAL).read_bytes()
        review = brands.review(write_zip(self.scratch, self.second_brand(), version="1.0.1"), self.root)
        real, calls = os.rename, []

        def flaky(src, dst, *a, **k):
            calls.append((src, dst))
            if len(calls) == 2:
                raise OSError("the disk said no")
            return real(src, dst, *a, **k)
        with mock.patch.object(brands.os, "rename", flaky):
            with self.assertRaises(brands.BrandError):
                brands.install(review["review_id"], self.root, self.data)
        self.assertEqual(snapshot(self.brand_dir()), old, "the old brand is in place again, with no recover() run")
        self.assertEqual(self.hidden(), [], "and nothing hidden is left")
        self.assertEqual((self.data / brands.JOURNAL).read_bytes(), before, "the undo journal still says what it said: nothing was changed")

    def test_the_journal_is_written_before_the_swap(self):       # #944: a failed journal write leaves the install not done, not done and reported failed
        self.put(bz.valid())
        old = snapshot(self.brand_dir())
        review = brands.review(write_zip(self.scratch, self.second_brand(), version="1.0.1"), self.root)
        with mock.patch.object(brands, "_journal", side_effect=OSError("no room")):
            with self.assertRaises(brands.BrandError):
                brands.install(review["review_id"], self.root, self.data)
        self.assertEqual(snapshot(self.brand_dir()), old, "the journal could not be written, so nothing was swapped")
        self.assertEqual(self.hidden(), [])

    def test_the_journal_names_the_change_when_the_swap_has_gone_through(self):
        self.put(bz.valid())
        order = []
        real_swap, real_journal = brands._swap, brands._journal
        with mock.patch.object(brands, "_swap", lambda *a: (order.append("swap"), real_swap(*a))[1]), \
                mock.patch.object(brands, "_journal", lambda *a: (order.append("journal"), real_journal(*a))[1]):
            review = brands.review(write_zip(self.scratch, self.second_brand(), version="1.0.1"), self.root)
            brands.install(review["review_id"], self.root, self.data)
        self.assertEqual(order, ["journal", "swap"])
        self.assertEqual(json.loads((self.data / brands.JOURNAL).read_text(encoding="utf-8"))["kind"], "replace")

    def test_a_crash_between_the_renames_is_also_put_right_by_the_next_brand_action(self):
        self.put(bz.valid())
        old = snapshot(self.brand_dir())
        review = brands.review(write_zip(self.scratch, self.second_brand(), version="1.0.1"), self.root)
        real, calls = os.rename, []

        def flaky(src, dst, *a, **k):
            calls.append((src, dst))
            if len(calls) in (2, 3):         # #944: the power goes for good: the second rename fails and so does the old folder's way back
                raise OSError("the power went")
            return real(src, dst, *a, **k)
        with mock.patch.object(brands.os, "rename", flaky):
            with self.assertRaises(Exception):
                brands.install(review["review_id"], self.root, self.data)
        self.assertFalse(self.brand_dir().exists())
        brands.review(write_zip(self.scratch, bz.valid(), version="1.0.0"), self.root)       # any action: it recovers first
        self.assertEqual(snapshot(self.brand_dir()), old)
        self.assertEqual(self.hidden(), [])

    def test_the_tokens_sentence_ends_as_ruled(self):
        self.assertTrue(brands.MESSAGES["tokens"].endswith("not refer to anything outside itself. Nothing was installed."))

    def test_the_deny_list_is_the_repos_own_listed_word_guard_and_holds_no_word_here(self):
        import importlib.util
        path = Path(__file__).resolve().parents[1] / "dev" / "tools" / "publish_public.py"
        spec = importlib.util.spec_from_file_location("_pp_for_test", str(path))
        pp = importlib.util.module_from_spec(spec)
        import sys
        sys.modules[spec.name] = pp
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(pp)
        word = pp.PEOPLE_ANY_CASE[0]                     # revealed at run time: this file holds no listed word
        brands.LISTED_WORD_CHECK = None
        self.addCleanup(lambda: setattr(brands, "LISTED_WORD_CHECK", None))
        self.assertTrue(brands._has_word("a line\nby " + word + " here"))
        self.assertFalse(brands._has_word("a plain line of colours"))
        brands.LISTED_WORD_CHECK = lambda line: "seamword" in line         # the named seam is what _has_word asks
        self.assertTrue(brands._has_word("x\nseamword"))
        self.assertFalse(brands._has_word("by " + word))

    def test_the_undo_journal_is_never_a_published_file_nor_a_backup_of_the_users_data(self):
        self.put(bz.valid())
        self.assertTrue((self.data / brands.JOURNAL).is_file(), "an install writes the journal")
        self.assertEqual(brands.JOURNAL, "brand-last.json")
        self.assertNotIn(brands.JOURNAL, self.backups(), "not inside brand-backups/")
        self.assertFalse((self.data / "brand-backups" / brands.JOURNAL).exists())
        from clark import backup, publish
        self.assertNotIn(brands.JOURNAL, str(publish.PUBLISH_FIELDS))
        self.assertEqual(backup.entries(self.data), [], "the data backups list never holds it")
        self.assertEqual(backup.entries(self.data / "brand-backups"), [])
        # nothing published, exported or backed up names it: the source of those paths never mentions the journal
        src = Path(__file__).resolve().parents[1] / "src" / "clark"
        for name in ("publish.py", "publish_flow.py", "word_route.py", "excel_route.py", "excel_client.py", "backup.py", "export.py"):
            if (src / name).is_file():
                self.assertNotIn("brand-last", (src / name).read_text(encoding="utf-8"), name)

    def test_leftovers_are_removed_when_the_brand_is_there(self):
        self.put(bz.valid())
        old = snapshot(self.brand_dir())
        for n in (HIDDEN_NEW + bz.BRAND_ID, HIDDEN_OLD + bz.BRAND_ID):
            (branding(self.root) / n).mkdir()
            (branding(self.root) / n / "tokens.css").write_text("x", encoding="utf-8")
        brands.recover(self.root)
        self.assertEqual(self.hidden(), [])
        self.assertEqual(snapshot(self.brand_dir()), old)

    def test_the_next_brand_action_does_the_recovery(self):
        self.put(bz.valid())
        os.rename(self.brand_dir(), branding(self.root) / (HIDDEN_OLD + bz.BRAND_ID))
        (branding(self.root) / (HIDDEN_NEW + bz.BRAND_ID)).mkdir()
        brands.review(write_zip(self.scratch, bz.valid_webp(), bz.BRAND_ID, "1.0.2"), self.root)
        self.assertEqual(self.hidden(), [], "a review is a brand action: it puts things right first")
        self.assertTrue(self.brand_dir().is_dir())


class JournalAfterSwap(Base):
    """The undo journal describes a swap that happened: a swap that fails puts the journal back as it was (the last change's undo stays true)."""

    def flaky_rename(self, fail_on):
        real, calls = os.rename, []

        def flaky(src, dst, *a, **k):
            calls.append((src, dst))
            if len(calls) == fail_on:
                raise OSError("no room")
            return real(src, dst, *a, **k)
        return flaky

    def test_a_failed_replace_leaves_the_journal_as_it_was(self):
        self.put(bz.valid())
        self.assertTrue(brands.can_undo(self.root, self.data))
        before = (self.data / brands.JOURNAL).read_bytes()
        review = brands.review(write_zip(self.scratch, self.second_brand(), version="1.0.1"), self.root)
        with mock.patch.object(brands.os, "rename", self.flaky_rename(2)):
            with self.assertRaises(Exception):
                brands.install(review["review_id"], self.root, self.data)
        self.assertEqual((self.data / brands.JOURNAL).read_bytes(), before, "a swap that did not happen leaves the journal as it was")
        self.assertTrue(brands.can_undo(self.root, self.data))

    def test_a_failed_remove_leaves_the_journal_as_it_was(self):
        self.put(bz.valid())
        before = (self.data / brands.JOURNAL).read_bytes()
        with mock.patch.object(brands.os, "rename", self.flaky_rename(1)):
            with self.assertRaises(Exception):
                brands.remove(bz.BRAND_ID, self.root, self.data)
        self.assertEqual((self.data / brands.JOURNAL).read_bytes(), before)
        self.assertTrue(brands.can_undo(self.root, self.data))

    def test_success_still_journals_and_undo_works(self):
        self.put(bz.valid())
        old = snapshot(self.brand_dir())
        self.put(self.second_brand(), version="1.0.1")
        self.assertTrue((self.data / brands.JOURNAL).is_file())
        self.assertTrue(brands.can_undo(self.root, self.data))
        brands.undo(self.root, self.data)
        self.assertEqual(snapshot(self.brand_dir()), old)


class Lock(Base):
    def test_install_remove_and_undo_are_refused_while_that_brand_is_in_use(self):
        self.put(bz.valid())
        review = brands.review(write_zip(self.scratch, self.second_brand(), version="1.0.1"), self.root)
        old = snapshot(self.brand_dir())
        with brands.in_use(bz.BRAND_ID):
            for label, call in (("install", lambda: brands.install(review["review_id"], self.root, self.data)),
                                ("remove", lambda: brands.remove(bz.BRAND_ID, self.root, self.data)),
                                ("undo", lambda: brands.undo(self.root, self.data))):
                with self.subTest(label):
                    with self.assertRaises(brands.BrandError) as cm:
                        call()
                    self.assertEqual(cm.exception.key, "busy")
        self.assertEqual(snapshot(self.brand_dir()), old)
        brands.install(review["review_id"], self.root, self.data)         # the hold is gone: it goes through

    def test_a_different_brand_is_not_refused(self):
        self.put(bz.valid())
        with brands.in_use("some-other-brand"):
            brands.remove(bz.BRAND_ID, self.root, self.data)
        self.assertFalse(self.brand_dir().exists())

    def test_the_hold_is_released_when_the_work_raises(self):
        self.put(bz.valid())
        with self.assertRaises(RuntimeError):
            with brands.in_use(bz.BRAND_ID):
                raise RuntimeError("publish failed")
        brands.remove(bz.BRAND_ID, self.root, self.data)


if __name__ == "__main__":
    unittest.main()
