"""Waiting for the NEW page after a reload, shared by every browser test that reloads.

`location.reload()` and Page.reload return while the old document is still up, so a read made straight afterwards can see the
old page (or none, mid-teardown), and Chrome answers a call made in that gap with 'Inspected target navigated or closed' (seen on
the hosted macOS runner). A test that reloads therefore:

  1. sets `window.__old_document = true` on the page it is leaving (the new document does not have it),
  2. reloads,
  3. waits with until_new_page(), whose condition starts with `window.__old_document === undefined`.

until_new_page() waits out the 'navigated or closed' answer and polls again; any other error still fails.
tests/test_reload_waits.py fails for a test that reloads without all of this.
"""
import time

OLD_DOCUMENT = "window.__old_document = true"
NEW_DOCUMENT = "window.__old_document === undefined"


def until_new_page(test, ask, what, seconds=15):
    """Poll ask() (a no-argument call that reads the page) until it is true, treating 'navigated or closed' as 'not yet'."""
    def asked():
        try:
            return ask()
        except RuntimeError as e:
            if "navigated or closed" in str(e):
                return False
            raise
    end = time.time() + seconds
    while time.time() < end:
        if asked():
            return
        time.sleep(0.2)
    test.fail(what)
