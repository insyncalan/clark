// The People card's rules (#454), as plain functions with no DOM and no network: the rows the card draws (the people clark holds, then
// the owner names on the open project's work items and milestones that are not on the list), the count of those who need details, and
// the rows pasted from Excel read, checked and set against the list for the preview. The prototype (system/prototype/views.js,
// "People") is the picture; the rules of an email, a name and the limits are the server's (clark/people.py), repeated here so a bad
// row is named before anything is sent. The server checks again and is the one that decides.

export const ROW_LIMIT = 500;                       // the most rows one paste takes (people.py ROW_LIMIT)
export const TEXT_LIMIT = 200000;                   // the most characters one paste takes (people.py TEXT_LIMIT)
export const NAME_MAX = 120;
export const CELL_MAX = 100;                        // organisation and role
const EMAIL_MAX = 254, LOCAL_MAX = 64;
const EMAIL_BAD = " ,;<>()[]\"'\\?#%`";
const UNSAFE = /[\p{Cc}\p{Cf}\p{Cs}\p{Co}\p{Cn}\p{Zs}\p{Zl}\p{Zp}\s]/u;

export const NONE_TO_ADD = "Nothing to add. Paste rows copied from Excel: name, email, organisation, role.";
export const NOTHING_NEW = "Those details are already in the list.";
export const EMAIL_REFUSED = "That email can't be used: it holds more than one address or a character that isn't allowed. Check the address and try again.";
export const EMAIL_INCOMPLETE = "That email is not complete (no dot after the @). Check the address and try again.";
export const EMAIL_TOO_LONG = "That email is too long. Check the address and try again.";
export const TOO_MANY = `That is more than ${ROW_LIMIT} rows. Paste fewer rows at a time.`;
export const TOO_MUCH = `That is too much text to paste at once. Paste at most ${ROW_LIMIT} rows at a time.`;

export const squash = (text) => String(text == null ? "" : text).normalize("NFKC").split(/\s+/).filter(Boolean).join(" ");
// The key a name is matched on: NFKC, lower case, spaces collapsed. (The server also reads look-alike letters as one; it is the one that decides.)
export const key = (text) => squash(text).toLowerCase();

// One address: a blank is allowed (that is what Needs details is for). Returns {email, problem}.
export function cleanEmail(value) {
  const text = String(value == null ? "" : value).trim().toLowerCase();
  if (!text) return { email: "", problem: "" };
  for (const ch of text) if (EMAIL_BAD.includes(ch) || UNSAFE.test(ch)) return { email: "", problem: EMAIL_REFUSED };
  if (text.length > EMAIL_MAX) return { email: "", problem: EMAIL_TOO_LONG };
  const parts = text.split("@");
  if (parts.length !== 2) return { email: "", problem: EMAIL_REFUSED };
  const [local, domain] = parts;
  if (!local || local.length > LOCAL_MAX || !domain) return { email: "", problem: EMAIL_REFUSED };
  if (!domain.includes(".")) return { email: "", problem: EMAIL_INCOMPLETE };
  if (domain.split(".").some((l) => !l || l.startsWith("-") || l.endsWith("-"))) return { email: "", problem: EMAIL_REFUSED };
  return { email: text, problem: "" };
}

const aliasesOf = (p) => String(p.aliases || "").split(";").map(key).filter(Boolean);

// Who a name points at on the list (live people, by name or alias): [] none, [p] one, [p, q ...] more than one.
export function holders(name, list) {
  const k = key(name);
  return k ? list.filter((p) => !p.archived && (key(p.name) === k || aliasesOf(p).includes(k))) : [];
}

// The rows the card draws: every live person, then each owner name on the project's work items and milestones that is not on the
// list (blank and TBC are no one). Sorted by name. `unlisted` marks an owner who is not a person on the list yet.
export function peopleRows(list, owners) {
  const live = list.filter((p) => !p.archived);
  const rows = live.map((p) => ({ name: p.name, email: p.email || "", org: p.organisation || "", role: p.role || "", id: p.id, unlisted: false }));
  const seen = new Set();
  for (const o of owners) {
    const name = squash(o), k = key(name);
    if (!k || k === "tbc" || seen.has(k) || holders(name, live).length) continue;
    seen.add(k);
    rows.push({ name, email: "", org: "", role: "", id: "", unlisted: true });
  }
  return rows.sort((a, b) => a.name.localeCompare(b.name));
}

export const needDetails = (rows) => rows.filter((r) => !r.email);

// "3 of 7 people need details", "1 of 1 person needs details" (the prototype's line)
export function countLine(need, total) {
  return `${need} of ${total} ${total === 1 ? "person needs" : "people need"} details`;
}

// How many a done paste says: "2 people updated", "1 person updated"
export const doneLine = (n) => `${n} ${n === 1 ? "person" : "people"} updated`;

const isHeading = (cells) => key(cells[0]) === "name" && /mail/i.test(cells[1] || "");

// Rows pasted from Excel (name, email, organisation, role, separated by tabs; a first row of headings is skipped) read against the
// list. Returns {rows, refused, tooMuch}:
//   rows    [{line, name, email, org, role, will: "add" | "update" | "same", problem}] for every non-blank line, in order; `line` is
//           the line of the pasted text (1 is the first), so "Row 4" is the fourth line they pasted; `problem` is "" or a sentence
//           that begins "Row n:" and says what to do next;
//   refused the problems, in order;
//   tooMuch a sentence when the paste is too big to read at all (no rows then), else "".
export function readPaste(text, list) {
  const raw = String(text == null ? "" : text);
  if (raw.length > TEXT_LIMIT) return { rows: [], refused: [TOO_MUCH], tooMuch: TOO_MUCH };
  const lines = raw.split(/\r?\n/).map((l, i) => ({ line: i + 1, cells: l.split("\t").map((c) => c.trim()) })).filter((l) => l.cells.some(Boolean));
  if (lines.length && isHeading(lines[0].cells)) lines.shift();
  if (lines.length > ROW_LIMIT) return { rows: [], refused: [TOO_MANY], tooMuch: TOO_MANY };
  const live = list.filter((p) => !p.archived);
  const rows = [], refused = [], sawEmail = new Map();      // an email to the line that first had it
  for (const { line, cells } of lines) {
    const name = squash(cells[0]), org = squash(cells[2]), role = squash(cells[3]);
    const { email, problem: bad } = cleanEmail(cells[1]);
    const said = (s) => `Row ${line}: ${s}`;
    let problem = "", will = "add";
    const who = holders(name, live);
    if (!name) problem = said("there is no name. Give the person a name, or take the row out.");
    else if (name.length > NAME_MAX) problem = said(`the name is too long (at most ${NAME_MAX} characters). Shorten it and try again.`);
    else if (bad) problem = said(bad.charAt(0).toLowerCase() + bad.slice(1));
    else if (org.length > CELL_MAX) problem = said(`the organisation is too long (at most ${CELL_MAX} characters). Shorten it and try again.`);
    else if (role.length > CELL_MAX) problem = said(`the role is too long (at most ${CELL_MAX} characters). Shorten it and try again.`);
    else if (who.length > 1) problem = said(`more than one person on the list is called ${name}. Change the name to say which one, then paste again.`);
    else {
      const other = email ? live.find((p) => (p.email || "") === email && (!who.length || p.id !== who[0].id)) : null;
      if (other) problem = said(`that email already belongs to ${other.name}. Check the address and try again.`);
      else if (email && sawEmail.has(email)) problem = said(`that email is already on row ${sawEmail.get(email)}. Check the address and try again.`);
    }
    if (!problem) {
      if (email) sawEmail.set(email, line);
      if (who.length === 1) {
        const p = who[0];
        will = (email && email !== (p.email || "")) || (org && org !== (p.organisation || "")) || (role && role !== (p.role || "")) ? "update" : "same";
      }
    }
    rows.push({ line, name, email, org, role, will: problem ? "" : will, problem });
    if (problem) refused.push(problem);
  }
  return { rows, refused, tooMuch: "" };
}

// What the paste will do, in a line: "2 will be added, 1 updated." (only the counts above 0), or "" when there is nothing to do
export function planLine(rows) {
  const n = (w) => rows.filter((r) => r.will === w).length;
  const parts = [];
  if (n("add")) parts.push(`${n("add")} will be added`);
  if (n("update")) parts.push(`${n("update")} will be updated`);
  if (n("same")) parts.push(`${n("same")} already ${n("same") === 1 ? "has" : "have"} these details`);
  return parts.length ? parts.join(", ") + "." : "";
}

// The rows to send: only what the server takes, in the order pasted
export const toSend = (rows) => rows.filter((r) => r.will === "add" || r.will === "update")
  .map((r) => ({ name: r.name, email: r.email, organisation: r.org, role: r.role }));
