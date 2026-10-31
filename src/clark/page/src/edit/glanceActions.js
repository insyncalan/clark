// What the At a glance controls ask of clark (#45): each is one change with one Undo (stores/changes.js). A tile is hidden, given an
// outline colour or moved by its closed name; the project's health and reason are sent together, so one Undo puts both back.
import { signal } from "@preact/signals";
import { change } from "../stores/changes.js";
import { note } from "./notes.js";
import { TILE_TITLES, OUTLINE_CHOICES, stepTile } from "../glanceTiles.js";

export const dropTile = signal(null);        // while a tile is dragged: { key, side: "left" | "right" } of the tile it would go before or after
export const pendingHealth = signal("");     // a health picked while the reason is empty: it is saved with the reason, when the reason box is left

const focusLater = (key, part) => setTimeout(() => { const el = document.querySelector(`[data-tile="${key}"] ${part}`); if (el) el.focus(); }, 0);
const keepFocus = (done, key, part) => done.then((r) => { focusLater(key, part); return r; });

export function hideTile(key, hidden, place = "menu") {
  return keepFocus(change({ kind: "glance_tiles", op: "update", id: key, changes: { hidden: hidden ? 1 : 0 }, place },
    hidden ? `${TILE_TITLES[key]} hidden from the published report.` : `${TILE_TITLES[key]} shown in the published report.`), key, "[data-tile-eye]");
}

export function outlineTile(key, outline) {
  const name = (OUTLINE_CHOICES.find((c) => c[0] === outline) || [0, ""])[1].toLowerCase();
  return keepFocus(change({ kind: "glance_tiles", op: "update", id: key, changes: { outline }, place: "menu" },
    outline ? `${TILE_TITLES[key]} outline: ${name}.` : `${TILE_TITLES[key]} outline: automatic.`), key, "[data-tile-grip]");
}

/** Move tile `key` before tile `before` (null: to the end). Moved to where it already is, it does nothing. */
export function moveTile(key, before, order, place = "report") {
  const at = order.indexOf(key);
  if (before === key || (before === null ? at === order.length - 1 : order[at + 1] === before)) return Promise.resolve(null);
  return keepFocus(change({ kind: "glance_tiles", op: "move", id: key, before, place }, `${TILE_TITLES[key]} moved.`), key, "[data-tile-grip]");
}
export function stepOne(key, dir, order) {
  const s = stepTile(order, key, dir);
  if (!s) { note(`${TILE_TITLES[key]} is already ${dir < 0 ? "first" : "last"}.`); return Promise.resolve(null); }
  return moveTile(key, s.before, order, "report");
}

export function sendHealth(health, reason, words) {
  return change({ kind: "projects", op: "update", changes: { health, health_reason: reason }, place: "menu" }, words || `Health changed to ${health}.`);
}
export function sendReason(reason) {
  return change({ kind: "projects", op: "update", changes: { health_reason: reason }, place: "cell" }, "Reason changed.");
}

/** A health picked from the pill's menu. With a reason in place it is sent as it stands (and the toast says to check it still
 *  fits); with none, the reason box takes focus and both save when it is left. */
export function pickHealth(health, now, reason) {
  if (health === now) return Promise.resolve(null);
  if (String(reason || "").trim()) return sendHealth(health, reason, `Health changed to ${health}. Check that the reason still fits.`);
  pendingHealth.value = health;
  note(`Say why it is ${health} in a line or two. The health and the reason are saved together when you leave the box.`);
  // After the pick menu has closed and given focus back to the pill, so the reason box keeps it
  const focus = () => { const el = document.querySelector("[data-reason]"); if (el && document.activeElement !== el) el.focus(); };
  setTimeout(focus, 0);
  setTimeout(focus, 120);
  return Promise.resolve(null);
}
