"""Row 512: the Docker starter's check, run on the Mac BEFORE the container starts (docker/start.command calls it).

Inside the container OneDrive cannot be seen, so platform.container_host_in_onedrive reads a name there. Here, on the Mac, a link is
followed first (resolve), then the folder names are read: OneDrive, Dropbox, iCloud Drive (Mobile Documents) and Google Drive copy
files while they are written, which damages the database. Like the container's check this reads names, not the disk, so a harmless
folder named like a service is refused (safe). The words are platform.check_data_dir's own for OneDrive; the others name the service.
Run: python3 src/clark/starter_check.py [--env-file docker/.env] [folder]   (exit 0: allowed; exit 1: the refusal on stderr). Standard library only."""
import os
import re
import sys
from pathlib import Path


def _from_env_file(env_file):
    """CLARK_DATA_DIR as docker/.env gives it (compose reads that file when the shell does not set the name), or ""."""
    try:
        with open(env_file, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except (OSError, TypeError, ValueError):
        return ""
    value = ""
    for line in lines:
        name, sep, rest = line.strip().partition("=")
        if sep and name.strip() == "CLARK_DATA_DIR":
            value = rest.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
    return value


def data_folder(environ=None, env_file=None):
    """The folder docker/compose.yaml shares in as the data folder: CLARK_DATA_DIR from the shell, else from docker/.env (`env_file`),
    else ~/Library/Application Support/clark. A name set in the shell, even empty, is not looked for in the file (compose's order)."""
    environ = os.environ if environ is None else environ
    value = environ["CLARK_DATA_DIR"] if "CLARK_DATA_DIR" in environ else _from_env_file(env_file)
    return value or str(Path(environ.get("HOME") or Path.home()) / "Library" / "Application Support" / "clark")


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
            shown = re.sub(r"(?i)(?<![^\\/])(onedrive)\s*-\s*(?!\s*personal(?:[\\/]|$))[^\\/]*", r"\1", str(path)) if service == "OneDrive" else path   # the tenant folder is the company: not said
            return (f"Your data can't be kept in {shown} because it is inside {service}. {service} copies files while they are "
                    f"being written, which damages the database. Choose a folder on this computer that {service} doesn't sync.")
    return None


def main(argv=None, environ=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    env_file = None
    if argv[:1] == ["--env-file"] and len(argv) >= 2:
        env_file, argv = argv[1], argv[2:]
    text = refusal(argv[0] if argv else data_folder(environ, env_file))
    if text:
        print(text, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
