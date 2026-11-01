"""Contacts (H4, #96): the content of a section of type 'contacts': a few people to reach. READY.

Stored (canonical JSON): {"v": 1, "people": [{"name", "role", "email", "phone"}, ...]}. Typed only: a person here is not a record
in clark, so nothing is looked up and nothing hidden can leak. A person with no details at all is dropped; a person with
details but no name is refused. An email is one address with an @ and no spaces; a phone is digits and the usual marks.
The page makes the email a mailto: link (the shared safe check). A section with no people is empty and stays out of the file.
"""
from clark.section_kinds.base import Bad

READY = True
LIMIT = 16384
EMPTY = ""

PEOPLE_MAX, NAME_MAX, ROLE_MAX, EMAIL_MAX, PHONE_MAX = 8, 80, 80, 120, 40
FIELDS = ("name", "role", "email", "phone")

NOT_OBJECT = "Contacts must be one set of fields. Check it and try again."
BAD_FIELD = "A contact field has the wrong kind of value. Check it and try again."
TOO_MANY = f"A contacts section can have {PEOPLE_MAX} people at most. Remove one and try again."
NO_NAME = "Give each contact a name. A contact with details but no name can't be saved."
TOO_LONG = "A contact's name or role can be 80 characters at most, an email 120 and a phone number 40. Shorten it and try again."
BAD_EMAIL = "That email address isn't one address. Use a form like name@example.org."
BAD_PHONE = "A phone number can have digits, spaces and + ( ) - . only."

_EMAIL_NO = set(" \t<>\"',;:()[]\\")      # characters that are never in one plain address
_PHONE_OK = set("0123456789+()-. ")


def _is_email(text):
    """One address: a name, one @, a host with a dot inside it, none of the characters that split or quote an address."""
    name, at, host = text.partition("@")
    return bool(at and name and "@" not in host and not (set(text) & _EMAIL_NO)
                and "." in host and not host.startswith(".") and not host.endswith("."))


def _text(value, most):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise Bad(BAD_FIELD)
    value = value.strip()
    if len(value) > most:
        raise Bad(TOO_LONG)
    return value


def check(value, rules):
    """The people rebuilt field by field, or Bad in plain words that never quote them."""
    if not isinstance(value, dict) or value.get("v") != 1:
        raise Bad(NOT_OBJECT)
    raw = value.get("people", [])
    if raw is None:
        raw = []
    if type(raw) is not list:
        raise Bad(BAD_FIELD)
    people = []
    for p in raw:
        if type(p) is not dict:
            raise Bad(BAD_FIELD)
        row = {f: _text(p.get(f), {"name": NAME_MAX, "role": ROLE_MAX, "email": EMAIL_MAX, "phone": PHONE_MAX}[f]) for f in FIELDS}
        if not any(row.values()):
            continue
        if not row["name"]:
            raise Bad(NO_NAME)
        if row["email"] and not _is_email(row["email"]):
            raise Bad(BAD_EMAIL)
        if row["phone"] and not set(row["phone"]) <= _PHONE_OK:
            raise Bad(BAD_PHONE)
        people.append(row)
    if len(people) > PEOPLE_MAX:
        raise Bad(TOO_MANY)
    return {"v": 1, "people": people}


def published(value, ctx):
    """{"content": {people}}, or None when there is no one to show."""
    people = [{f: p.get(f, "") for f in FIELDS} for p in value.get("people", ()) if p.get("name")]
    return {"content": {"people": people}} if people else None
