"""Hunt fixes on the published file, checked in the source (no browser): the top bar tabs scroll inside their bar up to 1000 px,
paper lists every use case, and a kept Work items choice is not written into the address of another page.

Run: python3 dev/run_tests.py test_hunt107_published_source
"""
import re
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "src" / "clark" / "page"


def media_block(css, query):
    out = []
    for m in re.finditer(r"@media \(%s\) \{" % re.escape(query), css):
        depth, i = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        out.append(css[m.end():i - 1])
    return "\n".join(out)


class Source(unittest.TestCase):
    def test_the_top_bar_tabs_scroll_inside_the_bar_up_to_1000px(self):
        css = (PAGE / "shell.css").read_text(encoding="utf-8")
        wide = media_block(css, "max-width: 1000px")
        self.assertRegex(wide, r"\.top \.tabs \{[^}]*overflow-x: auto")
        self.assertRegex(wide, r"\.top \.asat \{[^}]*white-space: nowrap")
        self.assertNotRegex(media_block(css, "max-width: 700px"), r"\.top \.tabs \{[^}]*overflow-x")

    def test_printing_ignores_the_open_use_case(self):
        jsx = (PAGE / "src" / "components" / "UseCasesTab.jsx").read_text(encoding="utf-8")
        self.assertRegex(jsx, r"const open = uc\.value && !printing\.value \?")

    def test_the_kept_filters_go_into_the_address_only_on_work_items(self):
        js = (PAGE / "src" / "stores" / "clientMemory.js").read_text(encoding="utf-8")
        self.assertRegex(js, r'if \(!f\.peek\(\) && view\.peek\(\) === "work"\) setFilterState\(')


if __name__ == "__main__":
    unittest.main()
