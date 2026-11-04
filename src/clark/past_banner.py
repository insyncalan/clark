"""The banner, tinted frame and 'Back to now' put on a past publication when it is opened (#343; used by past_reports, guarded).

The kept file is never changed: it stays on disk exactly as it was published, and its SHA-256 is checked before anything here
runs. `frame` returns the same page with one block added straight after the opening <body> tag, for that one visit: a banner
('Publication N · DD-MM-YYYY · read only', 'Back to now'), a tinted frame round the window that takes no clicks, and a short
script that closes the tab (or goes back to clark's own page when the tab can't be closed). Taking that block out again gives the
published bytes back exactly (`MARK_START`, `MARK_END`). The words are the prototype's (system/prototype/past.js). Nothing from a
request goes in but a whole number and a date made from the publication's own row.

A published page carries its own policy in a <meta> (publish.csp_meta): scripts and styles only by hash. That policy would stop the
block's own style and script, so the SHA-256 of each (both fixed text in this file, nothing from a request) is added to the two
lists in that meta, for this visit only; nothing else in the policy is touched, and `unframe` takes both back out. Standard
library only, Python 3.9."""
import base64
import hashlib
import re

MARK_START = b"<!--clark-past-start-->"
MARK_END = b"<!--clark-past-end-->"
BODY = re.compile(rb"<body(?=[\s>/])[^>]*>", re.IGNORECASE)
DAY = re.compile(r"\d\d-\d\d-\d{4}")

TITLE = "Publication {number} · {day} · read only"
BACK = "Back to now"
SMALL = "The report as it was published · corrections go into the next report"

STYLE = (
    "#clark-past-banner{position:sticky;top:0;z-index:2147483646;box-sizing:border-box;margin:0;padding:10px 16px;"
    "background:#fff0c2;color:#3b2a00;border-bottom:2px solid #c98f0a;font:15px/1.4 system-ui,-apple-system,Segoe UI,sans-serif}"
    "#clark-past-banner b{font-weight:700}#clark-past-banner small{display:block;font-size:13px;opacity:.85}"
    "#clark-past-banner a{color:inherit;font-weight:600;margin-left:12px;text-decoration:underline}"
    "#clark-past-frame{position:fixed;inset:0;z-index:2147483645;box-sizing:border-box;border:8px solid #c98f0a;"
    "background:rgba(201,143,10,.07);pointer-events:none}"
    "@media (prefers-color-scheme:dark){#clark-past-banner{background:#3d2f08;color:#ffeab0;border-bottom-color:#e0ae3a}"
    "#clark-past-frame{border-color:#e0ae3a;background:rgba(224,174,58,.08)}}"
    "@media print{#clark-past-banner,#clark-past-frame{display:none}}"
)
SCRIPT = ("document.getElementById('clark-past-back').addEventListener('click',function(e){"
          "try{window.close()}catch(x){}});")


def block(number, day):
    """The block that is added, as bytes. `number` is a whole number from 1 and `day` is DD-MM-YYYY, or this raises ValueError."""
    if type(number) is not int or number < 1 or not isinstance(day, str) or not DAY.fullmatch(day):
        raise ValueError("a publication number and a day are needed")
    words = TITLE.format(number=number, day=day)
    html = (f"<style>{STYLE}</style>"
            f'<div id="clark-past-banner" role="status"><b>{words}</b><a href="/" id="clark-past-back">{BACK}</a>'
            f"<small>{SMALL}</small></div>"
            f'<div id="clark-past-frame" aria-hidden="true"></div><script>{SCRIPT}</script>')
    return MARK_START + html.encode("utf-8") + MARK_END


def hashes():
    """The two source expressions the page's own policy must allow for the block: ('sha256-..' of the style, of the script)."""
    def one(text):
        return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode() + "'"
    return one(STYLE), one(SCRIPT)


META = re.compile(rb'(<meta http-equiv="Content-Security-Policy" content=")([^"]*)(">)')
NONE = b"'none'"


def allow(policy, directive, source):
    """`policy` (bytes) with `source` added to the directive's list; None when the policy has no such directive."""
    m = re.search(rb"(?:^|; )" + directive + rb" ([^;]*)", policy)
    if m is None:
        return None
    value = m.group(1)
    new = source if value.strip() == NONE else value + b" " + source
    return policy[:m.start(1)] + new + policy[m.end(1):]


def frame(page, number, day):
    """`page` (the published bytes) with the block after its opening <body> tag and the block's two hashes allowed in the page's own
    policy meta; None when it has no <body> tag to put the block after, or its policy has no script or style list to add to."""
    m = BODY.search(page)
    if m is None:
        return None
    meta = META.search(page)
    if meta is not None:
        style, script = (h.encode("ascii") for h in hashes())
        policy = allow(meta.group(2), b"script-src", script)
        policy = None if policy is None else allow(policy, b"style-src-elem", style)
        if policy is None or meta.end() > m.start():
            return None
        page = page[:meta.start(2)] + policy + page[meta.end(2):]
        m = BODY.search(page)
    return page[:m.end()] + block(number, day) + page[m.end():]


def unframe(shown):
    """The bytes with the block taken out again (what a test, or a reader, compares with the published file)."""
    start = shown.find(MARK_START)
    end = shown.find(MARK_END)
    if start < 0 or end < start:
        return shown
    page = shown[:start] + shown[end + len(MARK_END):]
    meta = META.search(page)
    if meta is None:
        return page
    policy = meta.group(2)
    for directive, source in ((b"script-src", hashes()[1]), (b"style-src-elem", hashes()[0])):
        source = source.encode("ascii")
        alone = re.compile(rb"(^|; )" + directive + b" " + re.escape(source) + rb"(?=;|$)")
        policy = alone.sub(lambda m: m.group(1) + directive + b" " + NONE, policy) if alone.search(policy) else policy.replace(b" " + source, b"")
    return page[:meta.start(2)] + policy + page[meta.end(2):]
