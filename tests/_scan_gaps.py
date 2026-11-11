"""The helpers the publish scan gap tests share (#112): the real finished page, a fragment spliced into it, and the bad/good
checks over a fragment. Split out when test_publish_scan_gaps.py was cut into four files so each takes about a quarter of the time."""
import _paths  # noqa: F401

from clark import publish, to_client  # noqa: E402
from clark.publish import PublishError  # noqa: E402
from test_publish import made  # noqa: E402

OPENER = '<script type="application/json" id="clark-data">'
_BASE = []


def real():
    if not _BASE:
        _BASE.append(made()[2])
    return _BASE[0]


def spliced(bad):
    text = real()
    assert text.count(OPENER) == 1
    return text.replace(OPENER, bad + OPENER, 1)


class GapsChecks:
    """The bad/good checks the Gaps classes use (a mixin: it has no tests of its own)."""
    def bad(self, *fragments, css=False):
        for frag in fragments:
            text = spliced(frag)
            self.assertTrue(publish.outside_addresses(text), f"outside_addresses passes {frag!r}")
            self.assertTrue(to_client.check_copy(text.encode("utf-8"), markers=()), f"check_copy passes {frag!r}")
            if css:
                with self.assertRaises(PublishError, msg=f"check_brand passes {frag!r}"):
                    publish.check_brand(text)

    def good(self, *fragments):
        for frag in fragments:
            self.assertEqual(publish.outside_addresses(spliced(frag)), [], frag)
