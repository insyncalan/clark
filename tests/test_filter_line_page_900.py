"""#153, #912: the one filter line on the Work items page, driven in the real page at 900 px.

Run: python3 dev/run_tests.py test_filter_line_page_900
test_filter_line_page drives the page at 1400 and 900 px in light and in dark. It was one file of about 400 s; it is now two: that file
loops over SIZES = (1400,) and this one runs the SAME test methods with SIZES = (900,). Only the methods that loop over SIZES are run
here (the others have no width to change and stay in test_filter_line_page), so every (width, theme) case is run exactly once and a
failed case is re-run on its own at about half the cost. Nothing about a test changes: the class below is the other file's Line.
"""
import inspect
import unittest

import test_filter_line_page as base


class Line(base.Line):
    """The tests of test_filter_line_page.Line that loop over the page widths, run at 900 px."""

    @classmethod
    def setUpClass(cls):
        cls._widths = base.SIZES
        base.SIZES = (900,)                    # the tests read the module's SIZES when they run
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        try:
            super().tearDownClass()
        finally:
            base.SIZES = cls._widths


for _name in dir(base.Line):
    if _name.startswith("test_") and "SIZES" not in inspect.getsource(getattr(base.Line, _name)):
        setattr(Line, _name, None)             # no width to change: it runs in test_filter_line_page only


if __name__ == "__main__":
    unittest.main()
