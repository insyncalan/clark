// Glance template (row 1264, slice 4), store type "glancetemplate": its Edit part for the built-in tiles (Project health, Overdue actions,
// High risks and issues, Decisions needed). Each tile has a grip (drag, or Alt with the arrows), an eye (hide it from the published
// report) and, but for Project health, a right-click menu for its outline colour; Project health keeps its pill and reason box. The
// controls are the At a glance ones (edit/GlanceEdit.jsx); only where they save differs: the section's own body (templates/glanceBody.js),
// one change() each, so one step and one Undo. A change that leaves the body as it was sends nothing. The words are the At a glance
// words (the existing toasts). Slice 6 adds the tiles the person types: Add a tile, the pencil and the bin on each, the editor in the page
// and its five colours (edit/templates/glanceTileEditor.jsx), in the order the body keeps. View part: templates/GlanceTemplate.jsx.
// Slice 9: the eye on Project health hides it completely and a button then brings it back; "Tiles on a line" (3 or 4) and the switch
// "Project health on its own row" sit under the tiles. Their words are the ruled ones (words file groups 2, 3, 10, 12, 13 and v2 A), in WORDS.
import { change } from "../../stores/changes.js";
import { data, rows } from "../../stores/report.js";
import { todayIso } from "../../workItems.js";
import { TILE_TITLES, OUTLINE_CHOICES, stepTile } from "../../glanceTiles.js";
import { Figure, Health } from "../../components/Glance.jsx";
import { GLANCE } from "../GlanceEdit.jsx";
import { note } from "../notes.js";
import { readBody, compact, withChange, moved, builtinTiles, PER_ROWS } from "../../templates/glanceBody.js";
import { drawnTiles, hiddenTiles } from "../../glanceHidden.js";
import { Icon } from "../../components/Icon.jsx";
import { classicTheme } from "../../components/Contents.jsx";
import { tileActions, OwnControls, OwnTile, PendingCell, AddTile, editor, WORDS as TILE_WORDS } from "./glanceTileEditor.jsx";

// The words of slice 9, quoted from the ruled words files (groups 2, 3, 10, 12, 13; v2 A). Nothing else is new here.
export const WORDS = {
  ownRow: "Project health on its own row", ownRowOn: "Project health sits on its own row", ownRowOff: "Project health sits with the tiles",       // group 2; v2 A
  showHealth: "Show project health here",                                                                                                    // group 3
  healthHidden: "Project health is hidden completely", healthShown: "Project health is shown",                                                // group 10
  hintEye: "The eye on Project health hides it completely.", hintAdd: "Use Add a tile to make your own. Click the pencil on your own tile to edit it.",   // group 12 (Cards keeps these)
  hint: "Drag a tile to move it, or hold Alt and press an arrow key. The eye hides a tile from the published page; the bin deletes it. Add a tile brings it back.",   // row 1336: the closing words are the ticket's: the bin deletes it
  perRow: "Tiles on a line", halfNote: "Half width always shows 2 on a line.",                                                               // group 13
};

const focusLater = (at) => setTimeout(() => { const el = document.querySelector(at); if (el) el.focus(); }, 0);
const keepFocus = (done, at) => Promise.resolve(done).then((r) => { focusLater(at); return r; });

// What the tiles' controls ask of clark for this section. `u` is the body as drawn now.
function actions(section, u, own) {
  const at = (part) => `[data-id="${section.id}"] ${part}`;
  const tile = (key, part) => at(`[data-tile="${key}"] ${part}`);
  // `where`: what takes the focus again once the page is drawn again. `named`: change()'s options ({silent: true}: no toast, the step is kept for Undo).
  const send = (next, words, where, named = null) => {
    if (JSON.stringify(compact(next)) === JSON.stringify(compact(u))) return Promise.resolve(null);       // nothing changed: no step
    return keepFocus(change({ op: "update", id: section.id, changes: { body: JSON.stringify(compact(next)) }, place: "report" }, words, named), where);
  };
  const drawn = u.order.filter((k) => k !== "health" || u.health.shown);      // every id the page draws: the built-in tiles (a health that is off is not one) and the tiles typed
  const titleOf = (key) => TILE_TITLES[key] || (u.bespoke.find((t) => t.id === key) || {}).label || key;
  const move = (key, before, order) => {
    const at = order.indexOf(key);
    if (before === key || (before === null ? at === order.length - 1 : order[at + 1] === before)) return Promise.resolve(null);
    return send(withChange(u, { order: moved(u.order, key, before, drawn) }), `${titleOf(key)} moved.`, tile(key, "[data-tile-grip]"));
  };
  const del = (key) => send(withChange(u, { hide: [key, true] }), `Removed: ${titleOf(key)}`, at(".tileadd"));      // row 1336: the bin on a built-in tile takes it off the strip with an Undo; the stored body is the hidden flag, so the published-file rule is the one it was (Add a tile brings it back)
  return {
    del,
    hide: (key, hidden) => send(withChange(u, { hide: [key, hidden] }),
      key === "health" ? (hidden ? WORDS.healthHidden : WORDS.healthShown) : hidden ? `${titleOf(key)} hidden from the published report.` : `${titleOf(key)} shown in the published report.`,
      key === "health" ? at(hidden ? "[data-gt-showhealth]" : "[data-tile=health] [data-tile-eye]") : tile(key, "[data-tile-eye]")),
    ownRow: (on) => send(withChange(u, { ownRow: on }), on ? WORDS.ownRowOn : WORDS.ownRowOff, at("[data-gt-own]")),
    perRow: (n) => send(withChange(u, { perRow: n }), "", at(`[data-gt-per="${n}"]`), { silent: true }),
    outline: (key, outline) => {
      if (!(key in TILE_TITLES)) return Promise.resolve(null);
      const name = (OUTLINE_CHOICES.find((c) => c[0] === outline) || [0, ""])[1].toLowerCase();
      return send(withChange(u, { outline: [key, outline] }), outline ? `${TILE_TITLES[key]} outline: ${name}.` : `${TILE_TITLES[key]} outline: automatic.`, tile(key, "[data-tile-grip]"));
    },
    move,
    step: (key, dir, order) => {
      const s = stepTile(order, key, dir);
      if (!s) { note(`${titleOf(key)} is already ${dir < 0 ? "first" : "last"}.`); return Promise.resolve(null); }
      return move(key, s.before, order);
    },
    outlines: (key) => key !== "health" && key in TILE_TITLES,       // the body keeps an outline for the three counting tiles only
    extra: (tile, title) => (tile.own ? <OwnControls tile={tile} title={title} tools={own} /> : tile.key === "health" || !classicTheme() ? null : (
      <button type="button" class="tdel" data-edit-only data-tile-bin aria-label={`Delete ${title}`} title={TILE_WORDS.deleteThis} onClick={() => del(tile.key)}><Icon name="trash" /></button>
    )),
    eye: () => true,                            // Project health has its eye here: the body keeps health.shown
  };
}

export function Edit({ section }) {
  const u = readBody(section), d = data.value;
  const built = Object.fromEntries(builtinTiles(u, rows.value, todayIso(), d.project).map((t) => [t.key, t]));
  const typed = Object.fromEntries(u.bespoke.map((t) => [t.id, { ...t, key: t.id, own: true, hidden: t.hidden === true }]));
  const every = u.order.filter((k) => k !== "health" || u.health.shown).map((k) => built[k] || typed[k]).filter(Boolean);
  const list = drawnTiles(every), away = hiddenTiles(every), order = list.map((t) => t.key), Cell = GLANCE.Cell;      // row 1303: a hidden tile leaves Edit; Add a tile lists it
  const own = { ...tileActions(section, u), sid: section.id }, act = actions(section, u, own), shown = editor.value;
  return (
    <div class="tpl-edit tpl-edit-glancetemplate" data-tpl="glancetemplate">
      <div class="glance" data-glance-template data-cols={u.per_row} data-own-row={u.health.own_row ? "1" : undefined}>
        {u.health.shown ? null : (
          <button type="button" class="gt-showhealth" data-gt-showhealth onClick={() => act.hide("health", false)}><span class="gt-showhealth-eye"><Icon name="eye" /></span>{WORDS.showHealth}</button>
        )}
        {list.map((t, i) => (
          <Cell key={t.key} tile={t} order={order} index={i} act={act}>
            {t.own ? <OwnTile t={shown && shown.id === t.key && shown.sid === section.id ? shown.draft : t} /> : t.key === "health" ? <Health t={{ ...t, pill: ({ "On track": "g", "At risk": "a", "Off track": "r" })[d.project.health] || "n" }} tools={{ glance: GLANCE }} editing={true} clean={null} /> : <Figure t={t} file={false} />}
          </Cell>
        ))}
        <PendingCell tools={own} />
      </div>
      {list.every((t) => t.key === "health") ? <p class="tile-empty" data-gt-empty>{`No tiles. Use ${TILE_WORDS.add}.`}</p> : null}
      <div class="tpl-gt-opts" data-gt-opts>
        <span class="tpl-gt-perrow" role="group" aria-label={WORDS.perRow}>{WORDS.perRow}
          {PER_ROWS.map((n) => <button type="button" key={n} class="gt-per" data-gt-per={n} aria-pressed={u.per_row === n ? "true" : "false"} onClick={() => act.perRow(n)}>{n}</button>)}
        </span>
        <button type="button" class="gt-own" data-gt-own role="switch" aria-checked={u.health.own_row ? "true" : "false"} onClick={() => act.ownRow(!u.health.own_row)}>
          <span class="gt-own-sw" aria-hidden="true"><i></i></span>{WORDS.ownRow}
        </button>
        <span class="tpl-gt-halfnote" data-gt-halfnote>{WORDS.halfNote}</span>
      </div>
      <AddTile tools={own} count={u.bespoke.length} hidden={away.map((t) => ({ key: t.key, title: t.own ? t.label : TILE_TITLES[t.key] }))} show={(key) => act.hide(key, false)} />
      <GLANCE.Hint {...(classicTheme() ? { text: WORDS.hint } : { more: `${WORDS.hintEye} ${WORDS.hintAdd}` })} />
    </div>
  );
}
