// Glance template (row 1264, slice 4), store type "glancetemplate": its Edit part for the built-in tiles (Project health, Overdue actions,
// High risks and issues, Decisions needed). Each tile has a grip (drag, or Alt with the arrows), an eye (hide it from the published
// report) and, but for Project health, a right-click menu for its outline colour; Project health keeps its pill and reason box. The
// controls are the At a glance ones (edit/GlanceEdit.jsx); only where they save differs: the section's own body (templates/glanceBody.js),
// one change() each, so one step and one Undo. A change that leaves the body as it was sends nothing. The words are the At a glance
// words (the existing toasts). Slice 6 adds the tiles the person types: Add a tile, the pencil and the bin on each, the editor in the page
// and its five colours (edit/templates/glanceTileEditor.jsx), in the order the body keeps. View part: templates/GlanceTemplate.jsx.
import { change } from "../../stores/changes.js";
import { data, rows } from "../../stores/report.js";
import { todayIso } from "../../workItems.js";
import { TILE_TITLES, OUTLINE_CHOICES, stepTile } from "../../glanceTiles.js";
import { Figure, Health } from "../../components/Glance.jsx";
import { GLANCE } from "../GlanceEdit.jsx";
import { note } from "../notes.js";
import { readBody, compact, withChange, moved, builtinTiles } from "../../templates/glanceBody.js";
import { tileActions, OwnControls, OwnTile, PendingCell, AddTile, editor } from "./glanceTileEditor.jsx";

const focusLater = (key, part) => setTimeout(() => { const el = document.querySelector(`[data-tile="${key}"] ${part}`); if (el) el.focus(); }, 0);
const keepFocus = (done, key, part) => Promise.resolve(done).then((r) => { focusLater(key, part); return r; });

// What the tiles' controls ask of clark for this section. `u` is the body as drawn now.
function actions(section, u, own) {
  const send = (next, words, key, part) => {
    if (JSON.stringify(compact(next)) === JSON.stringify(compact(u))) return Promise.resolve(null);       // nothing changed: no step
    return keepFocus(change({ op: "update", id: section.id, changes: { body: JSON.stringify(compact(next)) }, place: "report" }, words), key, part);
  };
  const drawn = u.order.slice();                   // every id the page draws: the built-in tiles and the tiles typed
  const titleOf = (key) => TILE_TITLES[key] || (u.bespoke.find((t) => t.id === key) || {}).label || key;
  const move = (key, before, order) => {
    const at = order.indexOf(key);
    if (before === key || (before === null ? at === order.length - 1 : order[at + 1] === before)) return Promise.resolve(null);
    return send(withChange(u, { order: moved(u.order, key, before, drawn) }), `${titleOf(key)} moved.`, key, "[data-tile-grip]");
  };
  return {
    hide: (key, hidden) => send(withChange(u, { hide: [key, hidden] }), hidden ? `${titleOf(key)} hidden from the published report.` : `${titleOf(key)} shown in the published report.`, key, "[data-tile-eye]"),
    outline: (key, outline) => {
      if (!(key in TILE_TITLES)) return Promise.resolve(null);
      const name = (OUTLINE_CHOICES.find((c) => c[0] === outline) || [0, ""])[1].toLowerCase();
      return send(withChange(u, { outline: [key, outline] }), outline ? `${TILE_TITLES[key]} outline: ${name}.` : `${TILE_TITLES[key]} outline: automatic.`, key, "[data-tile-grip]");
    },
    move,
    step: (key, dir, order) => {
      const s = stepTile(order, key, dir);
      if (!s) { note(`${titleOf(key)} is already ${dir < 0 ? "first" : "last"}.`); return Promise.resolve(null); }
      return move(key, s.before, order);
    },
    outlines: (key) => key !== "health" && key in TILE_TITLES,       // the body keeps an outline for the three counting tiles only
    extra: (tile, title) => (tile.own ? <OwnControls tile={tile} title={title} tools={own} /> : null),
    eye: () => true,                            // Project health has its eye here: the body keeps health.shown
  };
}

export function Edit({ section }) {
  const u = readBody(section), d = data.value;
  const built = Object.fromEntries(builtinTiles(u, rows.value, todayIso(), d.project).map((t) => [t.key, t]));
  const typed = Object.fromEntries(u.bespoke.map((t) => [t.id, { ...t, key: t.id, own: true, hidden: t.hidden === true }]));
  const list = u.order.map((k) => built[k] || typed[k]).filter(Boolean), order = list.map((t) => t.key), Cell = GLANCE.Cell;
  const own = { ...tileActions(section, u), sid: section.id }, act = actions(section, u, own), shown = editor.value;
  return (
    <div class="tpl-edit tpl-edit-glancetemplate" data-tpl="glancetemplate">
      <div class="glance" data-glance-template>
        {list.map((t, i) => (
          <Cell key={t.key} tile={t} order={order} index={i} act={act}>
            {t.own ? <OwnTile t={shown && shown.id === t.key && shown.sid === section.id ? shown.draft : t} /> : t.key === "health" ? <Health t={{ ...t, pill: ({ "On track": "g", "At risk": "a", "Off track": "r" })[d.project.health] || "n" }} tools={{ glance: GLANCE }} editing={true} clean={null} /> : <Figure t={t} file={false} />}
          </Cell>
        ))}
        <PendingCell tools={own} />
      </div>
      <AddTile tools={own} count={u.bespoke.length} />
      <GLANCE.Hint />
    </div>
  );
}
