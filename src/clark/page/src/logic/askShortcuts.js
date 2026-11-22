// Row 1295: the data model and rules of ask clark slash commands. Pure functions on a list of records; the files are kept by the server (ask_commands.py, one file
// per slash command) and the editor page (edit/SlashEditor.jsx) sits on top. A slash command is text: it gets no more access than a typed question.
import { SLASH_HINT } from "../edit/askWords.js";
import { todayDate } from "../workItems.js";
export const MAX_SHORTCUTS = 20;
export const NAME_MIN = 2, NAME_MAX = 24, MENU_MAX = 70, TEXT_MAX = 1000;
export const SCOPES = ["anywhere", "item", "section", "usecase"];      // Anywhere; About a work item; About a section; About a use case
export const RESULTS = ["answer", "changes", "draft"];                 // An answer; An answer + changes; A draft
export const PLACEHOLDERS = {                                           // name -> the scopes where it has something to fill (null: anywhere)
  item: ["item"], owner: ["item"], section: ["section"], today: null, input: null,
};
// The built-in names are reserved. /history and /new are actions, not questions: locked. The others are the questions of the / menu (edit/askSlash.js
// COMMANDS: a test pins that the two lists agree), each an answer that may be anywhere.
export const LOCKED = ["history", "new"];
const ask = (name, menu, text) => ({ name, menu, text, scope: "anywhere", result: "answer", builtin: true });
export const BUILTINS = [
  ask("check", SLASH_HINT.check, "Check this report"),
  ask("summary", SLASH_HINT.summary, "Summarise this week"),
  ask("overdue", SLASH_HINT.overdue, "What is overdue?"),
  ask("risks", SLASH_HINT.risks, "Which risks are red?"),
  ask("milestones", SLASH_HINT.milestones, "What is the next milestone?"),
  ask("usecases", SLASH_HINT.usecases, "Which use cases need attention?"),
  { name: "history", menu: SLASH_HINT.history, text: "", scope: "anywhere", result: "answer", builtin: true, locked: true },
  { name: "new", menu: SLASH_HINT.new, text: "", scope: "anywhere", result: "answer", builtin: true, locked: true },
];

const NAME_RE = /^[a-z][a-z0-9-]*$/;

/** The message for a name that breaks a rule, or "" when it is good. `taken` is the names already used, `self` the name being edited (kept allowed). */
export function nameProblem(name, taken = [], self = "", builtins = BUILTINS) {
  const n = String(name == null ? "" : name);
  if (n.length < NAME_MIN) return "The name needs at least " + NAME_MIN + " characters.";
  if (n.length > NAME_MAX) return "The name can be at most " + NAME_MAX + " characters.";
  if (/[A-Z]/.test(n)) return "Use lower case letters only in the name.";
  if (/\s/.test(n)) return "The name cannot have spaces. Use a hyphen instead.";
  if (!/^[a-z]/.test(n)) return "The name must start with a letter.";
  if (!NAME_RE.test(n)) return "The name can have only lower case letters, numbers and hyphens.";
  if (n === self) return "";
  if (builtins.some((b) => b.name === n)) return "That name is used by a built-in slash command. Choose another.";
  if (taken.includes(n)) return "You already have a slash command with that name.";
  return "";
}

/** Every plain-words problem with a slash command's fields (empty list when it can be saved). */
export function problems(s, mine = [], builtins = BUILTINS) {
  const out = [];
  const own = s.builtin ? "" : (s.was || "");
  const np = s.builtin ? "" : nameProblem(s.name, mine.map((m) => m.name), own, builtins);
  if (np) out.push(np);
  if (String(s.menu || "").length > MENU_MAX) out.push("The line in the menu can be at most " + MENU_MAX + " characters.");
  if (!String(s.menu || "").trim()) out.push("Say what it does in the menu, in a few words.");
  if (String(s.text || "").length > TEXT_MAX) out.push("The instructions can be at most " + TEXT_MAX.toLocaleString("en-GB") + " characters.");
  if (!String(s.text || "").trim()) out.push("Say what it should do, in plain words.");
  if (!SCOPES.includes(s.scope)) out.push("Choose where it appears.");
  if (!RESULTS.includes(s.result)) out.push("Choose what you get.");
  return out;
}

/** The list the person sees: their own first, then the built-ins, an edited built-in shown with their version and "edited". */
export function listAll(mine, builtins = BUILTINS) {
  const over = new Map(mine.filter((m) => m.replaces).map((m) => [m.replaces, m]));
  return {
    yours: mine.filter((m) => !m.replaces),
    builtIn: builtins.map((b) => (over.has(b.name) ? { ...over.get(b.name), name: b.name, builtin: true, edited: true } : b)),
  };
}

const err = (m) => { throw new Error(m); };

/** Saves a slash command of the person's. A built-in becomes their own version that replaces it (name kept); a locked one cannot be saved. */
export function save(mine, s, builtins = BUILTINS) {
  const b = s.builtin ? builtins.find((x) => x.name === s.name) : null;
  if (s.builtin && !b) err("No built-in slash command has that name.");
  if (b && b.locked) err("/" + b.name + " is an action, not a question, so it cannot be edited.");
  const rec = b ? { name: b.name, replaces: b.name, menu: s.menu, text: s.text, scope: s.scope, result: s.result }
                : { name: s.name, menu: s.menu, text: s.text, scope: s.scope, result: s.result, ...(s.ai ? { ai: true } : {}) };
  const rest = mine.filter((m) => (b ? m.replaces !== b.name : m.name !== (s.was || s.name)));
  const p = problems({ ...rec, builtin: !!b, was: s.was }, rest.filter((m) => !m.replaces), builtins);
  if (p.length) err(p[0]);
  if (!b && rest.filter((m) => !m.replaces).length >= MAX_SHORTCUTS) err("You can keep " + MAX_SHORTCUTS + " slash commands in a project. Remove one to add another.");
  return [...rest, rec];
}

/** Reset to the built-in: drops the person's version; the original text, where and result come back. */
export const reset = (mine, name) => mine.filter((m) => m.replaces !== name);
/** Remove: yours only (a built-in cannot be removed, only reset). */
export const remove = (mine, name) => (mine.some((m) => m.name === name && !m.replaces) ? mine.filter((m) => m.name !== name || m.replaces) : err("Only your own slash commands can be removed."));

/** Make a copy: a new slash command of yours ("check-2"), the original untouched. A locked built-in has nothing to copy. */
export function copy(mine, s, builtins = BUILTINS) {
  const from = (s.builtin ? listAll(mine, builtins).builtIn.find((b) => b.name === s.name) : mine.find((m) => m.name === s.name && !m.replaces)) || err("Nothing to copy.");
  if (from.locked) err("/" + from.name + " is an action, not a question, so it cannot be copied.");
  if (mine.filter((m) => !m.replaces).length >= MAX_SHORTCUTS) err("You can keep " + MAX_SHORTCUTS + " slash commands in a project. Remove one to add another.");
  const used = new Set([...mine.map((m) => m.name), ...builtins.map((b) => b.name)]);
  const base = from.name.replace(/-\d+$/, "");
  const make = (i) => base.slice(0, NAME_MAX - ("-" + i).length) + "-" + i;   // cut the base first, so the suffix is never cut off
  let i = 2; while (used.has(make(i))) i++;
  return [...mine, { name: make(i), menu: from.menu, text: from.text, scope: from.scope, result: from.result }];
}

const dmy = (d) => String(d.getDate()).padStart(2, "0") + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + d.getFullYear();

/** Fills the placeholders. ctx: { item:{id,title,owner,due,status,update}, section, input, today:Date }. Returns { text, notSet:[names] }: one with nothing
 * to fill is reported (and left out of the text as a visible "[not set]"), never sent as the word itself. */
export function fill(s, ctx = {}) {
  const notSet = [];
  const val = {
    item: ctx.item && ctx.item.id != null ? [ctx.item.id, ctx.item.title, ctx.item.owner, ctx.item.due, ctx.item.status, ctx.item.update].filter((v) => v).join(", ") : "",
    owner: ctx.item && ctx.item.owner || "",
    section: ctx.section || "",
    today: ctx.today ? dmy(ctx.today) : "",
    input: ctx.input || "",
  };
  const text = String(s.text || "").replace(/\{(item|owner|section|today|input)\}/g, (_, k) => {
    const ok = PLACEHOLDERS[k] === null || (PLACEHOLDERS[k].includes(s.scope));
    if (!ok || !val[k]) { if (!notSet.includes(k)) notSet.push(k); return "[not set]"; }
    return val[k];
  });
  return { text, notSet };
}

/** Placeholders in the text that cannot be filled where the slash command appears (the AI check's warning). */
export const unfillable = (s) => [...new Set([...String(s.text || "").matchAll(/\{(item|owner|section)\}/g)].map((m) => m[1]))].filter((k) => !PLACEHOLDERS[k].includes(s.scope));

/** The commands the / menu gets from the person's files (`b` is the server's answer {all, project}): an answer, anywhere, with no {input}, filled with today. A project's own wins. */
export function menuCommands(b, today = todayDate()) {
  const byName = new Map([...b.all, ...(Array.isArray(b.project) ? b.project : [])].map((m) => [m.name, m]));
  return [...byName.values()]
    .filter((m) => m.scope === "anywhere" && m.result === "answer" && !/\{input\}/.test(m.text) && !(BUILTINS.find((x) => x.name === m.name) || {}).locked)
    .map((m) => ({ name: m.name, hint: m.menu, ask: fill({ text: m.text, scope: "anywhere" }, { today }).text, own: !m.replaces }));
}
