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
TAG = {"overdue": {"r": "Overdue"}, "decisions": {"a": "Waiting"}, "risks": {"a": "Watch", "r": "High"}}      # glanceTiles.js TILE_WORDS_OF
TAG_ANY = {"g": "On track", "a": "At risk", "r": "Off track"}                                                   # glanceTiles.js TILE_WORDS


def _text(v):
    return v.strip() if isinstance(v, str) else ""


def _health(published):
    project = (published.get("data") or {}).get("project") or {}
    t = glance.tiles({"project": project}, published["as_at"], tile_order=["health"], for_client=True, kept={"rows": [], "hidden_types": set()})[0]
    return {"key": "health", "label": t["title"], "figure": str(t["value"]), "tag": "", "note": t.get("reason") or "",         # glance.tiles gives the reason as plain words already
            "colour": (t.get("pill") or {}).get("colour") or None}


def read(published, sec):
    """{"health_row": the health tile when it has a row of its own, else None, "tiles": [{key, label, figure, tag, note, colour}] in the
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
    return {"health_row": row, "tiles": tiles}
