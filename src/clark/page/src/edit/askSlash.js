// #1292 S10: slash commands in the ask clark box. Typing "/" at the very start of the box opens a menu of commands; arrows and Enter choose.
// The person's own commands are #1295, not here. This file is logic only: the panel draws the menu and runs the choice.
import * as W from "./askWords.js";

/** The commands, in the menu's order. `ask` is the question a command sends; `act` names a panel action that sends nothing. */
export const COMMANDS = [
  { name: "check", hint: W.SLASH_HINT.check, ask: "Check this report" },
  { name: "summary", hint: W.SLASH_HINT.summary, ask: "Summarise this week" },
  { name: "overdue", hint: W.SLASH_HINT.overdue, ask: "What is overdue?" },
  { name: "risks", hint: W.SLASH_HINT.risks, ask: "Which risks are red?" },
  { name: "milestones", hint: W.SLASH_HINT.milestones, ask: "What is the next milestone?" },
  { name: "usecases", hint: W.SLASH_HINT.usecases, ask: "Which use cases need attention?" },
  { name: "history", hint: W.SLASH_HINT.history, act: "history" },
  { name: "new", hint: W.SLASH_HINT.new, act: "new" },
];

/** The menu's commands with the person's own (row 1295; askOwn.js): their version of a built-in question replaces it, their new ones follow. */
export function withOwn(own, base = COMMANDS) {
  const mine = new Map((own || []).map((m) => [m.name, m]));
  return [...base.map((c) => (c.ask && mine.has(c.name) ? mine.get(c.name) : c)), ...[...mine.values()].filter((m) => !base.some((c) => c.name === m.name))];
}

/** The commands the box text matches, or null when the menu is not open. The caller passes classic (classicTheme()); Cards gets the hints it always had. `own` is the person's own commands. Open only for "/" at the start followed by letters (no space yet). */
export function slashMatches(text, classic = false, own) {
  const m = /^\/([a-z]*)$/i.exec(String(text || ""));
  if (!m) return null;
  const typed = m[1].toLowerCase();
  const base = classic ? COMMANDS.map((c) => ({ ...c, hint: W.SLASH_HINT_CLASSIC[c.name] || c.hint })) : COMMANDS;          // row 1350: the Classic wording is for Classic only; the caller says which
  return withOwn(own, base).filter((c) => c.name.startsWith(typed));
}

/** The next highlighted row for ArrowDown / ArrowUp, wrapping round; Home and End go to the ends. */
export function stepSlash(index, key, count) {
  if (!count) return 0;
  if (key === "ArrowDown") return (index + 1) % count;
  if (key === "ArrowUp") return (index - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return Math.min(Math.max(index, 0), count - 1);
}
