"""A person's click for the tests: a real mouse sequence (Input.dispatchMouseEvent), not a JS .click().

A JS .click() sends no mousedown, and the router's scroll restore after a hash change (router.js restore()) ends only on wheel, touchstart,
keydown or mousedown, so on a slow runner (macOS headless: slow requestAnimationFrame) it was still alive and put the jump back to 0.
"""


def click_at(cdp, sid, x, y):
    """The mouse moves to (x, y), goes down and comes up."""
    for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
        params = {"type": kind, "x": x, "y": y, "button": "none" if kind == "mouseMoved" else "left",
                  "buttons": 1 if kind == "mousePressed" else 0, "clickCount": 0 if kind == "mouseMoved" else 1}
        cdp.call("Input.dispatchMouseEvent", params, sid)


def click_centre(cdp, sid, find_js, what):
    """Click the centre of the element that the JS expression find_js returns; the element must be inside the window. Returns the point."""
    at = cdp.js("(function(){ var b = (%s), r = b.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, innerWidth, innerHeight]; })()" % find_js, sid)
    if not (0 <= at[0] <= at[2] and 0 <= at[1] <= at[3]):
        raise AssertionError(f"{what} is inside the window to be clicked: {at}")
    click_at(cdp, sid, at[0], at[1])
    return at


def menu_item_js(name_js):
    """JS for the Settings menu entry whose text is name_js (a JS expression, e.g. a quoted string)."""
    return "[...document.querySelectorAll('.set-menu .set-item')].find(b => b.textContent === %s)" % name_js
