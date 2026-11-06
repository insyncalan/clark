"""Row 830: the Use cases page's inline pieces (U3 archived list, U4 Add a use case, U5 Export to Excel, U7 next step and link).

Run: python3 dev/run_tests.py test_use_cases_fields
Source-level checks (no browser): the words are the prototype's (system/prototype/usecases.js), the pieces sit on the page and the
detail with no Edit gate, and the published file (page-view.html) carries none of them. Owner on a use case (U6) is not built:
changes.py does not take it for use_cases. The browser run at 1400 and 900 px is the lead's, under the box lock.
"""
import re
import unittest

from _paths import SRC

PAGE = SRC / "clark" / "page"
SRCS = PAGE / "src"


def text(path):
    return path.read_text(encoding="utf-8")


class UseCaseFields(unittest.TestCase):
    def test_page_has_the_pieces(self):
        page = re.sub(r"\s+", " ", text(SRCS / "edit" / "UseCasesPage.jsx"))
        for want in ("Add a use case", "Export to Excel", "Show archived", "Hide archived", "Restore", "archived use case"):
            self.assertIn(want, page)
        self.assertIn('op: "restore"', page)
        self.assertIn("exportExcel", page)

    def test_detail_offers_next_step_and_link_without_edit_mode(self):
        detail = text(SRCS / "components" / "UseCaseDetail.jsx")
        self.assertRegex(detail, r"!ro && ed \?[^\n]*NextStep[^\n]*LinkButton")
        self.assertNotIn('mode.value', detail)
        edit = text(SRCS / "edit" / "UseCasesEdit.jsx")
        self.assertIn("b.live", edit)
        self.assertIn('"Done"', edit)

    def test_published_file_has_none(self):
        view = text(PAGE / "page-view.html")
        for gone in ("data-arch-toggle", "ucAddPage", "data-uc-step"):
            self.assertNotIn(gone, view)


if __name__ == "__main__":
    unittest.main()
