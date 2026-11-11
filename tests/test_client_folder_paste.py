"""Item 647: Settings, Publishing: the client folder pasted as a folder path on this computer, as well as chosen.

A pasted folder must be inside a OneDrive root and then gets exactly the checks a chosen one gets (to_client.preflight). A pasted
link (a SharePoint, OneDrive or any other address) is refused by its form, in one plain sentence that points at Choose folder:
it is never opened or matched to a folder by name (the owner's change request: a name shared by two clients' libraries could
save the wrong client's folder), and nothing is saved. The route tests run a real server over the real publisher (the Rig of
tests/test_publish_route.py); the page tests need Chrome and fail, never skip, without it. Widths 1400 and 900, light and dark.

Run: python3 dev/run_tests.py test_client_folder_paste
"""
import os
import unittest
from pathlib import Path
from unittest import mock

from test_publish_route import Rig
from clark import publish_flow

M = publish_flow.MESSAGES
UNKNOWN = "That isn't a folder clark can find. Choose folder picks it for you."
NOT_SYNCED = "That folder isn't one OneDrive syncs on this computer. Choose folder picks it for you."
LINK = "A link can't be used here. Choose folder picks the folder on this computer. Nothing was saved."


class Base(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(self, saved=False)
        self.shared = self.rig.root / "OneDrive-SharedLibraries-Fictional"
        self.library = self.shared / "Harbour Bridge - Documents"
        self.reports = self.library / "Client Reports" / "Week 43"
        self.reports.mkdir(parents=True)
        self.rig.publisher.onedrive_roots = [str(self.rig.onedrive), str(self.shared)]

    def folder(self):
        return self.rig.store.read("projects", ref="PUB")["publish_client"]

    def paste(self, value):
        return self.rig.call("POST", "/api/client-folder", {"project": "PUB", "action": "paste", "value": value})

    def refused(self, value, words):
        status, got = self.paste(value)
        self.assertEqual((status, got["ok"], got["message"]), (409, False, words), repr(value)[:80])
        self.assertIsNone(self.folder(), "a refusal changes nothing")


class TheWords(unittest.TestCase):
    def test_the_owners_words_are_as_agreed(self):
        self.assertEqual((M["paste_unknown"], M["paste_not_synced"], M["paste_link"]), (UNKNOWN, NOT_SYNCED, LINK))
        self.assertNotIn("paste_no_match", M, "no link is matched to a folder")
        for text in (UNKNOWN, NOT_SYNCED, LINK):
            self.assertIn("Choose folder", text, "each points at Choose folder")


class APastedFolder(Base):
    def test_a_folder_inside_onedrive_is_saved_as_a_chosen_one(self):
        status, got = self.paste("  " + str(self.rig.client) + "  ")
        self.assertEqual((status, got["ok"], got["changed"], got["folder_name"]), (200, True, True, "Harbour Bridge"))
        self.assertEqual(self.folder(), str(self.rig.client))
        self.assertEqual(self.rig.picks, [], "pasting never opens the folder window")
        self.assertEqual(list(self.rig.client.iterdir()), [], "nothing is written into it")
        status, got = self.paste(str(self.rig.client))
        self.assertEqual((status, got["changed"], got["message"]), (200, False, M["folder_unchanged"]))

    def test_a_folder_from_the_home_folder_sign(self):
        with mock.patch.dict(os.environ, {"HOME": str(self.rig.root)}):
            status, got = self.paste("~/OneDrive-Fictional/Client reports/Harbour Bridge")
        self.assertEqual(status, 200, got)
        self.assertEqual(self.folder(), str(self.rig.client))

    def test_a_folder_outside_onedrive_is_refused(self):
        outside = self.rig.root / "Elsewhere"
        outside.mkdir()
        self.refused(str(outside), NOT_SYNCED)
        self.refused(str(self.rig.local), NOT_SYNCED)

    def test_dot_dot_and_links_that_leave_onedrive_are_refused(self):
        outside = self.rig.root / "Elsewhere"
        outside.mkdir()
        self.refused(str(self.rig.onedrive) + "/../Elsewhere", UNKNOWN)
        self.refused(str(self.rig.client) + "/..", UNKNOWN)
        link = self.rig.onedrive / "Looks synced"
        link.symlink_to(outside, target_is_directory=True)
        self.refused(str(link), NOT_SYNCED)
        inward = self.rig.root / "Shortcut"
        inward.symlink_to(self.rig.client, target_is_directory=True)
        status, got = self.paste(str(inward))         # a link from outside into OneDrive is saved as where it really is
        self.assertEqual(status, 200, got)
        self.assertEqual(self.folder(), str(self.rig.client))

    def test_a_missing_folder_or_a_file_is_refused(self):
        self.refused(str(self.rig.onedrive / "Not there"), UNKNOWN)
        f = self.rig.onedrive / "a file.txt"
        f.write_text("x", encoding="utf-8")
        self.refused(str(f), UNKNOWN)

    def test_the_same_refusals_as_choose_folder(self):
        inside = self.rig.onedrive / "clark-data"
        inside.mkdir()
        self.rig.publisher.data_dir = inside
        status, got = self.paste(str(inside))
        self.assertEqual((status, got["code"]), (409, "client_folder_refused"))
        self.assertIn("inside clark's own data folder", got["message"])
        self.assertIsNone(self.folder())


class ALink(Base):
    def test_a_link_is_refused_by_its_form_and_nothing_is_saved(self):
        """A SharePoint link to the very folder that is synced here is still refused: no folder is ever found from a link."""
        for link in ("https://fictional.sharepoint.com/sites/HarbourBridge/Shared%20Documents/Client%20Reports/Week%2043",
                     "https://onedrive.live.com/?id=ABC123%21456&cid=ABC123",
                     "http://example.test/Client%20reports/Harbour%20Bridge",
                     "file://" + str(self.rig.client)):
            with self.subTest(link=link[:70]):
                self.refused(link, LINK)
                self.assertEqual(self.rig.picks, [], "no folder window either")

    def test_other_link_forms_are_refused_the_same_way(self):
        for link in ("HTTPS://Fictional.SharePoint.com/sites/HarbourBridge/Shared%20Documents",
                     "fictional.sharepoint.com/sites/HarbourBridge/Shared%20Documents",
                     "fictional-my.sharepoint.com/personal/sam_fictional_com/Documents",
                     "onedrive.live.com/?id=ABC123", "1drv.ms/f/s!AbCdEf", "https://1drv.ms/f/s!AbCdEf",
                     "ftp://fictional.sharepoint.com/x", "smb://server/share", "  https://example.test/x  "):
            with self.subTest(link=link[:70]):
                self.refused(link, LINK)

    def test_nothing_is_fetched(self):
        with mock.patch("socket.socket", side_effect=AssertionError("a network call")), \
                mock.patch("socket.create_connection", side_effect=AssertionError("a network call")), \
                mock.patch("pathlib.Path.iterdir", side_effect=AssertionError("a folder listing")):
            got = self.rig.publisher.pasted_folder("https://fictional.sharepoint.com/sites/HarbourBridge/Shared%20Documents/Client%20Reports/Week%2043")
        self.assertEqual(got, (None, "paste_link"))


class Junk(Base):
    def test_anything_else_is_refused(self):
        for value in ("", "   ", "Client reports/Harbour Bridge", "~someone/OneDrive", "javascript:alert(1)", "notes.txt",
                      "https://fictional.sharepoint.com/x\n" + str(self.rig.client), str(self.rig.client) + "\n/etc", str(self.rig.client) + "\x00", "\u202e" + str(self.rig.client),
                      str(self.rig.client) + "/" + "x" * 2100):
            with self.subTest(value=repr(value)[:60]):
                self.refused(value, UNKNOWN)

    def test_a_bad_body_is_a_bad_action(self):
        for body in ({"action": "paste"}, {"action": "paste", "value": 7}, {"action": "paste", "value": ["/x"]},
                     {"action": "paste", "value": "/x", "folder": "/x"}, {"action": "choose", "value": str(self.rig.client)}):
            with self.subTest(body=body):
                status, got = self.rig.call("POST", "/api/client-folder", {"project": "PUB", **body})
                self.assertEqual((status, got["code"]), (400, "bad_action"))
        self.assertEqual(self.rig.picks, [])
        self.assertIsNone(self.folder())


class ThePage(unittest.TestCase):
    """The box under Choose folder, at 1400 and 900, light and dark: it pastes, saves and shows a refusal in a role=alert."""

    def test_the_box_is_shown_and_works(self):
        from test_page import navigate
        from test_server import chrome, wait
        import _testpage as testpage
        rig = Rig(self, saved=False, page_html=testpage.html)
        rig.publisher.onedrive_roots = [str(rig.onedrive)]
        with chrome() as cdp:
            sid = navigate(cdp, rig.httpd.server_port, "#settings&p=PUB&s=folder")
            js = lambda expr: cdp.js(expr, sid)  # noqa: E731
            until = lambda expr, what: self.assertTrue(wait(lambda: js(expr), 15), what)  # noqa: E731
            until("!!document.querySelector('#client-folder-paste')", "the paste box")
            grounds = {}
            for scheme in ("light", "dark"):
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                for width in (1400, 900):
                    with self.subTest(scheme=scheme, width=width):
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 800, "deviceScaleFactor": 1, "mobile": False}, sid)
                        js("document.querySelector('#client-folder-paste').scrollIntoView({block: 'center'})")
                        box = js("(function(){var b=document.querySelector('#client-folder-paste').getBoundingClientRect(),"
                                 "u=document.querySelector('[data-use-pasted]').getBoundingClientRect(),"
                                 "c=document.querySelector('[data-choose-folder]').getBoundingClientRect();"
                                 "return {w: b.width, h: b.height, below: b.top > c.bottom, beside: Math.abs(u.top - b.top) < 12 && u.left > b.right,"
                                 "fits: document.documentElement.scrollWidth <= innerWidth}})()")
                        self.assertTrue(box["w"] > 200 and box["h"] >= 28, box)
                        self.assertTrue(box["below"] and box["beside"] and box["fits"], box)
                        self.assertEqual(js("document.querySelector('label[for=client-folder-paste]').innerText"),
                                         "or paste the folder's path")
                        self.assertEqual(js("document.querySelector('#client-folder-paste-hint').innerText"),
                                         "A folder on this computer.")
                        grounds[scheme] = js("getComputedStyle(document.querySelector('#client-folder-paste')).backgroundColor")
                        self.assertTrue(js("document.querySelector('[data-use-pasted]').disabled"), "Use waits for something pasted")
            self.assertNotEqual(grounds["light"], grounds["dark"], "the box follows the theme")
            # a refusal, then a folder that is saved (typed in as a person pastes, so the page's own state is used)
            put = ("(function(v){var i=document.querySelector('#client-folder-paste');i.value=v;"
                   "i.dispatchEvent(new Event('input', {bubbles: true}));})(%s)")
            js(put % '"not a folder"')
            until("!document.querySelector('[data-use-pasted]').disabled", "Use is ready")
            js("document.querySelector('[data-use-pasted]').click()")
            until("document.querySelector('#client-folder [role=alert]') && document.querySelector('#client-folder [role=alert]').innerText.indexOf(%r) >= 0" % UNKNOWN,
                  "the plain refusal")
            js(put % repr(str(rig.client)))
            until("!document.querySelector('[data-use-pasted]').disabled", "Use is ready")
            js("document.querySelector('#client-folder-paste').form.requestSubmit()")       # Enter in the box does the same
            until("/Harbour Bridge/.test(document.querySelector('#client-folder-now').innerText)", "the folder is shown")
            self.assertEqual(rig.store.read("projects", ref="PUB")["publish_client"], str(rig.client))
            self.assertEqual(js("document.querySelector('#client-folder-paste').value"), "", "the box is emptied once it is used")


if __name__ == "__main__":
    unittest.main()
