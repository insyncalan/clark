"""#419: one shared way for a browser test to reload the page and wait for the NEW page before it reads anything.

`location.reload()` and `Page.reload` return while the old document is still up. A wait for something the old page already shows
(the list, the peek, a saved setting) is met at once by the old page, and the test then reads (or clicks) the page that is about to
go away. This is the flake PR 208 (#283) removed from five tests; this file is that wait, shared, so the rest use it too.

How it works: a token is set on the old window, the page is reloaded, and the wait ends only when the token is gone (so this is a
new document), the document has finished loading, and `ready` (an optional page condition) holds. A call made while Chrome is
navigating is answered "Inspected target navigated or closed" (seen on the hosted macOS runner): that poll is waited out and the
next one sees the new page. Any other error still fails the test. A page that never comes back fails with `what`.

`test_reload_waits.py` lists any test that reloads without this (or one of the waits it accepts, each with its reason).
"""
from test_server import wait

TOKEN = "__old_document"


def reload_to_new_page(js, ready="true", what="the page reloaded", seconds=15, reload=None):
    """Reload, then wait for the new document. `js(expr)` runs an expression in the page and returns its value. `ready` is an
    optional extra condition on the new page (a JavaScript expression). `reload` is what starts the reload (default
    `location.reload()`); pass a function for a test that reloads another way. Raises AssertionError with `what` on a timeout."""
    def asked(expr):
        try:
            return js(expr)
        except RuntimeError as e:
            if "navigated or closed" in str(e):
                return False
            raise

    # A test that has just navigated may find the page still changing: set the token once a call gets through.
    if not wait(lambda: asked(f"window.{TOKEN} = true; true"), seconds):
        raise AssertionError(f"timed out waiting for {what}")
    if reload is None:
        js("location.reload()")
    else:
        reload()

    if not wait(lambda: asked(f"window.{TOKEN} === undefined && document.readyState === 'complete' && !!({ready})"), seconds):
        raise AssertionError(f"timed out waiting for {what}")


def reload_to_new_page_cdp(cdp, sid, ready="true", what="the page reloaded", seconds=15):
    """reload_to_new_page for a test that holds a `cdp` and a session id `sid` and reloads with Chrome's own Page.reload."""
    reload_to_new_page(lambda expr: cdp.js(expr, sid), ready, what, seconds, reload=lambda: cdp.call("Page.reload", {}, sid))
