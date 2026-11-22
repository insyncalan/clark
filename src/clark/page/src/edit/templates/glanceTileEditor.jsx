// Glance template (row 1264, slice 6): the tile editor. Add a tile (a button with a menu), the pencil and the bin on a tile the person typed, and the
// editor in the page: label, figure or short text, tag text, note, and one of five colours. Each colour has its own shape and a tag word, so colour is
// never the only signal. A new tile is a draft until Done; Done is one change (one step, one Undo); Cancel and Esc change nothing.
// Words: only the ruled ones (the 1264 words files, groups 4 to 9 and 14, v2 D and E); none is made up here. Edit only: the published page has none of this.
import { signal } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import { Menu } from "../../components/Menu.jsx";
import { Icon } from "../../components/Icon.jsx";
import { actionIcon } from "../../menuIcons.js";
import { change } from "../../stores/changes.js";
import { note } from "../notes.js";
import { compact, withChange, cleanTile, nextId } from "../../templates/glanceBody.js";
import { BESPOKE_MAX, LABEL_MAX, FIGURE_MAX, TAG_MAX, NOTE_MAX, chars } from "../../templates/glanceLimits.js";

export const WORDS = {
  add: "Add a tile", hiddenLine: "Hidden from the published report. Show it.", own: "Your own tile", ownHelp: "A label, a figure or short text, a tag and a colour you set",                 // group 4
  editTile: "Edit tile", editThis: "Edit this tile", deleteThis: "Delete this tile", remove: "Remove tile",                            // group 5
  label: "Label", figure: "Figure or short text", tag: "Tag text", note: "Note", optional: "optional",                                // group 6
  noLabel: "Give the tile a label.", notSaved: "The tile was not saved. Give it a label, then try again.",                            // group 6
  colour: "Colour", tileColour: "Tile colour", sentence: "The colour is a shape and the tag word too, never colour alone.",          // group 7
  popOut: "Pop out to a larger editor", bringBack: "Bring back to the tile",                                                          // group 8
  saved: "Tile saved", cancelled: "Changes to the tile cancelled",                                                                    // group 9
  untitled: "Untitled", newTile: "New tile", zero: "0", done: "Done", cancel: "Cancel",                                               // v2 D and E; Cancel exists in the app
};
export const limitWords = () => `You can have up to ${BESPOKE_MAX} tiles.`;                                                          // group 14
export const COLOURS = [["green", "Green", "On track"], ["amber", "Amber", "At risk"], ["red", "Red", "Off track"], ["blue", "Blue", "Info"], ["neutral", "Neutral", ""]];   // each colour has its tag word: On track, At risk, Off track, Info; Neutral has none
export const TONE_CLASS = { green: "g", amber: "a", red: "r", blue: "b", neutral: "n" };
const MOST = { label: LABEL_MAX, figure: FIGURE_MAX, tag: TAG_MAX, note: NOTE_MAX };

// The open editor: { sid: the section, id: the tile, isNew, draft: {label, figure, tag, note, tone}, pop, tried } or null. One at a time.
export const editor = signal(null);

const SHAPE = {
  green: <circle cx="6" cy="6" r="5.5" fill="currentColor" />,
  amber: <path d="M6 .5 11.7 11H.3z" fill="currentColor" />,
  red: <path d="M6 .2 11.8 6 6 11.8.2 6z" fill="currentColor" />,
  blue: <rect x=".5" y=".5" width="11" height="11" rx="2" fill="currentColor" />,
  neutral: <circle cx="6" cy="6" r="4.5" fill="none" stroke="currentColor" stroke-width="2" />,
};
export const Shape = ({ tone }) => <svg class={`tpl-shp tone-${TONE_CLASS[tone]}`} viewBox="0 0 12 12" aria-hidden="true" focusable="false">{SHAPE[tone] || SHAPE.neutral}</svg>;

const focusAfter = (sel) => setTimeout(() => { const el = document.querySelector(sel); if (el) el.focus(); }, 0);
const focusTile = (sid, key, part) => focusAfter(`[data-id="${sid}"] [data-tile="${key}"] ${part}`);
const focusAdd = (sid) => focusAfter(`[data-id="${sid}"] .tileadd`);
const saving = new Set();                                   // ids of the sections with a Done on its way: a second Done in the same section does nothing, another section is free
const cut = (s, most) => Array.from(s).slice(0, most).join("");

// Close the editor `e` was opened as. When another tile (or another section's tile) has its editor open by now, that one is not this one: it stays, with
// what was typed in it, and the focus is left where the person is typing. Returns whether it closed.
function close(e, how) {
  const now = editor.value;
  if (!now || now.sid !== e.sid || now.id !== e.id) return false;
  editor.value = null;
  if (how === "cancel") { note(WORDS.cancelled); if (e.isNew) focusAdd(e.sid); else focusTile(e.sid, e.id, "[data-tile-pencil]"); }
  return true;
}

// Send one new body. `words` is the toast; resolves to the reply, or null when it failed (the toast says why).
function send(section, u, next, words) {
  if (JSON.stringify(compact(next)) === JSON.stringify(compact(u))) return Promise.resolve(false);       // nothing changed: no step
  return change({ op: "update", id: section.id, changes: { body: JSON.stringify(compact(next)) }, place: "report" }, words);
}

// What the tile controls ask of clark. `u` is the body as drawn now.
export function tileActions(section, u) {
  return {
    del: async (tile) => {
      const r = await send(section, u, withChange(u, { drop: tile.key }), `Deleted: ${tile.label}`);
      if (r) { if (editor.value && editor.value.id === tile.key && editor.value.sid === section.id) editor.value = null; focusAdd(section.id); }
    },
    pencil: (tile) => {
      const e = editor.value;
      if (e && e.id === tile.key && e.sid === section.id) { close(e, "cancel"); return; }      // the same tile of this section: a second press closes it (tile ids repeat across sections)
      const t = u.bespoke.find((x) => x.id === tile.key) || {};
      editor.value = { sid: section.id, id: tile.key, isNew: false, pop: false, tried: false,
        draft: { label: t.label || "", figure: t.figure || "", tag: t.tag || "", note: t.note || "", tone: t.tone || "neutral" } };
    },
    add: () => {
      if (u.bespoke.length >= BESPOKE_MAX) { note(limitWords()); return; }
      editor.value = { sid: section.id, id: nextId(u), isNew: true, pop: false, tried: false,
        draft: { label: WORDS.newTile, figure: WORDS.zero, tag: "", note: "", tone: "neutral" } };
    },
    done: async () => {
      const e = editor.value;
      if (!e || saving.has(section.id)) return;
      const d = e.draft;
      if (!d.label.trim()) { editor.value = { ...e, tried: true }; note(WORDS.notSaved); focusAfter(`[data-id="${section.id}"] [data-tile-editor] [data-f=label]`); return; }
      const old = u.bespoke.find((x) => x.id === e.id) || {};
      const tile = cleanTile({ id: e.id, label: d.label, figure: d.figure, tag: d.tag, note: d.note, tone: d.tone, hidden: old.hidden });
      saving.add(section.id);
      let r;
      try { r = await send(section, u, withChange(u, { put: tile }), e.isNew ? `Added: ${tile.label}` : WORDS.saved); } finally { saving.delete(section.id); }
      if (r === null) return;                                  // it failed: the toast says why, the editor stays with what was typed (r false: nothing changed, close silently, no toast)
      if (close(e, "done")) focusTile(section.id, e.id, "[data-tile-pencil]");
    },
    remove: async () => {
      const e = editor.value, t = e && u.bespoke.find((x) => x.id === e.id);
      if (e && saving.has(section.id)) return;                  // its Done is on its way: Remove waits, so the tile is not stored after Remove
      if (e && e.isNew && !t) { close(e, "removed"); note(`Removed: ${e.draft.label.trim() || WORDS.untitled}`); focusAdd(e.sid); return; }   // a draft was never stored: drop it with the Removed words, not the cancel ones
      if (!t) return;
      const r = await send(section, u, withChange(u, { drop: e.id }), `Removed: ${t.label}`);
      if (r && close(e, "removed")) focusAdd(section.id);
    },
  };
}

// The pencil and the bin of an own tile, and its editor when it is the one open.
export function OwnControls({ tile, title, tools }) {
  const e = editor.value, open = e && e.id === tile.key && e.sid === tools.sid;
  return (
    <>
      <button type="button" class="tpen" data-edit-only data-tile-pencil aria-label={`Edit ${title}`} title={WORDS.editThis} aria-expanded={open ? "true" : "false"} onClick={() => tools.pencil(tile)}><Icon name="pencil" /></button>
      <button type="button" class="tdel" data-edit-only data-tile-bin aria-label={`Delete ${title}`} title={WORDS.deleteThis} onClick={() => tools.del(tile)}><Icon name="trash" /></button>
      {open ? <TileEditor tools={tools} /> : null}
    </>
  );
}

// One tile as the View part draws it (its dot, label, figure, tag word, note), from a draft or a stored tile.
export function OwnTile({ t }) {
  const tone = TONE_CLASS[t.tone] || "n", label = (t.label || "").trim() || WORDS.untitled;
  return (
    <div class={`fig tpl-gt-tile tone-${tone}`} role="group" aria-label={`${label}: ${t.figure || ""}`}>
      <i class="tpl-gt-dot" aria-hidden="true"></i>
      <span class="tpl-gt-k" title={label}>{label}</span>
      {t.figure ? <span class="tpl-gt-v num">{t.figure}</span> : null}
      {t.tag ? <span class="tpl-gt-tag">{t.tag}</span> : null}
      {t.note ? <span class="tpl-gt-note" title={t.note}>{t.note}</span> : null}
    </div>
  );
}

// The cell of a new tile that is not stored yet: the draft as a tile, and the editor under it.
export function PendingCell({ tools }) {
  const e = editor.value;
  if (!e || !e.isNew || e.sid !== tools.sid) return null;
  return (
    <div class="tcell own pending" data-tile={e.id}>
      <OwnTile t={e.draft} />
      <TileEditor tools={tools} />
    </div>
  );
}

function Field({ name, label, hint, value, tools, tried }) {
  const e = editor.value, bad = name === "label" && tried && !value.trim(), n = chars(value);
  const set = (ev) => {
    const v = cut(ev.target.value, MOST[name]);
    if (ev.target.value !== v) ev.target.value = v;
    editor.value = { ...editor.value, draft: { ...editor.value.draft, [name]: v } };
  };
  return (
    <>
      <label for={`te-${e.id}-${name}`}>{label} <small>{hint ? `${hint}, ` : ""}{n} of {MOST[name]}</small></label>
      <input class={`inp${bad ? " bad" : ""}`} id={`te-${e.id}-${name}`} data-f={name} value={value} aria-label={label} aria-invalid={bad ? "true" : undefined}
        aria-describedby={bad ? `te-${e.id}-err` : undefined} onInput={set} />
      {bad ? <p class="err" id={`te-${e.id}-err`} role="alert">{WORDS.noLabel}</p> : null}
    </>
  );
}

export function TileEditor({ tools }) {
  const e = editor.value, d = e.draft, box = useRef(null);
  useEffect(() => { const i = box.current && box.current.querySelector("[data-f=label]"); if (i) { i.focus(); if (e.isNew) i.select(); } }, [e.id]);       // eslint-disable-line react-hooks/exhaustive-deps
  const pick = (tone) => { editor.value = { ...editor.value, draft: { ...editor.value.draft, tone } }; };
  const arrow = (ev, i) => {
    const step = ev.key === "ArrowRight" || ev.key === "ArrowDown" ? 1 : ev.key === "ArrowLeft" || ev.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    ev.preventDefault();
    const to = COLOURS[(i + step + COLOURS.length) % COLOURS.length][0];
    pick(to);
    focusAfter(`[data-id="${e.sid}"] [data-tile-editor] [data-tone=${to}]`);
  };
  const keys = (ev) => { if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); close(e, "cancel"); } };
  const pop = () => { editor.value = { ...editor.value, pop: !editor.value.pop }; };
  return (
    <div class={`tpl-ed${e.pop ? " pop" : ""}`} data-tile-editor role="group" aria-label={WORDS.editTile} ref={box} onKeyDown={keys}>
      <h4>{WORDS.editTile}
        <button type="button" class="popbtn" data-pop aria-pressed={e.pop ? "true" : "false"} aria-label={e.pop ? WORDS.bringBack : WORDS.popOut} title={e.pop ? WORDS.bringBack : WORDS.popOut} onClick={pop}>
          <Icon name={e.pop ? "shrink" : "expand"} />
        </button>
      </h4>
      <Field name="label" label={WORDS.label} value={d.label} tools={tools} tried={e.tried} />
      <Field name="figure" label={WORDS.figure} value={d.figure} tools={tools} />
      <Field name="tag" label={WORDS.tag} hint={WORDS.optional} value={d.tag} tools={tools} />
      <Field name="note" label={WORDS.note} hint={WORDS.optional} value={d.note} tools={tools} />
      <p class="lbl">{WORDS.colour}</p>
      <div class="cols" role="radiogroup" aria-label={WORDS.tileColour}>
        {COLOURS.map(([tone, name, word], i) => (
          <button key={tone} type="button" class="col" role="radio" data-tone={tone} aria-checked={d.tone === tone ? "true" : "false"} tabIndex={d.tone === tone ? 0 : -1}
            onClick={() => pick(tone)} onKeyDown={(ev) => arrow(ev, i)}>
            <Shape tone={tone} /><span>{name}</span>{word ? <small>{word}</small> : null}
          </button>
        ))}
      </div>
      <p class="live">{WORDS.sentence}</p>
      <div class="foot">
        <button type="button" class="rm" data-remove onClick={() => tools.remove()}>{WORDS.remove}</button>
        <button type="button" class="btn" data-cancel onClick={() => close(e, "cancel")}>{WORDS.cancel}</button>
        <button type="button" class="btn pri" data-done onClick={() => tools.done()}>{WORDS.done}</button>
      </div>
    </div>
  );
}

// The Add a tile button with its menu. First the tiles hidden with the eye (row 1303: choosing one shows it again), then the one to make
// your own. At the limit that item says why it does nothing. `hidden`: [{ key, title }], `show(key)`.
export function AddTile({ tools, count, hidden = [], show }) {
  const full = count >= BESPOKE_MAX;
  const items = [...hidden.map((t) => ({ id: `show:${t.key}`, icon: actionIcon("add"), name: t.title, line: WORDS.hiddenLine })),
    { id: "own", icon: actionIcon("add"), name: WORDS.own, line: full ? limitWords() : WORDS.ownHelp }];
  return (
    <div class="tpl-add">
      <Menu label={WORDS.add} icon={actionIcon("add")} btnCls="sec-add tileadd" id="glance-add" menuId="glance-add-menu" menuLabel={WORDS.add} left chevron={false}
        items={items} onPick={(id) => (id === "own" ? tools.add() : show && show(id.slice(5)))} />
    </div>
  );
}
