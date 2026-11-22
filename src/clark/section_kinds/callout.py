"""Callout (H1, #96): the content of a section of type 'callout': one thing the reader must see. READY.

Stored (canonical JSON, checked by section_bodies before and after this): {"v": 1, "tone": "info" | "decision" | "warning",
"title": text, "paras": [text, ...], "html": HTML}, and from #1272 these optional fields: "category" (free text, 30 characters at most),
"colour" (one of COLOURS), "icon" (one of ICONS), "tile" and "heading" (true or false). A callout without them is an older one: it is stored and read unchanged, and
`upgrade` gives its defaults (tile and heading on, the colour and icon its tone had) when a reader needs them. Nothing is rewritten in the store. `html` is the words as the one editor writes them (sanitise.clean_html, at most HTML_MAX characters once cleaned); `paras` is what
older clarks wrote, still read and shown when there is no `html`. The editor saves `html` and empties `paras`. Typed only: it holds no reference to a work item, so nothing here can leak a hidden one.
Fields are picked by name and rebuilt; an unknown field is dropped. A callout with no title and no paragraph is empty: it
starts as '' (no content) and stays out of the published file.
"""
from clark.section_kinds import doclinks
from clark.section_kinds.base import Bad

READY = True
LIMIT = 32768
EMPTY = ""

TONES = ("info", "decision", "warning")
# #1272: colour and icon are named, so a reader who cannot tell colours apart is told the name in words (Word, Excel, the published page).
COLOURS = {"plain": "Plain", "violet": "Violet", "amber": "Amber", "red": "Red", "green": "Green", "grey": "Grey"}
ICONS = {"none": "No icon", "info": "Information", "question": "Question", "warning": "Warning triangle", "alert": "Alert", "check": "Tick", "clock": "Clock",
         "cal": "Calendar", "flag": "Flag", "lock": "Lock", "key": "Key", "bulb": "Light bulb", "star": "Star", "bell": "Bell",
         "megaphone": "Megaphone", "doc": "Document", "link": "Link", "people": "People", "money": "Money", "chart": "Chart", "shield": "Shield",
         "flash": "Lightning", "eye": "Eye", "table": "Table", "gear": "Gear", "sparkle": "Sparkle", "fork": "Two ways"}
TONE_LOOK = {"info": ("violet", "info"), "decision": ("amber", "question"), "warning": ("red", "warning")}    # what an older callout's tone drew
TONE_WORDS = {"info": "Information", "decision": "Decision needed", "warning": "Warning"}    # the word an older callout drew
CATEGORY_MAX = 30
TITLE_MAX, PARA_MAX, PARAS_MAX = 120, 600, 6
HTML_MAX = PARA_MAX * PARAS_MAX

NOT_OBJECT = "A callout must be one set of fields. Check it and try again."
BAD_FIELD = "A callout field has the wrong kind of value. Check it and try again."
BAD_TONE = "A callout is information, a decision needed or a warning. Choose one of the three."
TOO_LONG_TITLE = f"A callout title can be {TITLE_MAX} characters at most. Shorten it and try again."
TOO_LONG_PARA = f"A callout paragraph can be {PARA_MAX} characters at most. Shorten it or split it in two."
BAD_COLOUR = "A callout colour is Plain, Violet, Amber, Red, Green or Grey. Choose one of them."
BAD_ICON = "A callout icon is one from the list, or No icon. Choose one of them."
TOO_LONG_CATEGORY = f"A callout category can be {CATEGORY_MAX} characters at most. Shorten it and try again."
TOO_MANY = f"A callout can have {PARAS_MAX} paragraphs at most. Remove one and try again."


def _text(value, most, words):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise Bad(BAD_FIELD)
    value = value.strip()
    if len(value) > most:
        raise Bad(words)
    return value


def check(value, rules):
    """The callout rebuilt field by field (empty paragraphs dropped), or Bad in plain words that never quote it."""
    if not isinstance(value, dict) or value.get("v") != 1:
        raise Bad(NOT_OBJECT)
    tone = value.get("tone", "info")
    if tone not in TONES:
        raise Bad(BAD_TONE)
    title = _text(value.get("title"), TITLE_MAX, TOO_LONG_TITLE)
    paras = value.get("paras", [])
    if paras is None:
        paras = []
    if type(paras) is not list:
        raise Bad(BAD_FIELD)
    paras = [p for p in (_text(p, PARA_MAX, TOO_LONG_PARA) for p in paras) if p]
    if len(paras) > PARAS_MAX:
        raise Bad(TOO_MANY)
    out = {"v": 1, "tone": tone, "title": title, "paras": paras}
    category = _text(value.get("category"), CATEGORY_MAX, TOO_LONG_CATEGORY)
    if category:
        out["category"] = category
    for name, allowed, words in (("colour", COLOURS, BAD_COLOUR), ("icon", ICONS, BAD_ICON)):
        if value.get(name) is not None:
            if value[name] not in allowed:
                raise Bad(words)
            out[name] = value[name]
    for name in ("tile", "heading"):
        if value.get(name) is not None:
            if type(value[name]) is not bool:
                raise Bad(BAD_FIELD)
            out[name] = value[name]
    if value.get("html"):
        html = doclinks.rich(value["html"], rules, HTML_MAX, TOO_LONG_PARA)
        if html:
            out["html"] = html
    return out


def upgrade(value):
    """The schema step (#1272): a stored callout with every new field filled in. An older callout (no such fields) is tile on, heading on,
    its tone's word as the category, and the colour and icon its tone drew (a callout that stores a colour, an icon or a category of its own,
    even an empty one, keeps its own words). The stored text is not changed; a reader asks here."""
    tone = value.get("tone", "info")
    colour, icon = TONE_LOOK[tone]
    older = not any(name in value for name in ("category", "colour", "icon"))
    return {**value, "category": value.get("category", TONE_WORDS[tone] if older else ""), "colour": value.get("colour", colour), "icon": value.get("icon", icon),
            "tile": value.get("tile", True), "heading": value.get("heading", True)}


def words(value):
    """The category, the colour's name and the icon's name as words, for the published file, Word and Excel, where colour and icon are
    never carried by themselves: {"category", "colour_name", "icon_name"} ("" for none: Plain and No icon say nothing extra)."""
    v = upgrade(value)
    return {"category": v["category"], "colour_name": COLOURS[v["colour"]], "icon_name": "" if v["icon"] == "none" else ICONS[v["icon"]]}


def published(value, ctx):
    """What the file carries: {"content": {tone, title, paras}}, or None when there is nothing to show."""
    html = value.get("html")       # cleaned by check, and a publish checks the stored content again first
    if not value.get("title") and not value.get("paras") and not html:
        return None
    v = upgrade(value)
    return {"content": {"tone": value["tone"], "title": value["title"], "paras": list(value["paras"]), **({"html": html} if html else {}),
                        "category": v["category"], "colour": v["colour"], "icon": v["icon"], "tile": v["tile"], "heading": v["heading"], **words(value)}}
