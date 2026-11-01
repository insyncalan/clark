"""The contract every section template's content module keeps (#96). Pure: it reads no file and no database and imports nothing
from clark, so section_bodies.py (and through it store.py and publish.py) can import the registry without a loop.

A template module in this folder (one per store type, named after it) offers exactly:
- READY: False while it is a stub. A builder sets it True when the template is built; the page's catalogue entry
  (page/src/logic/templates.js, `ready`) may be switched on only then (tests/test_section_registry.py checks it).
- LIMIT: the most bytes the stored text may take. A type saved through /api/change must fit that route's limit.
- EMPTY: the body a new section of this type starts with ('' is no content). Chosen by the store, never by the request.
- check(value, rules) -> value: given the content already through the generic check (section_bodies._generic: one JSON object
  or list, plain text, whole numbers, no repeated key, not too deep), return it rebuilt field by field, or raise Bad in plain
  words that never quote the value. `rules.plain(text)` and `rules.visible(text)` are the store's text rules.
- published(value, ctx) -> dict | None: what the published file carries of a checked body, as fields picked by name, merged
  into the section's entry; None (or an empty dict) leaves the section out (an empty template stays out of the file). `ctx` is what publish has
  already kept (see Context): a live part may only use ids found there, so a hidden or archived item can never publish.
"""


class Bad(ValueError):
    """The content can't be saved. The message is plain words for a person and never quotes the value."""


class Context:
    """What publish.select already kept, handed to published(): `rows[kind]` the published rows of each kind (milestones,
    actions, raid, decisions, use_cases), fields as the file carries them (milestones with their state); `ids[kind]` the set of
    their ids; `as_at` the report's day (YYYY-MM-DD). Copies: a template can't change what publish writes elsewhere."""

    __slots__ = ("rows", "ids", "as_at")

    def __init__(self, rows=None, as_at=None):
        self.rows = {k: [dict(r) for r in v] for k, v in (rows or {}).items()}
        self.ids = {k: frozenset(r.get("id") for r in v) for k, v in self.rows.items()}
        self.as_at = as_at


STUB_LIMIT = 65536                  # a stub's limit until its builder sets the real one


def stub_check(value, rules):
    """A stub's checker: what passed the generic check, unchanged. Its builder replaces it."""
    return value


def stub_published(value, ctx):
    """A stub is never in a published file, whatever its body holds."""
    return None
