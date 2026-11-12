// The app's filter line state (#153). The address still holds the older state in `f` (so every link, tile and Back works as before);
// the line is that state written as words, plus what the older state cannot hold (a search word, `today`), kept for the session per
// project. Storage may be refused (a private window, a file): then the line is still right for the page, and only the memory is lost.
// Only the served page's entry loads this file (see lineSlot.js).
import { signal, computed } from "@preact/signals";
import { project, rows, filterState, f, refusals, filterNote, filterCtx, setFilters } from "./report.js";
import { decode, encode, fits, MODES, TYPES } from "../filters.js";
import * as FL from "../logic/filterLine.js";
import * as Q from "../logic/filterQueryUi.js";

const session = () => { try { return window.sessionStorage; } catch (e) { return null; } };
export const local = () => { try { return window.localStorage; } catch (e) { return null; } };
const memo = signal(0);                              // bumped when the kept line changes, so lineText is read again

/** The line on the page: the one kept for this project when it is the address's state, else the address's state as words. */
export const lineText = computed(() => {
  void memo.value;
  const st = decode(f.value), mem = project.value ? FL.lineGet(session(), project.value) : FL.BASE;
  return encode(FL.toState(mem, rows.value, filterCtx()).state) === encode(st) ? mem : FL.fromState(st);
});
/** The line kept for this project in this session (the start line when none). */
export const rememberedLine = () => (project.value ? FL.lineGet(session(), project.value) : FL.BASE);

/** A change of the line: the line goes to the session, and its older-state form to the address, as any filter change does.
 *  False (nothing changes, a plain line says why) when it would not fit in the address. */
export function setLine(line) {
  const next = FL.toState(line, rows.value, filterCtx()).state;
  if (!fits(next)) {
    refusals.value++;
    filterNote.value = "That filter would not fit in the page's address, so it was not added. Remove another filter first.";
    return false;
  }
  filterNote.value = "";
  if (project.value) FL.linePut(session(), project.value, line);
  memo.value++;
  setFilters(encode(next));
  return true;
}

// The older state without the `is:` words and Freshness values the line cannot answer yet. Never throws: a state of any shape gives a state.
function usable(want) {
  try {
    const ctx = filterCtx(), r = rows.value, ok = (w) => !FL.parse(`is:${w}`, r, ctx).errors.length;
    const word = { stale: "quiet", incomplete: "incomplete", gap: "incomplete" };
    const out = { ...want, is: (Array.isArray(want.is) ? want.is : []).filter((w) => ok(word[w] || w)) };
    const fl = want.filters && typeof want.filters === "object" ? want.filters : {};
    if (Array.isArray(fl.reviewed)) {
      const keep = fl.reviewed.filter((v) => ok(word[v] || "x"));
      out.filters = { ...fl };
      if (keep.length) out.filters.reviewed = keep; else delete out.filters.reviewed;
    }
    return out;
  } catch (e) { return want; }
}

/** What the Work items list needs of the line: the older-form state, the rows shown, whether Clear all shows, and Clear all itself. */
function view(rows_, ctx) {
  const line = lineText.value;
  return {
    state: FL.toState(line, rows_, ctx).state, rows: Q.rowsFor(rows_, line, ctx),
    can: line.trim() !== "", clear: () => setLine(""), empty: Q.emptyWords(line, rows_, ctx),
  };
}

/** Coming back to Work items: the project's kept line is the one shown (the address holds the older form of it). */
function restore() {
  const kept = rememberedLine();
  if (!f.value && kept !== FL.BASE && rows.value.length) setLine(kept);
}

/** The app's Work items page opened with a state (a tile): keep it as the project's line. */
function remember(code, state) { FL.linePut(session(), code, FL.fromState(state)); memo.value++; }

// The type and Open / Closed / All switches (with the counts that were always shown): the line with that one thing changed, everything else in it
// left as typed. A count is the number of rows that line would show.
function switches(rows_, ctx) {
  const line = lineText.value, st = FL.toState(line, rows_, ctx).state, n = {}, t = {};
  for (const [v] of MODES) n[v] = Q.rowsFor(rows_, Q.withMode(line, v, rows_, ctx), ctx).length;
  for (const [v] of TYPES) t[v] = Q.rowsFor(rows_, Q.withType(line, v, rows_, ctx), ctx).length;
  return { state: st, n, t };
}
const pickMode = (v) => setLine(Q.withMode(lineText.value, v, rows.value, filterCtx()));
const pickType = (v) => setLine(Q.withType(lineText.value, v, rows.value, filterCtx()));

/** True while the line asks for archived work (is:archived, not negated): Work items then draws the archived list in place of the live one. */
function wantsArchived(rows_, ctx) {
  try { return Q.parseFor(lineText.value, rows_, ctx).terms.some((t) => t.kind === "state" && !t.negate && t.states.includes("archived")); } catch (e) { return false; }
}

export const LINE_CORE = { empty: Q.EMPTY, wantsArchived, lineText, setLine, view, switches, pickMode, pickType, restore, remember, usable, base: FL.BASE, apply: (rows_, ctx) => Q.rowsFor(rows_, lineText.value, ctx), toState: (rows_, ctx) => FL.toState(lineText.value, rows_, ctx).state };
