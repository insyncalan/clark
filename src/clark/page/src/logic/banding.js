// Row 1311 (ruling 19-11): the Classic dashboard bands every other VISIBLE section. CSS cannot count only the visible ones, so this sets the
// class `band`, as the prototype's tag() does. A hidden section does not count; the summary (the Current state block, type current) is never banded and does not count;
// a This week | Next week pair (slot-left then slot-right) counts and bands as ONE. Pure: items are { id, hidden, summary, slot } in page order.

// The ids that are banded: the first counted section, then every other one.
export function bandIds(items) {
  const out = [];
  let n = 0;
  let pairRight = false;      // the right half of a pair takes the band of its left half
  let prev = null;
  for (const it of items) {
    if (it.hidden) continue;
    if (it.summary) { prev = null; continue; }
    if (it.slot === "right" && prev && prev.slot === "left" && prev.banded !== undefined) {
      if (prev.banded) out.push(it.id);
      prev = null;
      continue;
    }
    const on = n % 2 === 0;
    n += 1;
    if (on) out.push(it.id);
    prev = { slot: it.slot, banded: on };
  }
  return out;
}

// The summary is the Current state block: the older type "current", or the default text section titled "Current state" (item 1188).
export function isSummary(e) {
  if (e.dataset.type === "current") return true;
  const h = e.querySelector(".sec-h");
  return e.dataset.type === "text" && !!h && h.textContent.trim() === "Current state";
}

// The DOM side: read the sections of `.secs` under root, set or clear .band on each. Returns the ids banded.
export function applyBands(root) {
  const els = [...root.querySelectorAll(".secs > .sec")];
  const ids = new Set(bandIds(els.map((e, i) => ({
    id: i, hidden: e.classList.contains("is-hidden") || e.classList.contains("drag-slot"), summary: isSummary(e),
    slot: e.classList.contains("slot-left") ? "left" : e.classList.contains("slot-right") ? "right" : "full" }))));
  els.forEach((e, i) => { if (e.classList.contains("band") !== ids.has(i)) e.classList.toggle("band", ids.has(i)); });
  return [...ids];
}
