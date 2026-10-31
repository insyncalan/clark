"""One generic finder for the page's Edit-only parts (#65; #66 and #67 re-use it unchanged).

`edit_elements(cdp, sid)` lists every form field (input, textarea, select), every element with a contenteditable attribute and every
element marked data-edit-only that is in the page. View must give []: View removes the Edit parts, it does not hide them, so
it does not matter whether one is shown (display, opacity, size). Edit gives a list, which a test looks into by kind.
Each entry is a short text such as `button[data-edit-only][data-drag]` or `span[contenteditable=plaintext-only][data-title]`.
"""

FINDER = """(function () {
  var found = document.querySelectorAll('input, textarea, select, [contenteditable], [data-edit-only]');
  return Array.prototype.map.call(found, function (el) {
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
