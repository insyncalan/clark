"""Item 633: the Windows route of the Docker update guide (docker/UPDATE-windows.txt) and the compose file it names.

Run: python3 dev/run_tests.py test_update_docker_windows
Reads files only. No server, no Docker. What needs a real Windows laptop is on dev/handchecks/1.1.0-sheet.md (lines 633.1 to 633.6).
"""
import re
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import release_files

ROOT = Path(__file__).resolve().parent.parent
GUIDE = (ROOT / "docker" / "UPDATE-windows.txt").read_text(encoding="utf-8")
MAC_GUIDE = (ROOT / "docker" / "UPDATE.txt").read_text(encoding="utf-8")
WIN_COMPOSE = (ROOT / "docker" / "compose.windows.yaml").read_text(encoding="utf-8")
SHEET = (ROOT / "dev" / "handchecks" / "1.1.0-sheet.md").read_text(encoding="utf-8")
BOTH = "docker compose -f docker/compose.yaml -f docker/compose.windows.yaml"
# Step 2 of the guide, ruled by the head 16-11 (WO-M3669, NEW-WORDS.md): the old folder is renamed, so the new one (always called clark) is not unzipped over it.
RULED_STEP = ("  2. Rename the old clark folder to clark-old. Then unzip the new download into the\n"
              "     folder that held it (the folder that now holds clark-old and clark-data).\n"
              "     If you use Extract All, change the folder it shows to that folder first.\n"
              "     The new folder is called clark and finds the folder clark-data again.\n"
              "     (The old folder stays as clark-old, if you want to go back.)\n")


def commands(text):
    return [l.strip() for l in text.splitlines() if l.strip().startswith("docker compose")]


class WindowsUpdateGuide(unittest.TestCase):
    def test_every_command_names_both_compose_files(self):
        found = commands(GUIDE)
        self.assertGreaterEqual(len(found), 4, found)
        for c in found:
            self.assertTrue(c.startswith(BOTH + " "), c)

    def test_down_up_logs_and_restore_are_all_there(self):
        found = commands(GUIDE)
        for verb in ("down", "up -d", "logs --tail 50", "run --rm clark python3 -m clark restore --data /data"):
            self.assertTrue(any(c == BOTH + " " + verb for c in found), verb)

    def test_the_compose_files_named_exist(self):
        for name in ("compose.yaml", "compose.windows.yaml"):
            self.assertTrue((ROOT / "docker" / name).is_file())

    def test_the_old_folder_is_renamed_first_and_the_step_does_not_contradict_itself(self):
        self.assertIn(RULED_STEP, GUIDE)
        self.assertNotIn("UNRULED", GUIDE)
        self.assertNotIn("Do not unzip it over the old one", GUIDE)
        self.assertNotIn("beside the old clark folder", GUIDE)

    def test_the_windows_data_source_is_a_sibling_of_the_clark_folder(self):
        self.assertIn("${CLARK_DATA_DIR:-../../clark-data}", WIN_COMPOSE)
        # docker/ is two levels below the folder that holds the clark folder, so a sibling clark folder reads the same path
        self.assertEqual(Path("/w/clark-1/docker").joinpath("../../clark-data").resolve(),
                         Path("/w/clark-2/docker").joinpath("../../clark-data").resolve())

    def test_the_hand_check_sheet_names_the_ruled_step_2_not_unzip_beside(self):
        row = [l for l in SHEET.splitlines() if l.startswith("| 633.1 ")][0]
        for words in ("rename the old clark folder to clark-old", "unzip the new download into the folder that held it", "Extract All, change the folder it shows to that folder first"):
            self.assertIn(words, row)
        self.assertNotIn("beside", row)

    def test_the_zip_always_unzips_to_clark_so_the_renamed_old_folder_leaves_the_name_free(self):
        """The zip's one top folder is clark (release_files.TOP), so after the old folder is renamed the new one finds the same clark-data."""
        from clark import release_files
        self.assertEqual(release_files.TOP, "clark")
        old = Path("/w/clark-old/docker").joinpath("../../clark-data").resolve()
        new = Path("/w") .joinpath(release_files.TOP, "docker", "../../clark-data").resolve()
        self.assertEqual(old, new)
        self.assertEqual(new, Path("/w/clark-data"))

    def test_the_hash_line_names_the_windows_zip_and_no_mac_name(self):
        self.assertIn("Get-FileHash -Algorithm SHA256 clark-<version>-windows.zip", GUIDE)
        self.assertNotIn("-mac", GUIDE)
        self.assertNotIn("shasum", GUIDE)
        self.assertNotIn("Terminal", GUIDE)

    def test_house_wording(self):
        self.assertNotIn("!", GUIDE)
        self.assertNotIn("\t", GUIDE)
        self.assertEqual(GUIDE.count("docker load"), 1)      # only the ruled changed-runtime-image sentence
        self.assertNotIn("#", GUIDE)
        self.assertNotRegex(GUIDE, r"(?m)(^|[.?]\s+)Clark\b")
        self.assertNotIn("usual", GUIDE)

    def test_it_keeps_the_ruled_sentences_of_the_mac_guide(self):
        for words in ("Your data is not in the clark folder. It stays where it is.",
                      "Its name ends in -migrate.db",
                      "never fewer than 3",
                      "start from the newer clark folder.\nNothing was changed.",
                      "Under Docker, Install from a file in Settings does not apply: update by starting from the newer clark folder."):
            self.assertIn(" ".join(words.split()), " ".join(MAC_GUIDE.split()))
            self.assertIn(" ".join(words.split()), " ".join(GUIDE.split()))

    def test_it_ships_in_the_docker_folder_of_the_windows_zip(self):
        self.assertTrue(release_files.covers("windows", "docker/UPDATE-windows.txt"))
        self.assertTrue(release_files.at_top("docker/UPDATE-windows.txt"))

    def test_the_sheet_has_the_six_update_lines_and_row_633_points_at_them(self):
        ids = re.findall(r"^\| (633\.\d+) \|", SHEET, re.M)
        self.assertEqual(ids, ["633.%d" % n for n in range(1, 7)])
        row = [l for l in SHEET.splitlines() if l.startswith("| 633 |")][0]
        self.assertIn("633.1 to 633.6", row)
        self.assertNotIn("no hand check", row)
        self.assertIn("Get-FileHash", SHEET)


    def test_the_guide_names_each_step_for_powershell_and_command_prompt(self):
        steps = re.findall(r"(?m)^  (\d)\. ", GUIDE.split("To go back")[0])
        self.assertEqual(steps, ["1", "2", "3", "4", "5"])
        self.assertIn("1. Open PowerShell or Command Prompt in the clark folder", GUIDE)
        self.assertIn(BOTH + " down", GUIDE.split("2. Rename")[0])          # step 1 stops the old clark
        self.assertIn("2. Rename the old clark folder to clark-old. Then unzip the new download into the", GUIDE)      # ruled 16-11 and amended 01:52, replaces the Mac guide's step 2
        self.assertIn("3. In the same window, go to the new clark folder", GUIDE)
        self.assertIn("cd /d", GUIDE)
        self.assertIn(BOTH + " up -d", GUIDE.split("4. Type this")[1].split("5. Open")[0])   # step 4 starts the new clark
        self.assertIn("5. Open http://127.0.0.1:8766 in Chrome.", GUIDE)

    def test_going_back_renames_the_folders_before_the_up_command(self):
        back = " ".join(GUIDE.split("To go back to the old clark")[1].split())
        self.assertIn("To go back: rename clark to clark-new, rename clark-old back to clark, then type the up command in that folder.", back)
        self.assertNotIn("in the old folder", back)

    def test_a_changed_runtime_image_is_loaded_again_before_the_up_command(self):
        text = " ".join(GUIDE.split())
        sentence = "If a new zip carries a changed runtime image, run docker load -i docker\\clark-runtime.tar again before the up command."
        self.assertIn(sentence, text)
        self.assertLess(text.index(sentence), text.index(BOTH + " up -d"))

    def test_the_hash_has_a_command_prompt_form_as_well(self):
        self.assertIn("certutil -hashfile clark-<version>-windows.zip SHA256", GUIDE)
        self.assertLess(GUIDE.index("Get-FileHash"), GUIDE.index("certutil"))

    def test_start_here_for_windows_points_at_the_guide_and_the_data_stays(self):
        import package
        text = " ".join(package.START_HERE_WINDOWS.split())
        self.assertIn("docker\\UPDATE-windows.txt", text)
        self.assertIn("for PowerShell and for Command Prompt", text)
        for step in ("stop the old clark", "rename this folder to clark-old", "unzip the newer download into the folder that held it", "start the new folder"):
            self.assertIn(step, text)
        self.assertNotIn("into a new folder", text)
        self.assertIn("Your data is not in the clark folder", text)
        self.assertTrue(release_files.covers("windows", "docker/UPDATE-windows.txt"))


if __name__ == "__main__":
    unittest.main()
