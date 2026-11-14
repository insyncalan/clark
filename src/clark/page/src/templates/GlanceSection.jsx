// The At a glance section as a template part (row 1190), store type "glance": the same Glance the built-in drew, reached through
// templateFor instead of a branch in Section.jsx. Tiles and health stay the project's (glance_tiles, projects), so nothing in the
// store, Word, Excel or the published file changes.
import { Glance } from "../components/Glance.jsx";
import { fromFile } from "../stores/report.js";

export const READY = true;
export function View({ clean }) { return <Glance tools={null} clean={clean} />; }
// A published file draws the section only when it carries tiles; the served View always draws it (as the built-in did).
export function isEmpty(section, data) {
  return fromFile.value ? !(data && data.glance && data.glance.tiles && data.glance.tiles.length) : false;
}
