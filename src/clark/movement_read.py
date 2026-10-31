"""The one function behind GET /api/movement (#136): the store's Movement read, cut down by the pure view (owner only).

The server imports nothing from clark, so this is the seam it is given (as `data_for` and `publisher`). It reads the milestone rows
and the history through two methods it is handed, runs movement_view over them and returns what the page draws, or None when
the project isn't there. No publishing module uses it. Standard library only, Python 3.9."""
from datetime import date

from clark import movement_view


def today_text():
    """Today as YYYY-MM-DD on this machine's clock (the slip is counted from it); a test passes its own."""
    return date.today().isoformat()


def make_read(milestone_moves, data_for, today=today_text):
    """`read(code)` for the server: milestone_moves(code) is Store.milestone_moves, data_for(code) is Store.data_for (its milestone
    rows). The reply is movement_view.view's: only its own keys, no raw event, no internal note."""
    def read(code):
        reply = milestone_moves(code)
        data = data_for(code) if reply is not None else None
        if data is None:
            return None
        return movement_view.view(data["milestones"], reply, today())
    return read
