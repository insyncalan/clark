"""Serve the test page with the Classic theme layered (the page then has <style id="theme">, which classicTheme() reads).
`classic(test)` swaps the running server of a test_report_editor.Base test for one that serves that page."""
from clark import page, theme
from _real_server import real_server
import _testpage as testpage

NAME = "prototype-2.0"


def classic(test):
    test.s.close()
    css = theme.css(NAME)
    test.s = real_server(test.store.path, test.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css), seam=test.seam)
    test.addCleanup(test.s.close)
