// Glance template (row 1264, slice 1), store type "glancetemplate": its view part, a plain placeholder until the View slice. It draws the
// bespoke tiles that are not hidden as text nodes (label, figure, tag, note) and nothing else: no words of its own are shown, no count (counts come with the next slice), no style. isEmpty: no bespoke tile is left to show, so the
// section is left out of the served View and the published file alike. The same reading as section_kinds/glancetemplate.py upgrade and
// published (a hidden tile and a tile with no label are left out). Its Edit part is edit/templates/GlanceTemplate.jsx.
import { source } from "./notes.js";

export const READY = true;
const text = (v) => (typeof v === "string" ? v.trim() : "");

// The bespoke tiles to show, in the order the section keeps.
export function shownTiles(section) {
  const v = source(section);
  const tiles = (Array.isArray(v.bespoke) ? v.bespoke : []).filter((t) => t && typeof t === "object" && typeof t.id === "string" && text(t.label) && t.hidden !== true);
  const rank = (t) => { const at = Array.isArray(v.order) ? v.order.indexOf(t.id) : -1; return at < 0 ? 1e6 : at; };
  return tiles.map((t, i) => [t, i]).sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1]).map((p) => p[0]);
}
export const isEmpty = (section) => shownTiles(section).length === 0;

export function View({ section }) {
  const tiles = shownTiles(section);
  if (!tiles.length) return null;
  return (
    <div class="tpl-gt">
      {tiles.map((t) => (
        <div key={t.id} class="tpl-gt-tile">
          <p>{text(t.label)}</p>
          {text(t.figure) ? <p>{text(t.figure)}</p> : null}
          {text(t.tag) ? <p>{text(t.tag)}</p> : null}
          {text(t.note) ? <p>{text(t.note)}</p> : null}
        </div>
      ))}
    </div>
  );
}
