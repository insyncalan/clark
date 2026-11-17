"""Row 1264 slice 7: the glance template as the Word report and the client workbook print it, one reader for both so they cannot drift.

Reads a published glancetemplate section (its `content`, section_kinds/glancetemplate.published) and gives the tiles in the content's order:
Project health (when its eye is on; from the project row the file carries, the At a glance tile's own code), the three counting tiles from
the content's counts (the figures the View draws; a tile the content has no count for is absent), and the bespoke tiles. A hidden tile is
not in the content at all, so it is not here. No new words: the tag words of a count are the page's (glanceTiles.js tileWord), a bespoke
tile's are the person's own.
"""
from clark import glance

COUNTING = ("overdue", "risks", "decisions")
TONE = {"g": "green", "a": "amber", "r": "red", "b": "blue", "n": None}
BESPOKE_TONE = {"green": "green", "amber": "amber", "red": "red", "blue": "blue", "neutral": None}
PER_LINE, PER_LINE_HALF = 4, 2                                                                                  # glancetemplate.PER_ROW_DEFAULT; half width always draws 2 (shell.css .tpl-gt in a slot)
TAG = {"overdue": {"r": "Overdue"}, "decisions": {"a": "Waiting"}, "risks": {"a": "Watch", "r": "High"}}      # glanceTiles.js TILE_WORDS_OF
TAG_ANY = {"g": "On track", "a": "At risk", "r": "Off track"}                                                   # glanceTiles.js TILE_WORDS


def _text(v):
    return v.strip() if isinstance(v, str) else ""


def _health(published):
    project = (published.get("data") or {}).get("project") or {}
    t = glance.tiles({"project": project}, published["as_at"], tile_order=["health"], for_client=True, kept={"rows": [], "hidden_types": set()})[0]
    return {"key": "health", "label": t["title"], "figure": str(t["value"]), "tag": "", "note": t.get("reason") or "",         # glance.tiles gives the reason as plain words already
            "colour": (t.get("pill") or {}).get("colour") or None}


def _right_half(published, sec):
    """True when `sec` is the second of a side-by-side pair: only the first carries `beside` 1, so the page's own walk (placement.js) is read again:
    a section with `beside` 1 and one after it opens a row of two, and the one after it is the right half."""
    rows = [x for x in (published or {}).get("sections") or [] if isinstance(x, dict)]
    i = 0
    while i < len(rows):
        if rows[i].get("beside") in (1, True) and i + 1 < len(rows):
            if rows[i + 1].get("id") == sec.get("id") and sec.get("id") is not None:
                return True
            i += 1
        i += 1
    return False


def per_line(sec, c, published=None):
    """Tiles on a line as the View draws them: 2 at half width (the published section's `beside` is 1, or it is the half after one that is: the page's
    slot-left or slot-right), else the body's per_row when it is 3 or 4, else 4 (the default is not stored)."""
    if sec.get("beside") in (1, True) or _right_half(published, sec):
        return PER_LINE_HALF
    n = c.get("per_row")
    return n if type(n) is int and n in (3, 4) else PER_LINE


def read(published, sec):
    """{"per_line": tiles on a line (per_line), "health_row": the health tile when it has a row of its own, else None, "tiles": [{key, label, figure, tag, note, colour}] in the
    section's order (health included there when it is shown and not on its own row)}. Total: a content that is not an object is nothing."""
    c = sec.get("content") if isinstance(sec.get("content"), dict) else {}
    h = c.get("health") if isinstance(c.get("health"), dict) else {}
    shown, own = h.get("shown", True) is not False, h.get("own_row") is True
    counts = {x.get("tile"): x for x in c.get("counts") or [] if isinstance(x, dict)}
    bespoke = {t.get("id"): t for t in c.get("bespoke") or [] if isinstance(t, dict)}
    order = [i for i in c.get("order") or [] if isinstance(i, str)]
    order += [i for i in ("health",) + COUNTING + tuple(bespoke) if i not in order]
    tiles, row = [], None
    for key in order:
        if key == "health":
            if not shown:
                continue
            t = _health(published)
            if own:
                row = t
                continue
        elif key in COUNTING:
            x = counts.get(key)
            if not x:
                continue
            rag = x.get("rag") if x.get("rag") in TONE else "n"
            t = {"key": key, "label": _text(x.get("title")), "figure": str(x.get("value", "")), "tag": TAG.get(key, {}).get(rag) or TAG_ANY.get(rag, ""),
                 "note": _text(x.get("detail")), "colour": TONE[rag]}
        elif key in bespoke:
            b = bespoke[key]
            t = {"key": key, "label": _text(b.get("label")), "figure": _text(b.get("figure")), "tag": _text(b.get("tag")), "note": _text(b.get("note")),
                 "colour": BESPOKE_TONE.get(b.get("tone"))}
        else:
            continue
        tiles.append(t)
    return {"per_line": per_line(sec, c, published), "health_row": row, "tiles": tiles}
