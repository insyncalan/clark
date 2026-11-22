// Row 1295: what the slash commands editor sends to the AI route and how it reads the answer. Plain JS, no DOM. Every request is the person's own
// words (the instructions as written, placeholders not filled, or the one sentence they typed) and one fixed instruction; no project data goes.
import { SCOPES, RESULTS } from "./askShortcuts.js";

export const PLACE = "plain";
export const DESCRIBE_ASK = "Write a slash command for ask clark from this sentence. Reply with exactly these lines: Name: (2 to 24 lower case letters, numbers or hyphens), "
  + "Menu: (at most 70 characters), Where: (anywhere, item, section or usecase), Gets: (answer, changes or draft), Instructions: (in plain words; may use {item}, {owner}, {section}, {today}, {input}).";
export const MENU_ASK = "Write the line a menu shows for a slash command that follows these instructions: one line of at most 70 characters, in plain words, no quotation marks.";
export const CLEARER_ASK = "Add short plain-English lines that make these instructions clearer, for example: Dates as DD-MM-YYYY. Keep every existing line exactly as it is and put the new lines after them.";
export const CHECK_ASK = "Judge these slash command instructions. Reply with exactly three lines: Clear: (yes or no, and one short reason), "
  + "Reads: (whether they ask for anything beyond what a question typed by hand can read), Changes: (what they could change, or nothing).";

// The requests as the route takes them: {option, place, text, instruction}.
export const describeRequest = (sentence) => ({ option: "custom", place: PLACE, text: sentence, instruction: DESCRIBE_ASK });
export const menuRequest = (text) => ({ option: "custom", place: PLACE, text, instruction: MENU_ASK });
export const clearerRequest = (text) => ({ option: "custom", place: PLACE, text, instruction: CLEARER_ASK });
export const shorterRequest = (text) => ({ option: "shorter", place: PLACE, text, instruction: "" });
export const checkRequest = (text) => ({ option: "custom", place: PLACE, text, instruction: CHECK_ASK });

// The route's cleaned html as plain lines (the route escapes every character, so only its own tags and entities are undone here).
export function htmlToLines(html) {
  return String(html || "").replace(/<\/(?:p|li|h[1-6])>|<br\s*\/?>/gi, "\n").replace(/<[^>]*>/g, "")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, "\"").replace(/&#x27;|&#39;/g, "'").replace(/&amp;/g, "&")
    .split("\n").map((l) => l.trim()).filter(Boolean);
}

// About four characters to a token: a size to judge by, not a count the provider will bill.
export const tokens = (text) => Math.ceil(String(text || "").length / 4);

export const slug = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^[^a-z]+/, "").replace(/-+$/g, "").slice(0, 24);

// "Name: x / Menu: y / Where: z / Gets: w / Instructions: ..." -> the fields, or null when the shape is not there.
export function parseDescribe(lines) {
  const got = {}; let key = "";
  for (const l of lines) {
    const m = /^(name|menu|where|gets|instructions)\s*:\s*(.*)$/i.exec(l);
    if (m) { key = m[1].toLowerCase(); got[key] = m[2].trim(); }
    else if (key === "instructions") got.instructions += "\n" + l;
  }
  if (!got.name || !got.menu || !got.instructions) return null;
  const name = slug(got.name);
  if (!name) return null;
  const where = String(got.where || "").toLowerCase().replace(/[^a-z]/g, ""), gets = String(got.gets || "").toLowerCase().replace(/[^a-z]/g, "");
  return { name, menu: got.menu.replace(/^["']|["']$/g, ""), text: got.instructions, scope: SCOPES.includes(where) ? where : "anywhere", result: RESULTS.includes(gets) ? gets : "answer" };
}

// "Clear: ... / Reads: ... / Changes: ..." -> {clear, reads, changes}, or null.
export function parseCheck(lines) {
  const got = {};
  for (const l of lines) { const m = /^(clear|reads|changes)\s*:\s*(.+)$/i.exec(l); if (m) got[m[1].toLowerCase()] = m[2].trim(); }
  return got.clear && got.reads && got.changes ? got : null;
}

// The menu line: the first line, without quotation marks.
export const menuLine = (lines) => (lines[0] || "").replace(/^["'“‘]+|["'”’]+$/g, "").trim();

export const addedLines = (changes) => (Array.isArray(changes) ? changes : []).filter((c) => c && c.op === "add").map((c) => String(c.text).trim()).filter(Boolean);
