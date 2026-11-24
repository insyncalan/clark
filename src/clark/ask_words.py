"""Row 1293 rulings: every NEW sentence ask clark says for the second change, the duplicate warning, the Used
line notes and the Docker refusal, in one place (so the words can be logged and approved together). Plain data and functions; it
imports nothing from clark, so any ask module may use it. The page shows these sentences as the server sends them."""

ROW_CUT_AT = 4000          # the length a row line is cut at (ask.MAX_PASSAGE)
REPLY_CUT_AT = 60000       # the length a reply is cut at (ask.MAX_REPLY)
SENT_SHOWN_ABOVE = 20000   # the size sent is said only above this many characters

# The plain name of a changed column, for the second-change line.
FIELD_NAMES = {"description": "title", "decision": "title", "name": "title", "due_date": "due date", "made_by": "owner",
               "baseline_date": "agreed date", "forecast_date": "forecast date", "actual_date": "achieved date",
               "needed_by": "needed by", "headline": "headline", "standing": "where it stands"}


def field_name(column):
    """The plain words for a column of the saved data."""
    return FIELD_NAMES.get(column) or str(column).replace("_", " ")


def stale(column):
    """(a) The second change to one item, when the first has been saved. Shown on the second card in place of its Apply."""
    return f"This one was not saved: {field_name(column)} changed when the first change was saved. Ask again to change it."


def duplicate(kind, title):
    """(b) A new item that matches one already there. Shown on the card above Apply; never blocks."""
    article = "an" if kind[:1].lower() in "aeiou" else "a"
    return f'There is already {article} {kind} called "{title}". Apply to add another.'


LONG_ROWS = f"Some long rows were cut at {ROW_CUT_AT:,} characters."
REPLY_CUT = f"The answer was cut at {REPLY_CUT_AT:,} characters."
SECRET_LEFT_OUT = "One passage was left out because it looked like a password or key."
READ_LEFT_OUT = "{n} {items} read, {m} left out. A higher size of one question in Settings reads more."      # Row 1293 (approved 22-11 16:25; singular only when N is 1)
DOCKER = "Ask clark is not available in the Docker version of clark."


def sent_about(characters):
    """The size sent, only above SENT_SHOWN_ABOVE characters, rounded to the thousand; "" otherwise."""
    if not isinstance(characters, int) or isinstance(characters, bool) or characters <= SENT_SHOWN_ABOVE:
        return ""
    return f"Sent about {(characters + 500) // 1000 * 1000:,} characters."


def read_left_out(counts):
    """The line for `data.counts` ((kind, rows sent, rows in all) for each kind): "N items read, M left out. A higher size of one question
    in Settings reads more." Only when M is above 0 (a question that cut nothing says nothing); "" otherwise."""
    sent = sum(n for _k, n, _t in counts)
    left = sum(t - n for _k, n, t in counts if t > n)
    return READ_LEFT_OUT.format(n=f"{sent:,}", items="item" if sent == 1 else "items", m=f"{left:,}") if left > 0 else ""
