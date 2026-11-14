"""Item 634: the copy folder (item 622) when clark runs in Docker, and a copy cut off by a kill.

Run: python3 dev/run_tests.py test_backup_copy_out
No Docker is started. The compose file is read as text.

What is asserted, and what each safety test guards:
- docker/compose.copy.yaml shares the folder named in CLARK_COPY_DIR into the container as /backups-out, refuses to start without it, and
  adds nothing else; compose.yaml itself is unchanged by it (no copy folder unless asked for);
- /backups-out is accepted as the copy folder (an absolute path that is not the data or backups folder), and a backup is copied there;
- a process killed after the copy file was written and before it was renamed leaves only a working file: no backup name, so a list,
  retention and a restore do not see it, and the next backup copies as usual.
"""
import contextlib
import io
import os
import re
import signal
import subprocess
import sys
import unittest
from pathlib import Path

import _paths  # noqa: F401
from clark import __main__ as launcher, backup, settings
from test_backup_copy import Rig

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


class TheComposeFile(unittest.TestCase):
    text = (ROOT / "docker" / "compose.copy.yaml").read_text(encoding="utf-8")
    lines = [x for x in text.splitlines() if x.strip() and not x.lstrip().startswith("#")]

    def test_it_shares_the_named_folder_as_backups_out_and_needs_it_named(self):
        self.assertEqual(self.lines[-1].strip(), "target: /backups-out")
        self.assertRegex(self.text, r"source: \$\{CLARK_COPY_DIR:\?[^}]+\}")

    def test_it_changes_nothing_but_that_one_share(self):
        self.assertEqual([x.strip() for x in self.lines],
                         ["services:", "clark:", "volumes:", "- type: bind",
                          re.search(r"source: .*", self.text).group(0), "target: /backups-out"])

    def test_the_main_file_has_no_copy_folder(self):
        main = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
        self.assertNotIn("backups-out", main)
        self.assertNotIn("CLARK_COPY_DIR", main)


KILL = """
import os, signal, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from clark import backup
def stop(fd):
    os.kill(os.getpid(), signal.SIGKILL)
os.fsync = stop                       # the bytes are written; the process dies before the rename
backup._copy_into(Path(sys.argv[2]), Path(sys.argv[3]), 14, True)
"""


class AKillMidCopy(Rig):
    def test_backups_out_is_accepted_as_a_copy_folder_when_it_is_there(self):
        out = self.tmp / "backups-out"
        out.mkdir()
        self.assertTrue(self.on(out))
        made = backup.take(self.s, "undo")
        self.assertEqual(self.names(out), [made.name])

    def test_a_kill_after_the_write_leaves_only_a_working_file_that_nothing_reads(self):
        made = self.on() and backup.take(self.s, "undo")
        settings.set_backup_copy_folder(self.data, "")
        for p in self.copy.iterdir():
            p.unlink()
        run = subprocess.run([sys.executable, "-c", KILL, str(SRC), str(self.copy), str(made)], capture_output=True, timeout=60)
        self.assertEqual(run.returncode, -signal.SIGKILL, run.stderr)
        left = self.names(self.copy)
        self.assertEqual(len(left), 1)
        self.assertTrue(left[0].startswith(".") and left[0].endswith(".part"), left)
        self.assertEqual(backup.listing(self.copy), [])
        self.assertEqual(backup.entries(self.copy), [])
        backup.prune(self.copy, 1, True, lock=contextlib.nullcontext())
        self.assertEqual(self.names(self.copy), left, "retention left the working file alone")
        out, err = io.StringIO(), io.StringIO()
        code = launcher.restore_main(["--data", str(self.tmp / "new"), "--from", str(self.copy), left[0]], out, err, onedrive_roots=[])
        self.assertNotEqual(code, 0)
        self.assertFalse((self.tmp / "new" / "clark.db").exists())

    def test_the_next_backup_after_a_kill_is_copied_as_usual(self):
        self.on()
        stale = self.copy / ".clark-20200101T000000Z-undo.99.deadbeef.part"
        stale.write_bytes(b"cut off")
        made = backup.take(self.s, "undo")
        self.assertIn(made.name, self.names(self.copy))
        self.assertTrue(stale.exists())


if __name__ == "__main__":
    unittest.main()
