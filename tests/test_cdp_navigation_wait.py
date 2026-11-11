"""The shared CDP pipe waits out a page that is navigating (error -32000, "Inspected target navigated or closed") on an evaluate,
and only that: no browser needed (a fake pipe stands in for Chrome)."""
import unittest

from test_server import _Pipe

NAV = {"code": -32000, "message": "Inspected target navigated or closed"}


class Fake(_Pipe):
    def __init__(self, script):
        super().__init__(None, None)
        self.script, self.asked = list(script), []

    def _call_once(self, method, params=None, session=None):
        self.asked.append(method)
        step = self.script.pop(0)
        if isinstance(step, dict) and "code" in step:
            raise RuntimeError(step)
        return step


class WaitsOutNavigation(unittest.TestCase):
    def test_two_navigation_errors_then_the_answer(self):
        p = Fake([NAV, NAV, {"result": {"value": 7}}])
        self.assertEqual(p.js("1+6", "s"), 7)
        self.assertEqual(len(p.asked), 3)

    def test_it_gives_up_at_the_deadline_with_the_error(self):
        p = Fake([NAV] * 1000)
        p.NAVIGATION_WAIT = 0.2
        with self.assertRaises(RuntimeError) as c:
            p.js("1", "s")
        self.assertEqual(c.exception.args[0], NAV)

    def test_another_error_is_not_retried(self):
        other = {"code": -32601, "message": "not found"}
        p = Fake([other, {"result": {"value": 1}}])
        with self.assertRaises(RuntimeError):
            p.js("1", "s")
        self.assertEqual(len(p.asked), 1)

    def test_other_methods_are_not_retried(self):
        p = Fake([NAV, {}])
        with self.assertRaises(RuntimeError):
            p.call("Page.navigate", {}, "s")
        self.assertEqual(len(p.asked), 1)

    def test_an_answer_is_returned_as_it_is(self):
        p = Fake([{"result": {"value": False}}])
        self.assertIs(p.js("false", "s"), False)


if __name__ == "__main__":
    unittest.main()
