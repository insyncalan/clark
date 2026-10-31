// #159: what the Publish dialog says is stale or missing before you publish. Pure: rows and today in, plain values out. It only
// counts; it never blocks, and it lives in the editor's part of the page, so a published file has none of these words.
import { freshnessValues, REVIEW_DAYS, initial, setFilter } from "../filters.js";
import { plural } from "../workItems.js";

// The groups with something in them, in this order; none when everything is fresh. `value` is the Freshness filter value that
// lists exactly these items.
export function groups(rows, today) {
  const count = { incomplete: 0, stale: 0 };
  for (const r of rows || []) for (const v of freshnessValues(r, today)) count[v]++;
  const out = [];
  const words = (n, what) => `${plural(n, "open item")} ${n === 1 ? "has" : "have"} ${what}.`;
  const name = (n, what) => `Show them: ${plural(n, "item")} ${what}`;      // the Show them link's own accessible name; it starts with the visible words, so voice control matches
  if (count.incomplete) out.push({ value: "incomplete", count: count.incomplete, text: words(count.incomplete, "no owner or no date"), label: name(count.incomplete, "with no owner or no date") });
  if (count.stale) out.push({ value: "stale", count: count.stale, text: words(count.stale, `not been reviewed in ${plural(REVIEW_DAYS, "day")}`), label: name(count.stale, `not reviewed in ${plural(REVIEW_DAYS, "day")}`) });
  return out;
}

// The Work items state that shows exactly one group.
export function showState(value) { return setFilter(initial(), "reviewed", [value], false); }

export const ANYWAY = "Show them, or publish anyway.";
