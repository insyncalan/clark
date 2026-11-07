"""Row 512: the Docker starter's check, run on the Mac BEFORE the container starts (docker/start.command calls it).

Inside the container OneDrive cannot be seen, so platform.container_host_in_onedrive reads a name there. Here, on the Mac, a link is
followed first (resolve), then the folder names are read: OneDrive, Dropbox, iCloud Drive (Mobile Documents) and Google Drive copy
files while they are written, which damages the database. Like the container's check this reads names, not the disk, so a harmless
folder named like a service is refused (safe). The words are platform.check_data_dir's own for OneDrive; the others name the service.
Run: python3 src/clark/starter_check.py [folder]   (exit 0: allowed; exit 1: the refusal on stderr). Standard library only."""
import os
import sys
from pathlib import Path


def data_folder(environ=None):
    """The folder docker/compose.yaml shares in as the data folder: CLARK_DATA_DIR, else ~/Library/Application Support/clark."""
    environ = os.environ if environ is None else environ
    return environ.get("CLARK_DATA_DIR") or str(Path(environ.get("HOME") or Path.home()) / "Library" / "Application Support" / "clark")


def _service(part):
    """The service a folder name belongs to, or None. `part` is one name of the path."""
    low = part.casefold()
    if low.startswith("onedrive"):
        return "OneDrive"
    if low == "dropbox" or low.startswith(("dropbox ", "dropbox-", "dropbox(")):
        return "Dropbox"
    if low == "mobile documents":
        return "iCloud Drive"
    if low.startswith("googledrive-") or low in ("google drive", "my drive"):
        return "Google Drive"
    return None


def refusal(path):
    """None if clark may keep its data in `path`; else the sentence that says why not. A link is followed first, and a folder
    that is not made yet is judged by the part of the path that exists."""
    resolved = Path(path).expanduser().resolve()
    for part in resolved.parts:
        service = _service(part)
        if service:
            tail = f" ({part})" if service == "OneDrive" else ""
            return (f"Your data can't be kept in {path} because it is inside {service}{tail}. {service} copies files while they are "
                    f"being written, which damages the database. Choose a folder on this computer that {service} doesn't sync.")
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    text = refusal(argv[0] if argv else data_folder())
    if text:
        print(text, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
