"""v1.1 item 625: a typed Windows path pasted as the client folder goes through host_folders.to_container (publish_flow.client_folder).

The mount point /shares/client is replaced by a folder in the test rig. Run: python3 dev/run_tests.py test_host_folders_route
"""
import unittest
from unittest import mock

from test_client_folder_paste import Base
from clark import host_folders as hf

ENV = {"CLARK_HOST": "windows", "CLARK_SHARE_CLIENT": "C:\\Users\\User\\Clients"}


class Typed(Base):
    def paste_on_windows(self, value, env=ENV):
        slots = dict(hf.SLOTS, client=(hf.SLOTS["client"][0], str(self.rig.root / "mount")))
        with mock.patch.dict("os.environ", env, clear=False), mock.patch("clark.platform.container_mode", lambda: True), \
                mock.patch.dict(hf.SLOTS, slots):
            return self.paste(value)

    def test_a_typed_path_inside_the_shared_folder_saves_the_container_path(self):
        (self.rig.root / "mount" / "ABC").mkdir(parents=True)
        status, got = self.paste_on_windows("c:/users/user/clients/ABC")
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual(self.folder(), str((self.rig.root / "mount" / "ABC").resolve()))

    def test_a_name_typed_in_the_wrong_case_saves_the_folder_as_the_share_lists_it(self):
        (self.rig.root / "mount" / "Abc Ltd").mkdir(parents=True)
        status, got = self.paste_on_windows("c:/users/user/clients/ABC LTD")
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual(self.folder(), str((self.rig.root / "mount" / "Abc Ltd").resolve()))

    def test_the_saved_response_returns_the_windows_form_as_typed(self):
        (self.rig.root / "mount" / "ABC").mkdir(parents=True)
        status, got = self.paste_on_windows("c:/users/user/clients/ABC")
        self.assertEqual(status, 200, got)
        self.assertEqual(got["folder_windows"], "C:\\users\\user\\clients\\ABC")

    def test_off_windows_the_saved_response_has_no_windows_form(self):
        (self.rig.root / "mount" / "ABC").mkdir(parents=True)
        status, got = self.paste_on_windows(str(self.rig.root / "mount" / "ABC"), env={"CLARK_HOST": ""})
        self.assertEqual(status, 409, got)
        self.assertNotIn("folder_windows", got)

    def test_a_path_outside_the_shared_folder_is_refused_and_nothing_is_saved(self):
        status, got = self.paste_on_windows("C:\\Other")
        self.assertEqual((status, got["ok"]), (409, False))
        self.assertIn("Nothing was changed.", got["message"])
        self.assertIsNone(self.folder())

    def test_a_shared_path_that_is_not_a_folder_is_refused(self):
        status, got = self.paste_on_windows("C:\\Users\\User\\Clients\\Missing")
        self.assertEqual((status, got["ok"]), (409, False))
        self.assertIsNone(self.folder())

    def test_off_windows_a_drive_path_is_still_unknown(self):
        status, got = self.paste_on_windows("C:\\Users\\User\\Clients", env={"CLARK_HOST": ""})
        self.assertEqual((status, got["message"]), (409, "That isn't a folder clark can find. Choose folder picks it for you."))


if __name__ == "__main__":
    unittest.main()
