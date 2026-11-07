"""A release that declares a NEWER data layout than the installed app: migrates with the safety copy; Undo restores the old file byte for byte."""
import hashlib
import unittest
from pathlib import Path

from clark import store as store_module, update_helper as h, update_install as ui
from clark.store import open_store
from test_store_migration import version
from test_update_migration import Migrated, rows
from test_updates import make_zip


class NewerLayoutRelease(Migrated):
    def test_a_release_with_a_newer_layout_migrates_with_the_copy_and_undo_puts_the_old_file_back_byte_for_byte(self):
        old_bytes = Path(self.db).read_bytes()
        newer = store_module.SCHEMA_VERSION            # the installed app's layout is 2: this release's is newer
        self.download.unlink()
        make_zip(self.downloads, version="0.3.1", files=self.new_files, schema=newer)
        self.installed()                                # read_release allows the newer layout; the helper installs it
        now, copy = self.new_start()                    # real open_store: safety copy, then migration
        self.assertEqual(str(newer), version(self.db))
        copy_bytes = Path(copy).read_bytes()
        self.assertEqual("1", version(copy))                        # the safety copy is the old layout
        record = ui.last_update(self.data)[1]
        self.assertEqual({"backup": Path(copy).name, "from": 1, "to": newer}, record["migration"])
        armed = now.arm_undo({})[1]
        self.assertEqual("full", armed["choice"])
        status, done = now.undo({"arm_id": armed["arm_id"]})
        self.assertEqual((200, True), (status, done["restart"]))
        self.assertEqual("1", version(self.db))
        self.assertEqual(hashlib.sha256(copy_bytes).hexdigest(), hashlib.sha256(Path(self.db).read_bytes()).hexdigest())
        self.assertEqual(self.before, {t: rows(self.db, t) for t in ("projects", "documents")})
        self.assertEqual(h.OK, self.run_helper()[0])

if __name__ == "__main__":
    unittest.main()
