// The contents minimap's logic (FR-18; the planning repo #67). Plain functions, no DOM and no Preact, so a test can run them alone.
// It lists the visible sections only, works out which one is current while the page scrolls, where a click should scroll
// to (below the sticky section bar), and what a key does inside the list.

import { isOpen, todayIso } from "../workItems.js";
import { milestoneRows } from "./milestones.js";

// A section's anchor id on the page: "sec-" and its id, with anything outside letters, digits, "_" and "-" turned into "-".
// The same id always gives the same anchor, so the report and the minimap agree without passing it around.
export function anchorId(id) {
  return `sec-${String(id).replace(/[^A-Za-z0-9_-]/g, "-")}`;
}

const TYPE_WORDS = { current: "Current state", glance: "At a glance", usecases: "Use cases", milestones: "Milestones", text: "Section", raid: "Risks and issues", actions: "Actions", decisions: "Decisions", docs: "Documents" };

// The entries to list: every section that is not hidden (its own `hidden` flag, or its id in hiddenSections), in page order,
// each { id, title, anchor, index }. A section with no title gets its type's plain name. Two ids that would give one anchor get
// distinct ones (-2, -3), so a click never lands on the wrong section.
export function entries(sections, hiddenSections) {
  const hidden = new Set(hiddenSections == null ? [] : Array.from(hiddenSections));
  const taken = new Set();
  const out = [];
  for (const s of sections || []) {
    if (!s || s.id == null || s.hidden === true || Number(s.hidden) === 1 || hidden.has(s.id)) continue;
    let anchor = anchorId(s.id), n = 1;
    while (taken.has(anchor)) anchor = `${anchorId(s.id)}-${++n}`;
    taken.add(anchor);
    out.push({ id: s.id, title: String(s.title || "").trim() || TYPE_WORDS[s.type] || "Section", anchor, index: out.length });
  }
  return out;
}

// Which entry is current. `offsets` is [{ id, top }] in page order, `top` measured from the top of the page. A section is
// current once its top is above a line 30% down the visible part of the page, under the sticky bar (the prototype's rule);
// at the very bottom the last section is current, as its top may never get that high. Returns an id, or null with no entries.
export function activeEntry(offsets, scrollTop, viewportHeight, stickyHeight = 0, pageHeight = 0) {
  if (!offsets || !offsets.length) return null;
  const sticky = Math.max(0, stickyHeight || 0);
  if (pageHeight > 0 && viewportHeight > 0 && scrollTop > 0 && scrollTop + viewportHeight >= pageHeight - 1) return offsets[offsets.length - 1].id;
  const line = scrollTop + sticky + Math.max(0, viewportHeight - sticky) * 0.3;
  let current = offsets[0].id;
  for (const o of offsets) if (o.top <= line) current = o.id;
  return current;
}

// Where to scroll to so a section's top sits just under the sticky bar: { id: scrollTop }, never below 0. `gap` is a little
// breathing room under the bar.
export function scrollTargets(offsets, stickyHeight = 0, gap = 0) {
  const out = {};
  for (const o of offsets || []) out[o.id] = Math.max(0, Math.round(o.top - Math.max(0, stickyHeight || 0) - Math.max(0, gap || 0)));
  return out;
}

// What a key does to which entry has the focus. Arrow Down/Right and Up/Left step (wrapping at the ends), Home and End go to
// the first and last. `index` is -1 when none has it yet. Any other key leaves it alone. -1 when there are no entries.
export function nextOnKey(index, count, key) {
  if (!(count > 0)) return -1;
  const at = Number.isInteger(index) ? Math.max(-1, Math.min(count - 1, index)) : -1;
  if (key === "ArrowDown" || key === "ArrowRight") return at < 0 ? 0 : (at + 1) % count;
  if (key === "ArrowUp" || key === "ArrowLeft") return at < 0 ? count - 1 : (at - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return at;
}

export function closesOn(key) {
  return key === "Escape" || key === "Esc";
}

// One step of the list's keyboard: { index, open } and a key give the new { index, open, handled }. Escape closes (and the
// caller puts the focus back on the minimap's button); a movement key moves and keeps it open.
export function onKey(state, key) {
  if (closesOn(key)) return { index: -1, open: false, handled: !!state.open };
  const moves = ["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft", "Home", "End"];
  if (!moves.includes(key)) return { ...state, handled: false };
  return { index: nextOnKey(state.index, state.count, key), open: true, handled: true };
}

// The count beside a section in the list (the prototype's "3 flagged", "2 slipped", "1 red", "1 late", "2"), worked out only from
// the report's own data block, so a published file shows the same words. Returns { text, hot } or null when there is nothing to say;
// `hot` marks a count that needs a look. A section type the data does not cover gets no count. `today` is YYYY-MM-DD; `client`
// is true for a published file (its milestone states are already worked out).
export function countOf(section, d, today, client) {
  const data = d || {};
  const on = today || todayIso();
  const live = (rows) => (rows || []).filter((r) => !r.archived);
  const some = (n, word) => (n ? { text: `${n} ${word}`, hot: true } : null);
  switch (section && section.type) {
    case "usecases": return some(live(data.use_cases).filter((u) => u.status && u.status !== "On track").length, "flagged");
    case "milestones": return some(milestoneRows(data.milestones, on, !!client).filter((m) => m.slip > 0).length, "slipped");
    case "actions": {
      const open = live(data.actions).filter(isOpen), late = open.filter((r) => r.due_date && r.due_date < on).length;
      return late ? some(late, "late") : open.length ? { text: String(open.length), hot: false } : null;
    }
    case "raid": {
      const open = live(data.raid).filter(isOpen), red = open.filter((r) => r.priority === "High" || r.priority === "Urgent").length;
      return red ? some(red, "red") : open.length ? { text: String(open.length), hot: false } : null;
    }
    case "decisions": return some(live(data.decisions).filter((r) => r.status === "Pending").length, "pending");
    case "docs": { const n = (data.documents || []).length; return n ? { text: String(n), hot: false } : null; }
    default: return null;
  }
}
