"""Glance template (row 1264, slice 1): the content of a section of type 'glancetemplate'. A NEW type, not a variant of the built-in At a
glance section (type glance): the built-in keeps its own tiles table and every existing report keeps today's look.

Stored (canonical JSON, checked by section_bodies before and after this):
  {"v": 1,
   "health": {"shown": bool, "own_row": bool},                       # the eye on Project health; Project health on its own row (off by default)
   "per_row": 3 | 4,                                                  # tiles on a line at full width (row 1264 slice 9); 4 is the default and is not stored
   "order": [tile id, ...],                                           # all tiles: the built-in names and the ids of the bespoke tiles
   "builtin": {"overdue" | "risks" | "decisions": {"hidden": bool, "outline": "R" | "A" | "G" | "N"}},
   "bespoke": [{"id", "label", "figure", "tag", "note", "tone", "hidden"}]}
Every field has a default (health shown, own row off, the built-in order then the bespoke tiles as listed, nothing hidden, outline
automatic, tone neutral), and a field that holds its default is not stored, so one content always stores as the same text. Counts are
never stored: the three built-in figures are worked out from the rows publish kept, at publish time (a later slice). Typed only: no
reference to a work item. Fields are picked by name and an unknown one is refused. Limits are in characters, not bytes. The number of
bespoke tiles is held to BESPOKE_MAX, the one constant the server and (later) the page read.
"""
import re

from clark.section_kinds.base import Bad

READY = True
LIMIT = 32768
EMPTY = ""                                        # a new template is left out of the file until it is first changed (row 1251); the Edit then writes the health eye OFF (glanceBody.js readBody: a never-written body reads as off, ticket 1264), while a body with no health field (an existing page) reads as shown

BESPOKE_MAX = 12                                  # the one tile cap: 12 is FINAL (ruled)
LABEL_MAX, FIGURE_MAX, TAG_MAX, NOTE_MAX = 40, 12, 12, 60      # characters, the text limits are approved
BUILT_IN = ("health", "overdue", "risks", "decisions")          # the tiles that count or show the project, in their default order
SETTLED = BUILT_IN[1:]                                           # the ones with a hidden flag and an outline (health has the eye)
OUTLINES = ("R", "A", "G", "N")                                  # glance_tiles.outline, '' (automatic) is not stored
TONES = ("green", "amber", "red", "blue", "neutral")
ID = re.compile(r"[a-z][a-z0-9]{0,15}\Z")
PER_ROW = (3, 4)                                                 # tiles on a line at full width; half width always draws 2 (the page's rule, not stored)
PER_ROW_DEFAULT = 4
KEYS = ("v", "health", "per_row", "order", "builtin", "bespoke")
TILE_KEYS = ("id", "label", "figure", "tag", "note", "tone", "hidden")

KEYS_OF_WORDS = ("not_object", "unknown_field", "not_bool", "bad_outline", "bad_tone", "bad_id", "dup_id", "bad_order", "too_many",
                 "label_missing", "label_long", "figure_long", "tag_long", "note_long", "bad_text", "too_long", "bad_per_row")


def words():      # words approved 17-11, see PR
    return {
        "not_object": "At a glance must be one set of fields. Check it and try again.",
        "unknown_field": "At a glance has a field it does not keep. Reload the page and try again.",
        "not_bool": "A yes or no setting in At a glance has the wrong kind of value. Check it and try again.",
        "bad_outline": "The outline colour of a tile is green, amber, red or no colour. Choose one of those.",
        "bad_tone": "The colour of a tile is green, amber, red, blue or neutral. Choose one of those.",
        "bad_id": "A tile in At a glance has a name it cannot keep. Reload the page and try again.",
        "dup_id": "Two tiles in At a glance have the same name. Reload the page and try again.",
        "bad_order": "The order of the tiles in At a glance cannot be kept. Reload the page and try again.",
        "too_many": "You can have up to 12 tiles.",
        "label_missing": "Give the tile a label.",
        "label_long": f"The tile label is too long ({LABEL_MAX} characters at most). Shorten it and try again.",
        "figure_long": f"The tile figure is too long ({FIGURE_MAX} characters at most). Shorten it and try again.",
        "tag_long": f"The tile tag is too long ({TAG_MAX} characters at most). Shorten it and try again.",
        "note_long": f"The tile note is too long ({NOTE_MAX} characters at most). Shorten it and try again.",
        "bad_text": "A tile in At a glance has text of the wrong kind. Check it and try again.",
        "bad_per_row": "Tiles on a line is 3 or 4. Choose one of those.",
        "too_long": f"At a glance is too long to keep ({LIMIT // 1024} KB at most in all). Remove a tile or shorten the text and try again.",
    }


APPROVED = words()
WORDS = APPROVED


def _no(key):
    raise Bad(words()[key])


def _flag(value, default):
    return value if type(value) is bool else default


def _default_order(bespoke):
    return list(BUILT_IN) + [t["id"] for t in bespoke]


def _complete(order, bespoke):
    ids = _default_order(bespoke)
    given = [i for i in order if isinstance(i, str) and i in ids] if isinstance(order, list) else []
    seen = []
    for i in given + ids:
        if i not in seen:
            seen.append(i)
    return seen


def _read_tile(t):
    """One bespoke tile as upgrade reads it, or None when it is not a tile (no id or no label)."""
    if type(t) is not dict or not isinstance(t.get("id"), str) or not isinstance(t.get("label"), str) or not t["label"].strip():
        return None
    out = {"id": t["id"], "label": t["label"].strip(), "tone": t["tone"] if t.get("tone") in TONES else "neutral", "hidden": _flag(t.get("hidden"), False)}
    for k in ("figure", "tag", "note"):
        out[k] = t[k].strip() if isinstance(t.get(k), str) else ""
    return {k: out[k] for k in TILE_KEYS}


def upgrade(value):
    """The body with every field present at its default (version 1 is the only one so far), for a reader that needs them all. Total: a
    body that is not an object, or that holds a wrong kind of value, reads as the defaults for that part."""
    v = value if type(value) is dict else {}
    h = v.get("health") if type(v.get("health")) is dict else {}
    b = v.get("builtin") if type(v.get("builtin")) is dict else {}
    bespoke, seen = [], set()
    for t in v.get("bespoke") if isinstance(v.get("bespoke"), list) else []:
        t = _read_tile(t)
        if t and t["id"] not in seen and t["id"] not in BUILT_IN:
            seen.add(t["id"])
            bespoke.append(t)
    builtin = {}
    for name in SETTLED:
        s = b.get(name) if type(b.get(name)) is dict else {}
        builtin[name] = {"hidden": _flag(s.get("hidden"), False), "outline": s["outline"] if s.get("outline") in OUTLINES else ""}
    per_row = int(v.get("per_row")) if type(v.get("per_row")) in (int, float) and v.get("per_row") in PER_ROW else PER_ROW_DEFAULT      # a whole float (3.0) reads as the page reads it: 3
    return {"v": 1, "health": {"shown": _flag(h.get("shown"), True), "own_row": _flag(h.get("own_row"), False)}, "per_row": per_row,
            "order": _complete(v.get("order"), bespoke), "builtin": builtin, "bespoke": bespoke}


def _bool(d, key, default):
    got = d.get(key)
    if got is None:
        return default
    if type(got) is not bool:
        _no("not_bool")
    return got


def _text(d, key, most, too_long, required=False):
    got = d.get(key)
    if got is None:
        got = ""
    if not isinstance(got, str):
        _no("bad_text")
    got = got.strip()
    if required and not got:
        _no("label_missing")
    if len(got) > most:
        _no(too_long)
    return got


def check(value, rules):
    """The body rebuilt field by field, defaults left out, or Bad in plain words that never quote it."""
    if not isinstance(value, dict) or value.get("v") != 1:
        _no("not_object")
    if any(k not in KEYS for k in value):
        _no("unknown_field")
    out = {"v": 1}
    h = value.get("health")
    if h is not None:
        if type(h) is not dict:
            _no("not_object")
        if any(k not in ("shown", "own_row") for k in h):
            _no("unknown_field")
        health = {}
        if not _bool(h, "shown", True):
            health["shown"] = False
        if _bool(h, "own_row", False):
            health["own_row"] = True
        if health:
            out["health"] = health
    per_row = value.get("per_row")
    if per_row is not None:
        if type(per_row) is not int or per_row not in PER_ROW:
            _no("bad_per_row")
        if per_row != PER_ROW_DEFAULT:
            out["per_row"] = per_row
    bespoke = []
    raw = value.get("bespoke")
    if raw is not None:
        if not isinstance(raw, list):
            _no("not_object")
        if len(raw) > BESPOKE_MAX:
            _no("too_many")
        seen = set()
        for t in raw:
            if type(t) is not dict:
                _no("not_object")
            if any(k not in TILE_KEYS for k in t):
                _no("unknown_field")
            tid = t.get("id")
            if not isinstance(tid, str) or not ID.match(tid) or tid in BUILT_IN:
                _no("bad_id")
            if tid in seen:
                _no("dup_id")
            seen.add(tid)
            tone = t.get("tone")
            if tone is not None and tone not in TONES:
                _no("bad_tone")
            tile = {"id": tid, "label": _text(t, "label", LABEL_MAX, "label_long", required=True)}
            for k, most in (("figure", FIGURE_MAX), ("tag", TAG_MAX), ("note", NOTE_MAX)):
                got = _text(t, k, most, k + "_long")
                if got:
                    tile[k] = got
            if any(not rules.visible(tile[k]) for k in tile if k != "id"):
                _no("bad_text")
            if tone not in (None, "neutral"):
                tile["tone"] = tone
            if _bool(t, "hidden", False):
                tile["hidden"] = True
            bespoke.append(tile)
        if bespoke:
            out["bespoke"] = bespoke
    built = value.get("builtin")
    if built is not None:
        if type(built) is not dict:
            _no("not_object")
        if any(k not in SETTLED for k in built):
            _no("unknown_field")
        kept = {}
        for name in SETTLED:
            s = built.get(name)
            if s is None:
                continue
            if type(s) is not dict:
                _no("not_object")
            if any(k not in ("hidden", "outline") for k in s):
                _no("unknown_field")
            one = {}
            if _bool(s, "hidden", False):
                one["hidden"] = True
            outline = s.get("outline")
            if outline not in (None, "") :
                if outline not in OUTLINES:
                    _no("bad_outline")
                one["outline"] = outline
            if one:
                kept[name] = one
        if kept:
            out["builtin"] = kept
    order = value.get("order")
    if order is not None:
        ids = _default_order(bespoke)
        if not isinstance(order, list) or any(not isinstance(i, str) or i not in ids for i in order) or len(set(order)) != len(order):
            _no("bad_order")
        full = _complete(order, bespoke)
        if full != ids:
            out["order"] = full
    if len(str(out).encode("utf-8")) > LIMIT:
        _no("too_long")
    return out


KIND_OF_TILE = {"overdue": "actions", "risks": "raid", "decisions": "decisions"}     # the rows each built-in count reads (ctx.rows keys)


def _counts(u, ctx):
    """The three built-in tiles as the At a glance tiles work them out (glance.tiles, the one code), from ctx.rows only: the rows
    publish kept, so a hidden section (its kind has no rows here), a client-hidden, Sensitive, archived or eye-hidden row is never counted
    and never named in a detail. A tile is left out when its eye is off or when its kind has no kept row (a hidden section, or none).
    Returns [{tile, title, value, detail, rag}] in the template's order, outline applied. Nothing else of a row is copied."""
    glance = __import__("clark.glance", fromlist=["tiles"])      # at call time: publish has loaded it; a load-time import would loop (as figures4)
    rows = ctx.rows if ctx is not None and isinstance(getattr(ctx, "rows", None), dict) else {}
    as_at = getattr(ctx, "as_at", None)
    if not isinstance(as_at, str) or not as_at:
        return []
    by_kind = {k: [r for r in (rows.get(k) or []) if type(r) is dict] for k in ("actions", "raid", "decisions")}
    off = {n for n in SETTLED if u["builtin"][n]["hidden"]} | {n for n in SETTLED if not by_kind[KIND_OF_TILE[n]]}
    kept = {"rows": glance.work_rows(by_kind), "hidden_types": set()}      # nothing is hidden here: a hidden section has no rows in ctx
    outlines = {n: u["builtin"][n]["outline"] for n in SETTLED}
    shown = glance.tiles({"project": {}}, as_at, tile_order=[i for i in u["order"] if i in SETTLED], hidden=off, outlines=outlines,
                         for_client=True, kept=kept)
    return [{"tile": t["tile"], "title": t["title"], "value": t["value"], "detail": t["detail"], "rag": t["class"]}
            for t in shown if t["tile"] in SETTLED]


def published(value, ctx):
    """What the file carries: {"content": {health, order, builtin, bespoke}}, or None when there is no body or no bespoke tile is left to
    show. (A section with no own tile, no count and the health eye off has nothing to draw.) A hidden bespoke tile is left out whole (its words and its id),
    and so is its place in the order. Picked by name from the read body, never passed through. The three built-in figures are "counts", worked out
    here from ctx.rows (see _counts), never from stored text."""
    if not value:
        return None
    u = upgrade(value)
    shown = [t for t in u["bespoke"] if not t["hidden"]]
    counts = _counts(u, ctx)
    if not shown and not counts and not u["health"]["shown"]:      # the health eye alone still prints its row, as the View shows it
        return None
    gone = {t["id"] for t in u["bespoke"] if t["hidden"]}
    content = {"health": dict(u["health"]), "per_row": u["per_row"], "order": [i for i in u["order"] if i not in gone],
               "builtin": {n: dict(u["builtin"][n]) for n in SETTLED},
               "bespoke": [{k: t[k] for k in ("id", "label", "figure", "tag", "note", "tone")} for t in shown]}
    if counts:
        content["counts"] = counts
    return {"content": content}
