"""Row 836 step 6: is the data folder a person chose inside a synced cloud folder (Dropbox, iCloud Drive, Google Drive)?

Pure: the answer is read from the text of the path, never from the disk, so a Mac path and a Windows path (a drive letter, either
slash, a network share) are judged the same way on any system, and letter case is ignored. A link is NOT followed here: a caller that
has a real folder resolves it first. The folder names are starter_check's (one list of names), with the Windows names added; OneDrive is
not here, it has its own check (platform.inside_onedrive). The words are starter_check's refusal, so nothing new is said.
Standard library only."""
import re
from pathlib import Path

from clark.starter_check import _service

_SPLIT = re.compile(r"[\\/]+")
_WINDOWS_ICLOUD = ("iclouddrive", "icloud drive")            # the iCloud for Windows folder in the user's profile


def cloud_service(path):
    """"Dropbox", "iCloud Drive" or "Google Drive" if `path` is inside that service's folder, else None (also for anything that is not text)."""
    if isinstance(path, Path):
        path = str(path)
    if not isinstance(path, str):
        return None
    for part in _SPLIT.split(path):
        service = _service(part)
        if service and service != "OneDrive":
            return service
        if part.casefold() in _WINDOWS_ICLOUD:
            return "iCloud Drive"
    return None


def cloud_warning(path, shown=None):
    """None if `path` is not inside a synced folder; else the sentence that says why not. `shown` is the way to write the path for a
    person (platform.shown), `path` itself if not given."""
    service = cloud_service(path)
    if service is None:
        return None
    return (f"Your data can't be kept in {shown or path} because it is inside {service}. {service} copies files while they are "
            f"being written, which damages the database. Choose a folder on this computer that {service} doesn't sync.")
