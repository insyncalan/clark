"""The commands clark's messages tell a person to type (issue 694).

In a download there is no `python3 -m clark` to type at the top of the folder: clark.command forwards everything, and it sets
CLARK_TYPED before it runs anything. When CLARK_TYPED is set the messages say `bash clark.command ...`; in a source checkout
(nothing sets it) they say what they always said, `python3 -m clark ...`. The environment is read at each call, never at import.
Standard library only.
"""
import os


def _set():
    return bool(os.environ.get("CLARK_TYPED"))


def clark(rest=""):
    """The command that starts clark (or runs `restore`), with `rest` after it."""
    head = "bash clark.command" if _set() else "python3 -m clark"
    return f"{head} {rest}" if rest else head


def doctor():
    """The command that checks what this computer needs."""
    return "bash clark.command --check" if _set() else "python3 -m clark.doctor"


def launch():
    """The command that starts clark and opens its window (clark.command's normal start, `python3 -m clark.launch` in a checkout)."""
    return "bash clark.command" if _set() else "python3 -m clark.launch"
