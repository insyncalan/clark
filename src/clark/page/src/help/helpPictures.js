// The Help pictures, inlined into the editing page at build time (dev/tools/build_page.py, help_pictures_path): the server has no
// route for files, so each picture is a data: URI in the page itself. Edit-served pages only; the published page's build maps
// "clark-help-pictures" to an empty object, so it holds none. The guides draw a step's picture with pictureUrl(id).
import PICTURES from "clark-help-pictures";

/** The data: URI of the picture with this shot id (an id in dev/tools/help_shots.json), or null for any other id. */
export function pictureUrl(id) {
  return typeof id === "string" && Object.prototype.hasOwnProperty.call(PICTURES, id) ? PICTURES[id] : null;
}
