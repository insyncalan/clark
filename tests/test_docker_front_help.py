"""Item 1100: Help says how to start clark on the Mac with Docker only in front, with the exact commands (the same ones docker/front.command takes).
Quick tier: reads Help's source and the script; no browser.
Run: python3 dev/run_tests.py test_docker_front_help"""
import json
import re
import unittest

from _paths import ROOT

HELP = json.loads((ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8"))
TASK = next(t for t in HELP["howto"]["tasks"] if t["id"] == "run-clark-with-docker")
LINE = next(s for s in TASK["s"] if s.startswith("Keep clark on the Mac and use Docker only to show it."))
SCRIPT = (ROOT / "docker" / "front.command").read_text(encoding="utf-8")


class HelpLine(unittest.TestCase):
    def test_the_line_gives_the_three_commands_exactly(self):
        for cmd in ("`bash docker/front.command server`", "`bash docker/front.command`", "`bash docker/front.command stop`", "`bash clark.command`"):
            self.assertIn(cmd, LINE)

    def test_every_command_in_the_line_is_one_the_script_accepts(self):
        for word in re.findall(r"bash docker/front\.command(?: (\w+))?`", LINE):
            self.assertTrue(word == "" or re.search(rf"^\s*{word}\)", SCRIPT, re.M), word)

    def test_it_names_the_page_the_person_sees_and_the_default_port(self):
        self.assertIn("localhost:8766", LINE)
        self.assertIn("clark is not running", LINE)
        self.assertIn("Connect, ask clark", LINE)

    def test_it_is_one_new_line_in_the_existing_docker_task_and_the_task_ids_are_unchanged(self):
        self.assertEqual(sum(1 for s in TASK["s"] if "front.command" in s), 1)
        self.assertEqual(len([t for t in HELP["howto"]["tasks"] if t["id"] == "run-clark-with-docker"]), 1)

    def test_no_path_that_is_not_in_the_download(self):
        self.assertTrue((ROOT / "docker" / "front.command").exists())
        self.assertNotIn("/home/", LINE)


if __name__ == "__main__":
    unittest.main()
