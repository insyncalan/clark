"""ask: the Mac's text recognition for pictures (#1366 follow-up). Standard library only. NOT RUN ON A MAC by its author: the tests here
use a stand-in for the system's script runner; dev/tools/check_picture_reader_mac.py is the check to run on a Mac.

The picture is read on THIS Mac only and is never sent anywhere: the Vision framework that ships with macOS does the reading, in the
system's own osascript (JavaScript for Automation), started by platform.run_jxa from an argument list (no shell). No network, no library,
no program is added. The picture goes to a private temporary file whose path is the script's one argument; the file is deleted after
every read, whatever happens. Recognition level accurate, the system's default languages. A run is limited to TIMEOUT seconds and a
picture to MAX_BYTES; anything that fails, times out or finds no text raises ask_picture.PictureUnreadable.
"""
import os
import tempfile

from clark import ask_picture, platform

MAX_BYTES = ask_picture.MAX_PICTURE_BYTES
TIMEOUT = 30            # seconds for one picture

SCRIPT = """
ObjC.import('Foundation');
ObjC.import('Vision');
function run(argv) {
  var data = $.NSData.dataWithContentsOfFile(argv[0]);
  if (!data) { return ''; }
  var request = $.VNRecognizeTextRequest.alloc.init;
  request.recognitionLevel = $.VNRequestTextRecognitionLevelAccurate;
  var handler = $.VNImageRequestHandler.alloc.initWithDataOptions(data, $.NSDictionary.dictionary);
  var ok = handler.performRequestsError($([request]), null);
  if (!ok) { return ''; }
  var found = request.results;
  var lines = [];
  for (var i = 0; i < found.count; i++) {
    var top = found.objectAtIndex(i).topCandidates(1);
    if (top.count > 0) { lines.push(ObjC.unwrap(top.objectAtIndex(0).string)); }
  }
  return lines.join('\\n');
}
"""


def read(raw, run=None):
    """The text lines in the picture `raw` (bytes), joined by newline. Raises PictureUnreadable when there is none, the picture is
    too big or not a picture, or the Mac's reader fails or runs out of time. `run` replaces subprocess.run (tests)."""
    if not isinstance(raw, (bytes, bytearray)) or not raw or len(raw) > MAX_BYTES:
        raise ask_picture.PictureUnreadable("size")
    if run is None and os.environ.get("CLARK_TEST") == "1":     # under the tests (tests/_paths.py) the real osascript is never reached by accident
        raise ask_picture.PictureUnreadable("the reader is not run under the tests")
    try:
        fd, name = tempfile.mkstemp(prefix="clark-picture-")    # private (mode 0600) file in the system's temporary folder
    except OSError:
        raise ask_picture.PictureUnreadable("no temporary file") from None
    try:
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
        except OSError:
            raise ask_picture.PictureUnreadable("no temporary file") from None
        try:
            out = platform.run_jxa(SCRIPT, [name], TIMEOUT, run=run)
        except (platform.PlatformError, platform.NotBuiltYet):
            raise ask_picture.PictureUnreadable("the reader failed") from None
    finally:
        try:
            os.unlink(name)
        except OSError:
            pass
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if not lines:
        raise ask_picture.PictureUnreadable("no text")
    return "\n".join(lines)


def register():
    """Make `read` the picture reader, on a Mac only (anywhere else nothing is registered)."""
    if platform.system() == platform.MAC:
        ask_picture.set_reader(read)
