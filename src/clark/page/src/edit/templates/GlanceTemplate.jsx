// Glance template (row 1264, slice 4), store type "glancetemplate": its Edit part for the built-in tiles (Project health, Overdue actions,
// High risks and issues, Decisions needed). Each tile has a grip (drag, or Alt with the arrows), an eye (hide it from the published
// report) and, but for Project health, a right-click menu for its outline colour; Project health keeps its pill and reason box. The
// controls are the At a glance ones (edit/GlanceEdit.jsx); only where they save differs: the section's own body (templates/glanceBody.js),
// one change() each, so one step and one Undo. A change that leaves the body as it was sends nothing. The words are the At a glance
// words (the existing toasts); no new word is shown (WORDS_PENDING: none needed yet). The tile editor and the bespoke tiles are a later
// slice. View part: templates/GlanceTemplate.jsx.
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
import { Icon } from "../../components/Icon.jsx";

// The words of slice 9, quoted from the ruled words files (groups 2, 3, 10, 12, 13; v2 A). Nothing else is new here.
export const WORDS = {
  ownRow: "Project health on its own row", ownRowOn: "Project health sits on its own row", ownRowOff: "Project health sits with the tiles",       // group 2; v2 A
  showHealth: "Show project health here",                                                                                                    // group 3
  healthHidden: "Project health is hidden completely", healthShown: "Project health is shown",                                                // group 10
  hintEye: "The eye on Project health hides it completely.", hintAdd: "Use Add a tile to make your own. Click the pencil on your own tile to edit it.",   // group 12
  perRow: "Tiles on a line", halfNote: "Half width always shows 2 on a line.",                                                               // group 13
};

export const WORDS_PENDING = {};     // the words a person has not been given yet would be listed here as "[words pending: ...]"; slice 4 needs none

const focusLater = (at) => setTimeout(() => { const el = document.querySelector(at); if (el) el.focus(); }, 0);
const keepFocus = (done, at) => Promise.resolve(done).then((r) => { focusLater(at); return r; });

// What the tiles' controls ask of clark for this section. `u` is the body as drawn now.
function actions(section, u) {
  const at = (part) => `[data-id="${section.id}"] ${part}`;
  const tile = (key, part) => at(`[data-tile="${key}"] ${part}`);
  // `where`: what takes the focus again once the page is drawn again. `named`: change()'s options ({silent: true}: no toast, the step is kept for Undo).
  const send = (next, words, where, named = null) => {
    if (JSON.stringify(compact(next)) === JSON.stringify(compact(u))) return Promise.resolve(null);       // nothing changed: no step
    return keepFocus(change({ op: "update", id: section.id, changes: { body: JSON.stringify(compact(next)) }, place: "report" }, words, named), where);
  };
  const drawn = u.order.filter((k) => k in TILE_TITLES && (k !== "health" || u.health.shown));      // the tiles on the page: a health that is off is not one
  const move = (key, before, order) => {
    const at = order.indexOf(key);
    if (before === key || (before === null ? at === order.length - 1 : order[at + 1] === before)) return Promise.resolve(null);
    return send(withChange(u, { order: moved(u.order, key, before, drawn) }), `${TILE_TITLES[key]} moved.`, tile(key, "[data-tile-grip]"));
  };
  return {
    hide: (key, hidden) => send(withChange(u, { hide: [key, hidden] }),
      key === "health" ? (hidden ? WORDS.healthHidden : WORDS.healthShown) : hidden ? `${TILE_TITLES[key]} hidden from the published report.` : `${TILE_TITLES[key]} shown in the published report.`,
      key === "health" ? at(hidden ? "[data-gt-showhealth]" : "[data-tile=health] [data-tile-eye]") : tile(key, "[data-tile-eye]")),
    ownRow: (on) => send(withChange(u, { ownRow: on }), on ? WORDS.ownRowOn : WORDS.ownRowOff, at("[data-gt-own]")),
    perRow: (n) => send(withChange(u, { perRow: n }), "", at(`[data-gt-per="${n}"]`), { silent: true }),
    outline: (key, outline) => {
      const name = (OUTLINE_CHOICES.find((c) => c[0] === outline) || [0, ""])[1].toLowerCase();
      return send(withChange(u, { outline: [key, outline] }), outline ? `${TILE_TITLES[key]} outline: ${name}.` : `${TILE_TITLES[key]} outline: automatic.`, tile(key, "[data-tile-grip]"));
    },
    move,
    step: (key, dir, order) => {
      const s = stepTile(order, key, dir);
      if (!s) { note(`${TILE_TITLES[key]} is already ${dir < 0 ? "first" : "last"}.`); return Promise.resolve(null); }
      return move(key, s.before, order);
    },
    outlines: (key) => key !== "health",       // the body keeps an outline for the three counting tiles only
    eye: () => true,                            // Project health has its eye here: the body keeps health.shown
  };
}

export function Edit({ section }) {
  const u = readBody(section), d = data.value;
  const all = builtinTiles(u, rows.value, todayIso(), d.project), list = all.filter((t) => t.key !== "health" || u.health.shown), order = list.map((t) => t.key), act = actions(section, u), Cell = GLANCE.Cell;
  return (
    <div class="tpl-edit tpl-edit-glancetemplate" data-tpl="glancetemplate">
      <div class="glance" data-glance-template data-cols={u.per_row} data-own-row={u.health.own_row ? "1" : undefined}>
        {u.health.shown ? null : (
          <button type="button" class="gt-showhealth" data-gt-showhealth onClick={() => act.hide("health", false)}><span class="gt-showhealth-eye"><Icon name="eye" /></span>{WORDS.showHealth}</button>
        )}
        {list.map((t, i) => (
          <Cell key={t.key} tile={t} order={order} index={i} act={act}>
            {t.key === "health" ? <Health t={{ ...t, pill: ({ "On track": "g", "At risk": "a", "Off track": "r" })[d.project.health] || "n" }} tools={{ glance: GLANCE }} editing={true} clean={null} /> : <Figure t={t} file={false} />}
          </Cell>
        ))}
      </div>
      <div class="tpl-gt-opts" data-gt-opts>
        <span class="tpl-gt-perrow" role="group" aria-label={WORDS.perRow}>{WORDS.perRow}
          {PER_ROWS.map((n) => <button type="button" key={n} class="gt-per" data-gt-per={n} aria-pressed={u.per_row === n ? "true" : "false"} onClick={() => act.perRow(n)}>{n}</button>)}
        </span>
        <button type="button" class="gt-own" data-gt-own role="switch" aria-checked={u.health.own_row ? "true" : "false"} onClick={() => act.ownRow(!u.health.own_row)}>
          <span class="gt-own-sw" aria-hidden="true"><i></i></span>{WORDS.ownRow}
        </button>
        <span class="tpl-gt-halfnote" data-gt-halfnote>{WORDS.halfNote}</span>
      </div>
      <GLANCE.Hint />
      <p class="glance-hint" data-gt-hint>{WORDS.hintEye} {WORDS.hintAdd}</p>
    </div>
  );
}
