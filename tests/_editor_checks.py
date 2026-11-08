"""One generic finder for the page's Edit-only parts (#65; #66 and #67 re-use it unchanged).

`edit_elements(cdp, sid)` lists every form field (input, textarea, select), every element with a contenteditable attribute and every
element marked data-edit-only that is in the page, except the report bar's Week ending box (still typed as DD-MM-YYYY), which View has as well as Edit (the
prototype's bar, views.js:509; #439). View must give []: View removes the Edit parts, it does not hide them, so
it does not matter whether one is shown (display, opacity, size). Edit gives a list, which a test looks into by kind.
Each entry is a short text such as `button[data-edit-only][data-drag]` or `span[contenteditable=plaintext-only][data-title]`.
"""

FINDER = """(function () {
  var found = document.querySelectorAll('input, textarea, select, [contenteditable], [data-edit-only]');
  return Array.prototype.filter.call(found, function (el) { return el.id !== 'week-ending'; }).map(function (el) {
    var s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    if (el.hasAttribute('contenteditable')) s += '[contenteditable=' + el.getAttribute('contenteditable') + ']';
    Array.prototype.forEach.call(el.attributes, function (a) { if (a.name.indexOf('data-') === 0) s += '[' + a.name + ']'; });
    return s;
  });
})()"""


def edit_elements(cdp, sid):
    """Every form field, contenteditable and data-edit-only element now in the page, as short descriptions."""
    return cdp.js(FINDER, sid)


def for_project(hash_):
    """#944: the page for a project is its own page load (GET /?project=CODE), and a page opened at an address for another project loads itself
    again for it. A test that opens '#view&p=CODE' therefore opens '?project=CODE#view&p=CODE', so the document it measures is the one it
    goes on using; no assertion changes. Any address without a project code (or with the same one) is returned as it was."""
    import re
    m = re.search(r"[#&]p=([A-Za-z0-9]+)", hash_ or "")
    if not m or "?project=" in hash_:
        return hash_
    return "?project=" + m.group(1) + hash_


def for_url(url):
    """The same for a whole address: 'http://127.0.0.1:PORT/[?q][#view&p=CODE...]' gets 'project=CODE' in its query (see for_project)."""
    import re
    left, sep, right = url.partition("#")
    m = re.search(r"(?:^|&)p=([A-Za-z0-9]+)", right)
    if not sep or not m or re.search(r"[?&]project=", left):
        return url
    return left + ("&" if "?" in left else "?") + "project=" + m.group(1) + sep + right


def after_reload(js, action, ready="true"):
    """#944: changing project (clarkPage.setProject, a typed or Back address for another project) is a real page load now. `js` is the test's
    own evaluate-an-expression function and `action` the JavaScript that changes the project. Run it, then wait for the NEW document (the old
    one is marked; the new one is not and its document is complete), so the test goes on in the page it asked for."""
    import time
    js("window.__before = 1")
    js(action)
    end = time.time() + 20
    while time.time() < end:
        try:
            if js("window.__before !== 1 && document.readyState === 'complete' && %s" % ready):
                return
        except RuntimeError:
            pass                                    # the old document is going away
        time.sleep(0.1)
    raise AssertionError("the page for the other project did not load: " + repr(js("[location.href, window.__before, document.readyState, !!window.clarkPage]")))


def set_project_and_wait(js, code):
    """clarkPage.setProject(code), then after_reload."""
    after_reload(js, "window.clarkPage.setProject(%r)" % code)
