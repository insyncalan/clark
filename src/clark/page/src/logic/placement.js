// Where a section goes when it is moved (#95): pure functions, no DOM, no signals, nothing sent. The page gives them its sections
// in the order clark sent (data.report_sections: by sort_order, then id) and a target; they give back the one change to ask clark
// for, or a refusal in plain words. docs/handoff/design-95-drag-sections.md has the rules.
//
// A section is { id, title, beside, hidden, ... }. `beside: 1` means "shares its row with the next section". Rows are read from the
// list in order, so any flags give rows of one or two and never three: a flag on the second of a pair, or on the last section, does
// nothing. A target is { before: id | null } (a row of its own, before the row that starts with that section; null: at the end) or
// { beside: id, side: "left" | "right" } (half of a section that is alone).
//
// A change is { op: "move", id, before, flags? }: `before` is the section the moved one ends up directly before (null: last), and
// `flags` is { id: 0 | 1 } for the sections whose `beside` changes, only those. Without flags it is the request the page sends today.
// With flags (and for a flag of 1 on a section that is not text) it needs the guarded changes in the design note, section 2.

const MESSAGES = {
  gone: "That section isn't in the report any more. Reload the page.",
  full: "A row holds two sections at most. Put it between rows, or beside a section on its own.",
  inside: "A section can't go in the middle of a pair. Put it between rows.",
  first: "This section is already first.",
  last: "This section is already last.",
  noNext: "This is the last section, so there is nothing to sit beside.",
  nextFull: "The next row already has two sections. Move one of them first, or move this section between rows.",
  shared: "This section already shares its row. Choose Full width to give it a row of its own.",
  alone: "This section already has its own row.",
};
const QUIET = { itself: true, same: true };        // nothing to say: dropped on itself, or where it already is
const EDGE = 56;                                   // px: the top and bottom of a section where a drop means "between rows" (at most a quarter of it)

const refuse = (why) => ({ ok: false, why, message: QUIET[why] ? "" : MESSAGES[why], quiet: !!QUIET[why] });

// A section's title as a person reads it in a message: short, never empty.
const name = (s) => {
  const t = Array.from(String((s && s.title) || "").trim());
  return t.length === 0 ? "This section" : t.length > 40 ? t.slice(0, 39).join("") + "…" : t.join("");
};

// The rows as the page draws them: one or two sections each. With `keep` (a function), a section it refuses is left out AFTER the
// rows are read, so a pair with one half out shows the other on its own, and the sections either side never pair.
export function rows(sections, keep) {
  const out = [];
  for (let i = 0; i < sections.length; i++) {
    if (sections[i].beside && i + 1 < sections.length) { out.push([sections[i], sections[i + 1]]); i++; } else out.push([sections[i]]);
  }
  return keep ? out.map((r) => r.filter(keep)).filter((r) => r.length) : out;
}

// { id: "full" | "left" | "right" } for the sections `keep` allows: what the grid needs (the classes slot-full, slot-left, slot-right).
export function slots(sections, keep) {
  const out = {};
  for (const r of rows(sections, keep)) r.forEach((s, i) => { out[s.id] = r.length === 1 ? "full" : i === 0 ? "left" : "right"; });
  return out;
}

// Move section `id` to `target`. { ok: true, payload, words } or { ok: false, why, message, quiet }.
export function place(sections, id, target) {
  return plan(sections, id, target, null);
}

function plan(sections, id, target, say) {
  const at = sections.findIndex((s) => s.id === id);
  if (at < 0 || !target) return refuse("gone");
  const base = {};
  const wk = sections.map((s) => { base[s.id] = s.beside ? 1 : 0; return { id: s.id, beside: base[s.id], title: s.title }; });
  const me = wk[at];
  const old = rows(wk).find((r) => r.includes(me));
  const partner = old.length === 2 ? old.find((s) => s !== me) : null;
  const rest = wk.filter((s) => s !== me);
  if (partner) partner.beside = 0;                   // alone now; a stray flag on it must not pair it with what follows
  const readRows = rows(rest);
  let idx, ref = null, side = null;
  if ("beside" in target) {
    if (target.beside === id) return refuse("itself");
    ref = rest.find((s) => s.id === target.beside);
    side = target.side;
    if (!ref || (side !== "left" && side !== "right")) return refuse("gone");
    if (readRows.find((r) => r.includes(ref)).length > 1) return refuse("full");
    idx = rest.indexOf(ref) + (side === "right" ? 1 : 0);
    me.beside = side === "left" ? 1 : 0;
    ref.beside = side === "right" ? 1 : 0;
  } else {
    if (!("before" in target)) return refuse("gone");
    if (target.before === id) return refuse("itself");
    if (target.before === null) idx = rest.length;
    else {
      idx = rest.findIndex((s) => s.id === target.before);
      if (idx < 0) return refuse("gone");
      if (readRows.find((r) => r.includes(rest[idx]))[0] !== rest[idx]) return refuse("inside");
    }
    me.beside = 0;
  }
  const before = rest[idx - 1];                      // a section on its own with a flag would take the moved one as its pair
  if (before && before !== ref && readRows.find((r) => r.includes(before)).length === 1) before.beside = 0;
  const list = rest.slice();
  list.splice(idx, 0, me);
  const flags = {};
  for (const s of list) if (s.beside !== base[s.id]) flags[s.id] = s.beside;
  const next = list[list.indexOf(me) + 1];
  const payload = { op: "move", id, before: next ? next.id : null };
  if (Object.keys(flags).length) payload.flags = flags;
  if (!payload.flags && list.every((s, i) => s.id === sections[i].id)) return refuse("same");
  const you = name(sections[at]);
  let words;
  if (say) words = say;
  else if (ref) words = `Moved ${you} beside ${name(ref)}, on the ${side}.`;
  else if (target.before === null) words = `Moved ${you} to its own row, at the end.`;
  else if (idx === 0) words = `Moved ${you} to its own row, at the top.`;
  else words = `Moved ${you} to its own row, above ${name(rest[idx])}.`;
  return { ok: true, payload, words };
}

// Move up (dir -1) and Move down (1), by rows: a section on its own passes the neighbouring row (a pair counts as one); half of a
// pair steps out of it, to full width: towards its partner it lands just beside the pair, away from it goes out and past the next row.
export function step(sections, id, dir) {
  const rs = rows(sections);
  const k = rs.findIndex((r) => r.some((s) => s.id === id));
  if (k < 0) return refuse("gone");
  const row = rs[k], me = row.find((s) => s.id === id);
  const second = row.length === 2 && row[1] === me;
  const others = rs.filter((_, j) => j !== k);
  if (row.length === 2) others.splice(k, 0, row.filter((s) => s !== me));       // its partner, alone, where the pair was
  const to = row.length < 2 ? k + dir : dir < 0 ? (second ? k : k - 1) : (second ? k + 2 : k + 1);
  if (to < 0) return refuse("first");
  if (to > others.length) return refuse("last");
  return plan(sections, id, { before: others[to] ? others[to][0].id : null }, `Moved ${name(me)} ${dir < 0 ? "up" : "down"}.`);
}

// "Place beside the next section": a section on its own, with a section on its own after it; it takes the left half.
export function beside(sections, id) {
  const rs = rows(sections);
  const k = rs.findIndex((r) => r.some((s) => s.id === id));
  if (k < 0) return refuse("gone");
  if (rs[k].length === 2) return refuse("shared");
  if (!rs[k + 1]) return refuse("noNext");
  if (rs[k + 1].length === 2) return refuse("nextFull");
  return place(sections, id, { beside: rs[k + 1][0].id, side: "left" });
}

// "Full width": either half of a pair. The pair ends and both stay where they are.
export function fullWidth(sections, id) {
  const row = rows(sections).find((r) => r.some((s) => s.id === id));
  if (!row) return refuse("gone");
  if (row.length < 2) return refuse("alone");
  const at = sections.findIndex((s) => s.id === id);
  const next = sections[at + 1];
  return plan(sections, id, { before: next ? next.id : null }, `${name(sections[at])} is now full width.`);
}

// The target for a pointer at point { x, y }. `rects` is { id: { left, top, right, bottom } } for the sections drawn. `columns` is 2
// when pairs sit side by side, 1 when they stack (then there is no half to drop on). The section nearest the pointer decides:
// its top or bottom edge is a row of its own above or below its row, its middle is a half when it is alone, and over a pair the
// nearer of the two lines. Over the section being moved there is no target (null); above the first row is the top; below the last, the end.
export function targetAt(sections, id, rects, point, opts) {
  const columns = opts && opts.columns === 1 ? 1 : 2;
  let best = null, nearest = Infinity;
  for (const s of sections) {
    const r = rects[s.id];
    if (!r) continue;
    const dx = Math.max(r.left - point.x, 0, point.x - r.right), dy = Math.max(r.top - point.y, 0, point.y - r.bottom);
    if (dx * dx + dy * dy < nearest) { nearest = dx * dx + dy * dy; best = s; }
  }
  if (!best || best.id === id) return null;
  const all = rows(sections).filter((r) => r.some((s) => rects[s.id]));
  const k = all.findIndex((r) => r.includes(best));
  const row = all[k];
  const drawn = row.map((s) => rects[s.id]).filter(Boolean);
  const top = Math.min(...drawn.map((r) => r.top)), bottom = Math.max(...drawn.map((r) => r.bottom));
  const others = row.filter((s) => s.id !== id);
  const above = () => ({ before: others[0].id });
  const below = () => {
    const next = all[k + 1];
    if (!next) return { before: null };
    const there = next.filter((s) => s.id !== id);
    if (there.length) return { before: there[0].id };
    const after = all[k + 2];                         // the next row is the moved section's own: its place is where it is
    return { before: after ? after[0].id : null };
  };
  const edge = Math.min((bottom - top) / 4, EDGE);
  if (point.y < top + edge) return above();
  if (point.y > bottom - edge) return below();
  if (columns === 2 && others.length === 1) {
    const r = rects[best.id];
    return { beside: best.id, side: point.x < r.left + (r.right - r.left) / 2 ? "left" : "right" };
  }
  return point.y < (top + bottom) / 2 ? above() : below();
}

// What to draw for a target while dragging, or null where a drop would do nothing or be refused (so the indicator and the drop never
// disagree). { outline: id, side } is the half to outline; { line: "before", ids } is a line above the row that holds those
// sections; { line: "end" } is a line below the last row.
export function indicator(sections, id, target) {
  if (!place(sections, id, target).ok) return null;
  if ("beside" in target) return { outline: target.beside, side: target.side };
  if (target.before === null) return { line: "end", ids: [] };
  const row = rows(sections).find((r) => r.some((s) => s.id === target.before));
  return { line: "before", ids: row.map((s) => s.id) };
}

// What clark will do with a change: the list as it will be, in its new order, with the flags set. (The server works out each
// section's sort_order; here the order is the list's.) For the tests, and so a Python test can be held to the same answer.
export function applied(sections, payload) {
  const moved = sections.find((s) => s.id === payload.id);
  const list = sections.filter((s) => s.id !== payload.id);
  const k = payload.before === null ? list.length : list.findIndex((s) => s.id === payload.before);
  list.splice(k, 0, moved);
  const flags = payload.flags || {};
  return list.map((s) => (s.id in flags ? { ...s, beside: flags[s.id] } : s));
}
