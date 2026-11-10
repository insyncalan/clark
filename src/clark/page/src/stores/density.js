// Spacing (item 1025, Settings > Personal): Compact or Comfortable, one setting for the whole app. One setting for this person on this
// computer, remembered in the browser under one key (never in the project's data), applied at once as html[data-density]. A published
// file carries the choice it was published with (useFileDensity) and has no way to change it.
//
// Bridge, until the guarded publish files change (publish.py, publish_flow.py, to_client.py; see the plan on item 1025): they still
// speak the four old section words, so the choice is sent and read as the old word: Compact is "card", Comfortable is "roomy" (the publish code fills a missing word with "slim", which must read as Compact). No other old word is ever sent.
import { signal } from "@preact/signals";

export const IDS = ["compact", "comfortable"];
const KEY = "clark.density";
export const DEFAULT_DENSITY = "compact";             // for a person who has chosen nothing, and for any unknown or missing value
export const valid = (v) => IDS.includes(v);
const normal = (v) => (valid(v) ? v : DEFAULT_DENSITY);

/** The old section word that carries a density to the guarded publish code (the bridge above). */
export const sectionWord = (d) => (d === "comfortable" ? "roomy" : "card");
/** The density a published file's section word stands for; anything not "roomy" is Compact. */
export const densityOfWord = (w) => (w === "roomy" ? "comfortable" : DEFAULT_DENSITY);

function remembered() {
  try { return normal(localStorage.getItem(KEY)); } catch (e) { return DEFAULT_DENSITY; }
}

export const density = signal(remembered());

function paint(v) {
  try {
    const root = document.documentElement;
    root.dataset.density = v;
  } catch (e) { /* no document: nothing to paint */ }
}
paint(density.value);

/** Choose a density (Settings > Personal): it applies at once and is remembered. Anything else is ignored. */
export function setDensity(v) {
  if (!valid(v)) return;
  density.value = v;
  paint(v);
  try { localStorage.setItem(KEY, v); } catch (e) { /* a private window: it applies now, and is not remembered */ }
}

/** A published file's own density (set once, never remembered), from the section word its data block carries. */
export function useFileDensity(word) {
  const d = densityOfWord(word);
  density.value = d;
  paint(d);
}
