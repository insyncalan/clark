// Glance template (row 1264, slice 3), store type "glancetemplate": its view part, full width. Draws LOW tiles in the section's order:
// the three counting tiles (Overdue actions, High risks and issues, Decisions needed) as the At a glance section counts them, then the
// bespoke tiles. Each tile: a the At a glance tile look (1 px border, a 2 px tone edge fading from the top left, no edge when neutral), a dot (its
// SHAPE says the tone: circle green, triangle amber, diamond red, rounded square blue, ring neutral), the label and the note (they wrap, as in
// the approved v2 mock-up), the figure with the tag word at its right. Every tile is one fixed width (4 per line for now), left aligned. Colour is never the only signal: the shape
// and the tag word say it too. Text nodes only. The words are the At a glance ones that exist already (glanceTiles.js) or what the
// person typed; the library card and Edit words are the approved ones (section_kinds/glancetemplate.py), none is invented here.
// Project health (slice 9) is the At a glance health tile, drawn in the section's order when its eye is on; it takes the whole row when the
// section says so (health.own_row), else one tile's place. The grid has 4 tiles on a line, 3 when the section says so (per_row), 2 at half
// width (CSS) and 1 at 900. Health alone never makes a section: isEmpty looks at the counting and bespoke tiles only.
// A published file carries no counts yet (the counts slice), so a file draws only the bespoke tiles; the served View also counts.
// isEmpty: no tile is left to show. Edit part: edit/templates/GlanceTemplate.jsx; rules: section_kinds/glancetemplate.py.
import { source } from "./notes.js";
import { rows, fromFile, data, openWork } from "../stores/report.js";
import { todayIso } from "../workItems.js";
import { tiles as counted, shownRag, tileWord, HEALTH_WORDS } from "../glanceTiles.js";
import { Health } from "../components/Glance.jsx";
import { readBody } from "./glanceBody.js";

export const READY = true;
const text = (v) => (typeof v === "string" ? v.trim() : "");
const COUNTING = ["overdue", "risks", "decisions"];      // the three tiles that count work items, in the default order
const TONE_OF = { green: "g", amber: "a", red: "r", blue: "b", neutral: "n" };
const OUTLINES = ["R", "A", "G", "N"];

// The tiles the section's settings leave to show, in order: [{kind: "count" | "bespoke", key, ...}]. A counting tile is shown unless its
// hidden flag is set; a bespoke tile when it has a label and is not hidden. Health is not a tile of this part.
export function plan(section) {
  const v = source(section);
  const set = (v.builtin && typeof v.builtin === "object" && !Array.isArray(v.builtin)) ? v.builtin : {};
  const bespoke = (Array.isArray(v.bespoke) ? v.bespoke : []).filter((t) => t && typeof t === "object" && typeof t.id === "string" && text(t.label) && t.hidden !== true);
  const all = [...COUNTING.map((key) => {
    const s = set[key] && typeof set[key] === "object" ? set[key] : {};
    return { kind: "count", key, hidden: s.hidden === true, outline: OUTLINES.includes(s.outline) ? s.outline : "" };
  }), ...bespoke.map((t) => ({ kind: "bespoke", key: t.id, tile: t }))].filter((t) => t.kind === "bespoke" || !t.hidden);
  const rank = (t) => { const at = Array.isArray(v.order) ? v.order.indexOf(t.key) : -1; return at < 0 ? 1e6 : at; };
  return all.map((t, i) => [t, i]).sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1]).map((p) => p[0]);
}
// A counting tile is drawn only when its kind has rows (the published file's rule, section_kinds/glancetemplate.py _counts): no rows of
// the kind, no tile; so a fresh section with no rows and no bespoke tile draws nothing.
const KIND_OF = { overdue: (r) => r.kind === "action", risks: (r) => r.kind !== "action" && r.kind !== "decision", decisions: (r) => r.kind === "decision" };
const hasRows = (key) => rows.value.some((r) => r && KIND_OF[key](r));
const showable = (t) => t.kind === "bespoke" || (!fromFile.value && hasRows(t.key));
const fresh = (section) => Object.keys(source(section)).length === 0;     // no body at all: the published file leaves it out whole
// Every tile hidden (the three counting eyes off, no bespoke tile shown) is a section the person emptied on purpose: the View says so, as the
// approved v2 mock-up does (v2:539), instead of leaving the section out. A fresh section (no body) and a section with no rows and no
// bespoke tile stay left out: the published file leaves them out, and the mock-up draws sample tiles only because it has sample data.
export const EMPTY_WORDS = "No tiles on this section.";       // approved word, 1264-words group 11
const allHidden = (section) => {
  const set = source(section).builtin;
  return !!set && typeof set === "object" && COUNTING.every((k) => set[k] && set[k].hidden === true);      // a bespoke tile shown makes a list, so the sentence never meets it
};
export const isEmpty = (section) => !allHidden(section) && (fresh(section) || plan(section).filter(showable).length === 0);

// One tile as the part draws it: {key, label, figure, tag, note, tone}.
export function drawn(section) {
  if (isEmpty(section)) return [];
  const live = fromFile.value ? [] : counted(rows.value, todayIso());
  const out = [];
  for (const t of plan(section)) {
    if (t.kind === "bespoke") {
      out.push({ key: t.key, label: text(t.tile.label), figure: text(t.tile.figure), tag: text(t.tile.tag), note: text(t.tile.note), tone: TONE_OF[t.tile.tone] || "n" });
      continue;
    }
    const c = showable(t) ? live.find((x) => x.key === t.key) : null;
    if (!c) continue;
    const tone = shownRag(t.outline, c.rag);
    out.push({ key: t.key, label: c.label, figure: String(c.value), tag: tileWord(t.key, tone, t.outline), note: c.detail, tone, filter: c.filter });
  }
  return out;
}

// Project health as the At a glance health tile reads it: the pill's word and colour from the project, the reason as it is (a published file's
// is already cleaned; View's goes through `clean`). Not a counting tile: it has no figure of its own.
const PILL = { "On track": "g", "At risk": "a", "Off track": "r" };
const healthTile = (d) => {
  const h = (d && d.project && d.project.health) || "";
  return { key: "health", rag: HEALTH_WORDS[h] || "n", value: h || "Not set", reason: (d && d.project && d.project.health_reason) || "", pill: PILL[h] || "n", word: "" };
};

export function View({ section, clean }) {
  const list = drawn(section);
  if (!list.length) return allHidden(section) ? <div class="tpl-gt" data-gt><p class="tile-empty">{EMPTY_WORDS}</p></div> : null;
  const u = readBody(section), rank = (k) => { const at = u.order.indexOf(k); return at < 0 ? 1e6 : at; };
  const items = list.map((t) => ({ tile: t, key: t.key }));
  if (u.health.shown) {
    const at = items.findIndex((i) => rank(i.key) > rank("health"));
    items.splice(at < 0 ? items.length : at, 0, { health: true, key: "health" });
  }
  return (
    <div class="tpl-gt" data-gt data-cols={u.per_row}>
      {items.map((i) => {
        if (i.health) return (
          <div key="health" class={`tpl-gt-health${u.health.own_row ? " own-row" : ""}`} data-tile="health">
            <Health t={healthTile(data.value)} tools={null} editing={false} clean={clean} />
          </div>
        );
        const t = i.tile;
        const inner = (
          <>
            <span class="k">
              <i class="tpl-gt-dot" aria-hidden="true"></i>
              <span class="tpl-gt-k" title={t.label}>{t.label}</span>
            </span>
            {t.figure || t.tag ? (
              <span class="vrow">
                {t.figure ? <span class="v tpl-gt-v num">{t.figure}</span> : null}
                {t.tag ? <span class="tw tpl-gt-tag">{t.tag}</span> : null}
              </span>
            ) : null}
            {t.note ? <span class="dd tpl-gt-note" title={t.note}>{t.note}</span> : null}
          </>
        );
        // A counting tile opens Work items with its filter, as the At a glance tile does (Glance.jsx, v2:497); a bespoke tile has no filter and stays plain.
        return t.filter
          ? <button key={t.key} type="button" class={`fig go tpl-gt-tile tone-${t.tone}`} data-tile={t.key} onClick={() => openWork(t.filter)} aria-label={`${t.label}: ${t.figure}${t.note ? ", " + t.note : ""}${t.tag ? ". " + t.tag : ""}. Opens Work items showing these`}>{inner}</button>
          : <div key={t.key} class={`fig tpl-gt-tile tone-${t.tone}`} data-tile={t.key}>{inner}</div>;
      })}
    </div>
  );
}
