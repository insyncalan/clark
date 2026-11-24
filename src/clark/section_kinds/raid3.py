"""RAID cards, three (F8, #96): the content of a section of type 'raid3', three cards across. Each card points at one work item
(a risk or issue, an action or a decision) by its id and says where the words under it come from. raid4.py is the same with four.

The content: {"v": 1, "cards": [{"id": "ABC-001", "source": "client" | "own" | "latest", "own": "words"}, ...]}.
- id: a risk or issue (ABC-001), an action (ABC-A-001) or a decision (ABC-D-001). A card holds the id only, never a copy of the
  item's words, so what the item says is read when the page is drawn or published.
- source: "client" is the item's client wording, "own" is the card's own words, "latest" is an action's latest update. A risk,
  issue or decision has no latest update (the record keeps one for actions only), so "latest" is refused on those and the page
  does not offer it there.
- own: the card's own words, plain text on one line, at most OWN_MAX characters; only the "own" source reads it.
The published file carries, for each card whose item the file already holds, the id and the words chosen, and nothing else (the
item's own fields are in the file's data, which publish has already cleaned). A card whose item is hidden, archived, not client
visible or sensitive is left out, never shown blank; a section with no card left stays out of the file.
"""
from clark.section_kinds.base import Bad

READY = True
SIZE = 3                                   # cards across; raid4.py sets four
OWN_MAX = 400                              # characters of a card's own words
CARD_BYTES = 6 * OWN_MAX + 100             # worst case: every character escaped to six bytes, plus the id and the keys
LIMIT = 4 * CARD_BYTES + 64                # raid4 holds four cards; one limit for both, well inside the route's
EMPTY = ""

UPPER, DIGITS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "0123456789"
SOURCES = ("client", "own", "latest")
KIND_OF = {None: "raid", "A": "actions", "D": "decisions"}

NOT_AN_OBJECT = "That content isn't a set of cards."
TOO_MANY = "A card row holds {n} cards at most."
BAD_CARD = "A card needs the number of a risk, issue, action or decision."
BAD_SOURCE = "Choose Client wording, Own words or Latest update for a card."
NO_LATEST = "Only an action has a latest update. Choose Client wording or Own words for this card."
TWICE = "The same item is on two cards."
OWN_LONG = "A card's own words can be {n} characters at most."
OWN_BAD = "A card's own words can only be plain text on one line."


def _id(item):
    """(True, letter) for an item number: a risk or issue ABC-001 (letter None), an action ABC-A-001 or a decision ABC-D-001; the
    project code is 3 to 7 capitals or digits starting with a capital, the number three digits. (False, None) for anything else."""
    parts = item.split("-") if isinstance(item, str) else []
    if len(parts) not in (2, 3):
        return False, None
    code, number = parts[0], parts[-1]
    letter = parts[1] if len(parts) == 3 else None
    ok = (3 <= len(code) <= 7 and code[0] in UPPER and all(c in UPPER + DIGITS for c in code)
          and len(number) == 3 and all(c in DIGITS for c in number) and letter in (None, "A", "D"))
    return (True, letter) if ok else (False, None)


def _check(value, rules, size):
    if type(value) is not dict or set(value) - {"v", "cards"} or value.get("v") != 1 or type(value.get("cards")) is not list:
        raise Bad(NOT_AN_OBJECT)
    if len(value["cards"]) > size:
        raise Bad(TOO_MANY.format(n=size))
    out, seen = [], set()
    for card in value["cards"]:
        if type(card) is not dict or set(card) - {"id", "source", "own"}:
            raise Bad(BAD_CARD)
        item = card.get("id")
        found, letter = _id(item)
        if not found:
            raise Bad(BAD_CARD)
        if item in seen:
            raise Bad(TWICE)
        seen.add(item)
        source = card.get("source", "client")
        if source not in SOURCES:
            raise Bad(BAD_SOURCE)
        if source == "latest" and letter != "A":
            raise Bad(NO_LATEST)
        own = card.get("own", "")
        if type(own) is not str:
            raise Bad(OWN_BAD)
        own = " ".join(own.split())
        if len(own) > OWN_MAX:
            raise Bad(OWN_LONG.format(n=OWN_MAX))
        if own and not rules.visible(own):
            raise Bad(OWN_BAD)
        built = {"id": item, "source": source}
        if own:
            built["own"] = own
        out.append(built)
    return {"v": 1, "cards": out}


def _words(card, row):
    """The words under a card: the item's client wording, the card's own words, or an action's latest update."""
    source = card.get("source")
    if source == "own":
        return card.get("own") or ""
    if source == "latest":
        return str(row.get("latest_update") or "").strip()
    return str(row.get("client_message") or "").strip()


def _published(value, ctx, size):
    out = []
    for card in (value or {}).get("cards") or ():
        found, letter = _id(card.get("id"))
        kind = KIND_OF[letter] if found else ""
        row = next((r for r in ctx.rows.get(kind, ()) if r.get("id") == card.get("id")), None)
        if row is None:
            continue                       # not kept by publish: hidden, archived, not client visible, sensitive, or a hidden section
        out.append({"id": card["id"], "text": _words(card, row)})
    return {"cards": out[:size]} if out else None


def check(value, rules):
    return _check(value, rules, SIZE)


def published(value, ctx):
    return _published(value, ctx, SIZE)
