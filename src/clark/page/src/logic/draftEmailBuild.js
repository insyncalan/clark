// The Draft email builder, in the page (#51; BRD FR-94, FR-95): the same wording and rules as src/clark/draft_email.py, run in
// the browser so a published file needs no server and no model. tests/test_client_email.py builds the same email in both and
// compares them, so the two cannot drift. It reads and writes nothing: it takes the items, the options and the time and
// returns {to, subject, html, text, items, tone, mode, ids, internal_ids, problems, ready}. Nothing here sends mail.
//
// An item is {id, project, kind ("actions"|"raid"|"decisions"), text, due, priority, owner, type, response, update, status,
// client_visible, sensitive, hidden}. Only those words can reach an email; itemsOf() builds them from the PUBLISHED rows,
// so an internal note, a hidden row or anything unpublished is not in the page to be drafted from.

const UPDATE_REQUEST = "Up" + "date request";            // the subject word; joined from parts as the Python module does
const MODES = ["update_request", "chase", "decision"];
const TONES = 3;
const DUE_SOON_DAYS = 7;
const HELD_WORDS = ["confidential", "restricted"];
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
export const NO_SENDER = "Add your name in Settings › Profile so it signs the email.";
export const NO_SENDER_HERE = "Add your name above so it signs the email.";     // on a published page, which has no Settings (opts.sender_words)
export const NOTHING_TICKED = "No items are ticked. Tick at least one to draft the email.";
export const NO_OPEN = "There are no open items to put in an email.";
const COLOURS = { red: "#B3261E", amber: "#8A5A00", ink: "#1E1F1E", muted: "#5C5D60", head: "#F1F3F4", rule: "#D9D9E0", white: "#FFFFFF" };
const FONT = "font-family:Calibri,Arial,sans-serif;font-size:11pt;";
const OPEN = "I'm pulling together where things stand on the items below.";
const ASK = "Could you let me know where each one stands, and flag anything that's blocking you or that you need from me?";
const DECIDE = "Where an item is a decision we need from you, could you let me know what you have decided?";
const THANKS = " Thank you.";
const SIGN_OFF = { update_request: "Kind regards,", chase: "Kind regards,", decision: "Thank you," };
const CHASE = {
  subjects: ["Reminder", "Second reminder", "Reply needed"],
  asks: ["Could you let me know where each one stands, and when I can expect it?",
    "Could you let me have an update on each, and a date for anything still open?",
    "Please reply with a firm date for each, or tell me what is blocking any of them, so that we can resolve it together."],
  one_asks: ["Could you let me know where it stands, and when I can expect it?",
    "Could you let me have an update, and a date for it?",
    "Please reply with a firm date, or tell me what is blocking it, so that we can resolve it together."],
};
const DECISION = { subjects: ["Decision needed", "Decision needed (second reminder)", "Decision needed"],
  ask: "Could you let me have the decision, or tell me what you need to make it, by {reply_by}?" };

// ---- reading text the way a person reads it (confusables.skeleton) ----
const LOOK = (() => {
  const keys = "0410 0412 0415 041a 041c 041d 041e 0420 0421 0422 0425 0405 0406 0408 04c0 0474 051a 051c 04ae 0430 0435 043e 0440 0441 0443 0445 0455 0456 0458 0501 04bb 0475 051b 051d 0461 043a 0391 0392 0395 0396 0397 0399 039a 039c 039d 039f 03a1 03a4 03a5 03a7 03f9 037f 03b1 03bf 03c1 03bd 03b9 03ba 03c5 03c7 03f2 03f3 0585 0578 057d 0581 0566 0570 0575 0555 054d a4ee a4d0 a4d1 a4d3 a4d4 a4d6 a4d7 a4d9 a4da a4dc a4dd a4df a4e0 a4e1 a4e2 a4e3 a4e6 a4e7 a4ea a4eb a4ec a4f0 a4f2 a4f3 a4f4 13aa 13f4 13df 13a0 13ac 13bb 13c0 13ab 13e6 13b7 13e2 13d2 13da 13a2 13d9 13b3 13c3 13de 1d00 0299 1d04 1d05 1d07 a730 0262 029c 026a 1d0a 1d0b 029f 1d0d 0274 1d0f 1d18 0280 a731 1d1b 1d1c 1d20 1d21 028f 1d22 0131 0237 01c0 0269 0251 0261 01bf".split(" "), vals = "ABEKMHOPCTXSIJIVQWYaeopcyxsijdhvqwwkABEZHIKMNOPTYXCJaopvikuxcjonugqhjOUABPDTGKJCZFMNLSRVHWXYEIOUABCDEHGJKMPRSTVWZLABCDEFGHIJKLMNOPRSTUVWYZijlIagp", m = new Map();
  keys.forEach((k, i) => { if (!m.has(parseInt(k, 16))) m.set(parseInt(k, 16), vals[i]); });
  return m;
})();
const DASHES = "‐‑‒–—―−﹘﹣－";
const IGNORABLE = [[0xAD, 0xAD], [0x34F, 0x34F], [0x61C, 0x61C], [0x115F, 0x1160], [0x17B4, 0x17B5], [0x180B, 0x180F], [0x200B, 0x200F],
  [0x202A, 0x202E], [0x2060, 0x206F], [0x3164, 0x3164], [0xFE00, 0xFE0F], [0xFEFF, 0xFEFF], [0xFFA0, 0xFFA0], [0xFFF0, 0xFFF8],
  [0x1BCA0, 0x1BCA3], [0x1D173, 0x1D17A], [0xE0000, 0xE0FFF]];
// Controls other than tab, line feed and carriage return, noncharacters (U+FDD0 to U+FDEF, the last two of every plane) and lone surrogates.
const CONTROLS = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f﷐-﷯]|[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]|\p{Cs}|[\u{fffe}\u{ffff}\u{1fffe}\u{1ffff}\u{2fffe}\u{2ffff}\u{3fffe}\u{3ffff}\u{4fffe}\u{4ffff}\u{5fffe}\u{5ffff}\u{6fffe}\u{6ffff}\u{7fffe}\u{7ffff}\u{8fffe}\u{8ffff}\u{9fffe}\u{9ffff}\u{afffe}\u{affff}\u{bfffe}\u{bffff}\u{cfffe}\u{cffff}\u{dfffe}\u{dffff}\u{efffe}\u{effff}\u{ffffe}\u{fffff}\u{10fffe}\u{10ffff}]/gu;
const LINE_LIKE = "\x0b\x0c\x1c\x1d\x1e\x85";
const IGNORED = new Set();
for (const [a, b] of IGNORABLE) for (let c = a; c <= b; c++) IGNORED.add(c);

function unseen(t) {
  t = t.replace(CONTROLS, (m) => (LINE_LIKE.includes(m) ? "\n" : ""));
  let out = "";
  for (const ch of t) {
    const cp = ch.codePointAt(0);
    if (IGNORED.has(cp) || /^\p{Cf}$/u.test(ch)) continue;
    out += cp === 0x2800 ? " " : ch;
  }
  return out;
}
function unmarked(t) { return t.normalize("NFKD").replace(/\p{M}/gu, ""); }
function looks(t) { let o = ""; for (const ch of t) { const v = LOOK.get(ch.codePointAt(0)); o += v === undefined ? ch : v; } return o; }
function dashes(t) { let o = ""; for (const ch of t) o += DASHES.includes(ch) ? "-" : ch; return o; }
/** The text as every restricted-text scan reads it (confusables.skeleton). */
export function skeleton(text) {
  let t = looks(unseen(String(text == null ? "" : text)));
  t = looks(unmarked(t)).normalize("NFKC");
  t = dashes(looks(unseen(t)));
  return t.normalize("NFKC");
}

// ---- small helpers ----
function str(x) { return x == null ? "" : String(x); }
function esc(s) { return str(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#x27;"); }
export function oneLine(x) { return str(x).replace(/[\p{Cc}\u2028\u2029]/gu, " ").split(/\s+/).filter(Boolean).join(" "); }
function parseIso(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(str(iso));
  if (!m) return null;
  const t = Date.UTC(+m[1], +m[2] - 1, +m[3]), d = new Date(t);
  return d.getUTCFullYear() === +m[1] && d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[3] ? t : null;
}
const DAY = 86400000;
export function shown(iso) { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(str(iso)); return m && parseIso(iso) !== null ? `${m[3]}-${m[2]}-${m[1]}` : str(iso); }
export function weekdayDate(iso) { const t = parseIso(iso); return t === null ? "" : `${WEEKDAYS[(new Date(t).getUTCDay() + 6) % 7]} ${shown(iso)}`; }
function chars(s) { return Array.from(s); }
export function short(text, limit = 60) {
  text = oneLine(text);
  const c = chars(text);
  if (c.length <= limit) return text;
  let cut = c.slice(0, limit - 1).join("");
  if (c[limit - 1] !== " " && cut.includes(" ")) cut = cut.slice(0, cut.lastIndexOf(" "));
  return cut.replace(/[ ,;:.\-]+$/, "") + "…";
}
const times = (n) => (n === 1 ? "once" : n === 2 ? "twice" : `${n} times`);
export function greeting(hour, first = "") { return `Good ${hour < 12 ? "morning" : hour < 18 ? "afternoon" : "evening"}${first ? ", " + first : ""},`; }
export function dueInfo(due, today, kind = "actions", soon = DUE_SOON_DAYS) {
  if (!due) return { date: "No date", words: "", level: "" };
  const a = parseIso(due), b = parseIso(today);
  if (a === null || b === null) return { date: str(due), words: "", level: "" };
  const n = Math.round((a - b) / DAY);
  if (n < 0) return { date: shown(due), words: `${-n} day${n === -1 ? "" : "s"} overdue`, level: "over" };
  if (n > soon) return { date: shown(due), words: "", level: "" };
  const verb = kind === "decisions" ? "needed" : "due";
  return { date: shown(due), level: "soon", words: n === 0 ? `${verb} today` : n === 1 ? `${verb} tomorrow` : `${verb} in ${n} days` };
}
function rank(i, today) { const d = i.due || ""; return [d && d < today ? 0 : d ? 1 : 2, d || "9999", i.id || ""]; }
export function sortItems(items, today) {
  return items.slice().sort((x, y) => { const a = rank(x, today), b = rank(y, today); for (let k = 0; k < 3; k++) { if (a[k] < b[k]) return -1; if (a[k] > b[k]) return 1; } return 0; });
}

// ---- who and what may go in an email ----
export function host(address) { const p = str(address).split("@"); return p.length > 1 ? p[1].trim().toLowerCase() : ""; }
export function isOutside(address, own) { const h = host(address); return !h || !(own || []).map((d) => str(d).trim().toLowerCase()).includes(h); }
export function barred(item, outside = true) {
  if (item.hidden) return true;
  const said = skeleton(["text", "response", "update"].map((k) => str(item[k])).join(" ")).toLowerCase();
  if (HELD_WORDS.some((w) => said.includes(skeleton(w).toLowerCase()))) return true;
  return !!(outside && item.sensitive);
}
export function openItems(items) {
  const done = ["closed", "done", "cancelled", "dropped", "resolved", "decided", "withdrawn"];
  return items.filter((i) => !done.includes(str(i.status).trim().toLowerCase()));
}
export const isInternal = (item) => !item.client_visible;

// ---- chase counts and tone ----
export function toneFor(ids, counts) { return Math.min(Math.max(0, ...ids.map((i) => ((counts || {})[i] || {}).n || 0)), TONES - 1); }
function perItem(items, counts) { return items.map((i) => { const r = (counts || {})[i.id] || {}; return [r.n || 0, r.n ? r.last || "" : ""]; }); }
const same = (per) => new Set(per.map((p) => p.join("\u0000"))).size <= 1;

function subjectOf(mode, items, today, tone, names, replyBy) {
  names = names || {};
  const codes = Array.from(new Set(items.map((i) => i.project || ""))).sort();
  let lead = oneLine(codes.map((c) => names[c] || c).join(" / "));
  lead = lead ? `${lead} · ` : "";
  if (mode === "decision") {
    if (tone === 2) { const when = weekdayDate(replyBy); return when ? `${lead}Decision needed: reply by ${when}` : `${lead}Decision still needed`; }
    return `${lead}${DECISION.subjects[tone]}` + (items.length === 1 ? `: ${short(items[0].text)}` : "");
  }
  const word = mode === "update_request" ? UPDATE_REQUEST : CHASE.subjects[tone];
  if (!items.length) return word;
  if (items.length === 1) return `${lead}${oneLine(items[0].id)} · ${word}: ${short(items[0].text)}`;
  const over = items.filter((i) => i.due && i.due < today).length;
  if (mode === "chase") return over === items.length ? `${lead}${word}: ${items.length} overdue items` : `${lead}${word}: ${items.length} items` + (over ? ` (${over} overdue)` : "");
  return `${lead}${word}: ${items.length} open items` + (over ? ` (${over} overdue)` : "");
}
function daysLate(item, today) { const a = parseIso(item.due), b = parseIso(today); return item.due && today && item.due < today && a !== null && b !== null ? Math.round((b - a) / DAY) : 0; }
const plural = (n) => `${n} day${n === 1 ? "" : "s"}`;
function history(per, items, asked = "chased") {
  if (!per.some((p) => p[0])) return "";
  const last = per.reduce((m, p) => (p[1] > m ? p[1] : m), "");
  const since = last ? `, most recently on ${shown(last)}` : "";
  if (same(per)) {
    return asked === "chased" ? `I have chased ${items.length === 1 ? "it" : "them"} ${times(per[0][0])}${since}.`
      : `I have asked for ${items.length === 1 ? "this decision" : "these decisions"} ${times(per[0][0])}${since}.`;
  }
  return asked === "chased" ? `I have chased some of them before${since}.` : `I have asked for some of these decisions before${since}.`;
}
function opening(mode, items, tone, per, unblocks, today) {
  unblocks = str(unblocks).trim();
  if (mode === "update_request") return OPEN;
  const late = items.filter((i) => daysLate(i, today));
  const longest = Math.max(0, ...items.map((i) => daysLate(i, today)));
  const uniform = same(per), one = items.length === 1;
  const last = per.length && uniform ? per[0][1] : "";
  const dueOf = (i) => (i.due ? shown(i.due) : "");
  if (mode === "chase") {
    if (tone === 0) {
      if (one) { const due = dueOf(items[0]); return late.length ? "A quick reminder about the item below, which is now past its due date." : due ? `A quick reminder about the item below, which is due on ${due}.` : "A quick reminder about the item below."; }
      return late.length === items.length ? "A quick reminder about the items below, which are now past their due dates." : late.length ? "A quick reminder about the items below, some of which are past their due dates." : "A quick reminder about the items below.";
    }
    if (tone === 1) {
      const what = one ? "item" : "items";
      const state = late.length === items.length ? `, which ${one ? "is" : "are"} still overdue` : late.length ? ", some of which are still overdue" : one && items[0].due ? `, which is due on ${shown(items[0].due)}` : "";
      if (uniform) return `I'm following up on my earlier note${last ? " of " + shown(last) : ""} about the ${what} below${state}.`;
      return `I'm following up on the ${what} below${state}. ${history(per, items)}`.trim();
    }
    let lead;
    if (one) { const due = dueOf(items[0]); lead = late.length ? `This item is now ${plural(longest)} overdue.` : due ? `This item is due on ${due}.` : ""; }
    else lead = late.length === items.length ? `These items are now well overdue, the longest by ${plural(longest)}.` : late.length ? `Some of these items are now well overdue, the longest by ${plural(longest)}.` : "I'm writing again about the items below.";
    let text = `${lead} ${history(per, items)}`.trim();
    if (unblocks) text += one ? ` It is holding up ${unblocks}.` : ` They are holding up ${unblocks}.`;
    return text;
  }
  const needed = unblocks && tone === 0 ? `, which is needed for ${unblocks}` : unblocks ? `; it is needed for ${unblocks}` : "";
  if (tone === 0) return `A quick note on the decision below${needed}.`;
  if (tone === 1) {
    if (uniform) return `I'm following up on my earlier note${last ? " of " + shown(last) : ""} about the decision below${needed}.`;
    return `I'm following up on the decision below${needed}. ${history(per, items, "asked")}`;
  }
  return history(per, items, "asked") + (unblocks ? ` It is holding up ${unblocks}.` : "");
}
function askOf(mode, items, tone, replyBy) {
  const w = weekdayDate(replyBy), reply = w ? ` It would be helpful to hear back by ${w}.` : "";
  if (mode === "update_request") return `${ASK}${items.some((i) => i.kind === "decisions") ? " " + DECIDE : ""}${reply}${THANKS}`;
  if (mode === "chase") return `${(items.length === 1 ? CHASE.one_asks : CHASE.asks)[tone]}${reply}${THANKS}`;
  return DECISION.ask.replace("{reply_by}", w || "").replace("by ?", "as soon as you can?");
}
function what(item) {
  if (item.kind === "decisions") return "Decision needed: " + str(item.text);
  if (item.kind === "raid") return `${item.type || "Risk"}: ${str(item.text)}`;
  return str(item.text);
}
function lines(item, includeUpdate) {
  const out = [];
  if (item.kind === "raid") out.push("Response: " + (str(item.response).trim() || "none recorded yet"));
  const u = str(item.update).trim();
  if (includeUpdate && u) out.push("Latest update: " + u);
  return out;
}

// ---- HTML (inline styles only) ----
const p = (inner, extra = "") => `<p style="${FONT}color:${COLOURS.ink};margin:0 0 12px 0;${extra}">${inner}</p>`;
const head = (t) => `<p style="${FONT}color:${COLOURS.ink};margin:16px 0 6px 0;"><b style="font-weight:bold;">${esc(t)}</b></p>`;
const td = (inner, extra = "", colour) => `<td style="${FONT}color:${colour || COLOURS.ink};border-bottom:1px solid ${COLOURS.rule};padding:6px 8px;vertical-align:top;${extra}">${inner}</td>`;
const th = (t, width = "") => `<th align="left" style="${FONT}color:${COLOURS.ink};background:${COLOURS.head};border-bottom:1px solid ${COLOURS.rule};padding:6px 8px;text-align:left;font-weight:bold;${width ? "width:" + width + ";" : ""}">${t}</th>`;
const muted = (t) => `<i style="font-style:normal;color:${COLOURS.muted};">${esc(t)}</i>`;
function rowHtml(item, today, includeUpdate) {
  const d = dueInfo(item.due, today, item.kind || "actions");
  const colour = d.level === "over" ? COLOURS.red : d.level === "soon" ? COLOURS.amber : COLOURS.ink;
  const strong = d.level === "over" ? "font-weight:bold;" : "";
  let w = esc(what(item));
  if (item.kind === "raid" || item.kind === "decisions") {
    const full = what(item), at = full.indexOf(": ");
    w = `<b style="font-weight:bold;">${esc(full.slice(0, at))}:</b> ${esc(full.slice(at + 2))}`;
  }
  const extra = lines(item, includeUpdate).map((x) => "<br>" + muted(x)).join("");
  const pr = item.priority || "";
  const prio = pr === "Urgent" ? '<b style="font-weight:bold;">Urgent</b>' : esc(pr);
  const due = esc(d.date) + (d.words ? `<br>${esc(d.words)}` : "");
  return `<tr style="vertical-align:top;">${td(esc(item.id), "white-space:nowrap;")}${td(w + extra)}${td(due, "white-space:nowrap;" + strong, colour)}${td(prio, "white-space:nowrap;")}</tr>`;
}
function tableHtml(items, today, includeUpdate) {
  return `<table cellpadding="6" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;${FONT}color:${COLOURS.ink};"><tr style="vertical-align:top;">${th("ID", "9%")}${th("Item")}${th("Due", "18%")}${th("Priority", "10%")}</tr>${items.map((i) => rowHtml(i, today, includeUpdate)).join("")}</table>`;
}
function textRows(items, today, includeUpdate) {
  const width = Math.max(0, ...items.map((i) => i.id.length)), pad = " ".repeat(width), out = [];
  for (const i of items) {
    const d = dueInfo(i.due, today, i.kind || "actions");
    out.push(`  ${i.id.padEnd(width)}  ${what(i)}  |  ${d.date}${d.words ? ` (${d.words})` : ""}  |  ${i.priority || ""}`);
    for (const x of lines(i, includeUpdate)) out.push(`  ${pad}  ${x}`);
  }
  return out;
}

/** The email for the items ticked (draft_email.build). opts: mode, items, picked (null: all), name, first, email, own_domains,
 *  from, now ("YYYY-MM-DD HH:MM"), include_update, reply_by, chased, project_names, unblocks, cover. */
export function build(opts) {
  const mode = opts.mode || "update_request";
  if (!MODES.includes(mode)) throw new Error("That kind of email isn't available. Choose Update request, Chase or Decision.");
  const now = str(opts.now), today = now.slice(0, 10), hour = now.length >= 13 ? parseInt(now.slice(11, 13) || "0", 10) : 0;
  const outside = isOutside(opts.email, opts.own_domains), picked = opts.picked;
  let items = (opts.items || []).filter((i) => !barred(i, outside) && (picked == null || picked.includes(i.id)));
  items = sortItems(items, today);
  const internalIds = items.filter((i) => outside && isInternal(i)).map((i) => i.id), ids = items.map((i) => i.id);
  const tone = mode !== "update_request" ? toneFor(ids, opts.chased) : 0;
  const per = perItem(items, opts.chased);
  const first = str(opts.first || str(opts.name).split(" ")[0]).trim(), names = opts.project_names || {}, inc = !!opts.include_update;
  const open = str(opts.cover).trim() || opening(mode, items, tone, per, str(opts.unblocks), today);
  const ask = askOf(mode, items, tone, opts.reply_by || "");
  const sender = (str(opts.from).split(/\s+/).filter(Boolean)[0]) || "";
  const hello = greeting(hour, first);
  const codes = Array.from(new Set(items.map((i) => i.project || ""))).sort();
  const blocks = codes.map((c) => head(names[c] || c) + tableHtml(items.filter((i) => (i.project || "") === c), today, inc)).join("");
  const html = `<div style="${FONT}color:${COLOURS.ink};background:${COLOURS.white};">${p(esc(hello))}${p(esc(open))}${blocks}${p(esc(ask), "margin-top:16px;")}${p(esc(SIGN_OFF[mode]) + "<br>" + esc(sender), "margin-bottom:0;")}</div>`;
  const out = [hello, "", open, ""];
  for (const c of codes) out.push(str(names[c] || c).trim(), ...textRows(items.filter((i) => (i.project || "") === c), today, inc), "");
  out.push(ask, "", SIGN_OFF[mode], sender);
  const offerable = (opts.items || []).some((i) => !barred(i, outside));
  const problems = [...(items.length ? [] : [offerable ? NOTHING_TICKED : NO_OPEN]), ...(sender ? [] : [opts.sender_words || NO_SENDER])];
  const keep = ["id", "project", "kind", "text", "due", "priority", "owner", "type", "response", "update", "status", "client_visible", "sensitive", "hidden"];
  return { to: oneLine(opts.email), internal_ids: internalIds, problems, ready: !problems.length, subject: subjectOf(mode, items, today, tone, names, opts.reply_by || ""),
    html, text: out.join("\n"), items: items.map((i) => Object.fromEntries(keep.filter((k) => k in i).map((k) => [k, i[k]]))), ids, tone, mode };
}

// ---- the published rows as items (FR-94: only what was published) ----
/** The items a client may draft about, from the published data block: its actions, risks and issues and decisions, as the page
 *  shows them. Nothing else of a row is read, so a field the file does not carry cannot reach an email. */
export function itemsOf(data) {
  const code = (data.project || {}).code || "";
  const all = [];
  for (const r of data.actions || []) all.push({ id: r.id, project: code, kind: "actions", text: str(r.description), due: r.due_date || "", priority: r.priority || "", owner: r.owner || "", status: r.status, update: str(r.latest_update), client_visible: 1 });
  for (const r of data.raid || []) all.push({ id: r.id, project: code, kind: "raid", type: str(r.type) ? str(r.type)[0].toUpperCase() + str(r.type).slice(1) : "Risk", text: str(r.description), due: r.due_date || "", priority: r.priority || "", owner: r.owner || "", status: r.status, update: "", response: "", client_visible: 1 });
  for (const r of data.decisions || []) all.push({ id: r.id, project: code, kind: "decisions", text: str(r.decision), due: r.needed_by || "", priority: "", owner: r.made_by || "", status: r.status, update: "", client_visible: 1 });
  return openItems(all).filter((i) => i.id && !["made", "achieved"].includes(str(i.status).trim().toLowerCase()));
}

/** The contact the file carries, or null: a name and an address, both plain one-line text. */
export function contactOf(raw) {
  if (!raw || typeof raw !== "object") return null;
  const name = oneLine(raw.name), email = oneLine(raw.email);
  return /^[^\s@<>(),;:"]+@[^\s@<>(),;:"]+\.[^\s@<>(),;:"]+$/.test(email) ? { name, email } : null;
}
