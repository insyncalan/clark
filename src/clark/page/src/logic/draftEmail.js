// The Draft email editor's logic (#50; FR-44, FR-45). Plain functions, no DOM state and no Preact, so a test can run them alone.
// The wording of the email is built by the draft_email module (plain code, no model); this file holds only what the editor
// itself needs: the three kinds, the ticks, the options to ask the builder with, the words of the editor, what goes on the
// clipboard, and the entry "I sent it" hands to the history. Nothing here sends mail, makes an Outlook draft or saves.

export const MODES = [
  { mode: "update_request", label: "Update request" },
  { mode: "chase", label: "Chase" },
  { mode: "decision", label: "Decision" },
];
// The tone of a chase (#452): the three steps, in the prototype's words (draft_email.TONE_NAMES says the same; a test holds them
// together). They are labels on the editor's buttons only: no tone word is ever put in the email.
export const TONES = [
  { tone: 0, label: "First chase" },
  { tone: 1, label: "Second chase" },
  { tone: 2, label: "Firmer chase" },
];
export const CHOOSE_A_KIND = "That kind of email isn't available. Choose Update request, Chase or Decision.";
export const NOTHING_SAVED = "Nothing was saved.";
export const NOTHING_TO_RECORD = "Tick at least one item before you press I sent it. " + NOTHING_SAVED;
export const COPY_REFUSED = "The browser did not copy it. Press ⌘C to copy the selected text.";
export const NO_OPEN_ITEMS = "There are no open items to put in an email.";
export const NO_ADDRESS = "No address yet. Add one in your mail app.";
export const COPIED = "Copied";
export const NO_BUILDER = "The email could not be drafted. Close this and open it again.";
export const MAIL_TOO_LONG = "This email is too long for a mail link. Use Copy for Outlook or Copy as text.";
export const LABELS = {
  title: "Draft email",
  kind: "Kind of email",
  to: "To",
  subject: "Subject",
  tone: "Tone",
  items: "Items in the email",
  replyBy: "Reply by",
  unblocks: "What is this holding up? (optional)",
  includeUpdate: "Include the latest update on each item",
  copyOutlook: "Copy for Outlook",
  copyText: "Copy as text",
  mail: "Open in mail app",
  sent: "I sent it",
  close: "Close",
  edit: "You can edit the wording below before you copy it.",
};

const SENT_KIND = "email_sent";
const MAX_IDS = 50;

function text(x) { return x == null ? "" : String(x); }
function modeKnown(mode) { return MODES.some((m) => m.mode === mode); }

/** The label of a kind, or the plain choice message when the kind is unknown. */
export function modeLabel(mode) {
  const m = MODES.find((x) => x.mode === mode);
  return m ? m.label : CHOOSE_A_KIND;
}

/** The ticks the editor starts with: the builder's own choice (default_picked) when given, else every offered item. */
export function startPicks(items, picked) {
  const all = (items || []).map((i) => i.id);
  if (!Array.isArray(picked)) return all;
  const known = new Set(all);
  return picked.filter((id) => known.has(id));
}

/** Tick or untick one item; a new array, the order of the offered items kept. */
export function togglePick(items, picked, id) {
  const on = new Set(picked || []);
  if (on.has(id)) on.delete(id); else on.add(id);
  return (items || []).map((i) => i.id).filter((x) => on.has(x));
}

/** The words under the item list: how many are ticked ("1 item ticked", "2 of 3 items ticked"); nothing when no item is offered
 *  (the page then shows NO_OPEN_ITEMS instead). The next step for none ticked is said once, in the alert, not here. */
export function pickWords(n, of) {
  if (!of) return "";
  const noun = (k) => (k === 1 ? "item" : "items");
  return n === of ? `${n} ${noun(n)} ticked` : `${n} of ${of} ${noun(of)} ticked`;
}

/** The note after I sent it: what was recorded and the day (DD-MM-YYYY), and whether the history has it. */
export function sentWords(entry, saved = false, failed = false) {
  const n = (entry.ids || []).length;
  const [y, m, d] = text(entry.date).split("-");
  if (failed) return "That could not be saved to the history. Try again. " + NOTHING_SAVED;
  const items = `${n} ${n === 1 ? "item" : "items"}`;
  if (saved) return `Recorded: ${items} marked as sent on ${d}-${m}-${y}. It is in the history.`;      // only after the save worked
  return `Marked as sent for ${items} on ${d}-${m}-${y}. It is not saved to the history yet.`;
}

/** The tone the user picked, or null when none (the history of earlier chases decides): a whole number 0, 1 or 2 only. */
export function toneOf(tone) {
  return Number.isInteger(tone) && tone >= 0 && tone <= 2 ? tone : null;
}

/** What is said under the tone buttons about earlier chases: "chased 2 times before", "not chased yet" (the prototype's words). */
export function chasedWords(n) {
  const k = Number.isInteger(n) && n > 0 ? n : 0;
  return k ? `chased ${k} time${k > 1 ? "s" : ""} before` : "not chased yet";
}

/** The line under the editor's title, in the prototype's words (system/prototype/peek.js): what kind of email this is, how often a
 *  chase has been sent before, and that clark never sends it. An unknown kind says nothing (the editor names the choice elsewhere). */
export const NEVER_SENDS = "clark never sends it: copy it into Outlook.";
export function subLine(mode, chased) {
  const kind = { update_request: "An update request", chase: `A chase · ${chasedWords(chased)}`, decision: "A decision request" }[mode];
  return kind ? `${kind}. ${NEVER_SENDS}` : "";
}

/** What a person reads when "I sent it" got no message of the server's own (a fault, no answer, an old page): by the status of the
 *  reply (0 for none), each ending "Nothing was saved." and saying what to do next. */
export function sentFailedWords(status) {
  const tail = " " + NOTHING_SAVED;
  if (status === 0) return "clark did not answer. Start it again from clark.command, then try again." + tail;
  if (status === 403) return "This page is out of date. Reload the page and try again." + tail;
  if (status === 500) return "A problem came up recording that. Try again. If it happens again, restart clark." + tail;
  if (status === 503) return "That could not be recorded just now. Wait a moment and try again. If it keeps happening, restart clark." + tail;
  return "That could not be recorded. Reload the page and try again." + tail;
}

/** What the builder is asked with each time something changes. Only the editor's own inputs; the caller adds the items, the
 *  recipient, the sender, the clock and the settings. An unknown kind is refused in plain words (never sent on). */
export function buildOptions(state) {
  const mode = text(state.mode) || "update_request";
  if (!modeKnown(mode)) throw new Error(CHOOSE_A_KIND);
  const out = {
    mode,
    picked: Array.isArray(state.picked) ? state.picked.slice() : [],
    reply_by: text(state.replyBy),
    unblocks: text(state.unblocks).trim(),
    include_update: !!state.includeUpdate,
  };
  const tone = toneOf(state.tone);
  if (mode !== "update_request" && tone !== null) out.tone = tone;     // only a chase or a decision has a tone; none picked is left out
  return out;
}

/** The note shown under the preview, and never in the email, for a ticked item that is not marked for the client. */
export function internalNote(ids) {
  const list = Array.from(new Set(ids || []));
  if (!list.length) return "";
  return `Marked internal: ${list.join(", ")}. ${list.length === 1 ? "It is" : "They are"} in this email, so untick ${list.length === 1 ? "it" : "them"} before you copy if the recipient should not see ${list.length === 1 ? "it" : "them"}.`;
}

/** Copy is blocked while the draft has a problem to fix first; the first problem is the words to show. */
export function blocked(draft) {
  const p = draft && Array.isArray(draft.problems) ? draft.problems : [];
  return p.length ? p[0] : "";
}

/** Elements and attributes that an email from the builder can carry (inline styles only). Anything else is dropped before
 *  the preview is drawn, so a draft handed in from elsewhere can never run a script or load a picture. */
const TAGS = new Set(["DIV", "P", "B", "I", "STRONG", "EM", "BR", "TABLE", "TBODY", "THEAD", "TR", "TD", "TH"]);
const ATTRS = new Set(["style", "align", "cellpadding", "cellspacing", "border", "colspan"]);

/** The email's HTML with everything outside the allowed elements and attributes removed (the text of a removed element goes
 *  with it when it is a script or style). Returns a string. */
export function safeHtml(html, parse) {
  const doc = (parse || ((s) => new DOMParser().parseFromString(s, "text/html")))(`<body>${text(html)}</body>`);
  const walk = (node) => {
    for (const child of Array.from(node.childNodes)) {
      if (child.nodeType === 3) continue;
      if (child.nodeType !== 1) { node.removeChild(child); continue; }
      if (!TAGS.has(child.tagName)) {
        if (/^(SCRIPT|STYLE|IFRAME|OBJECT|EMBED)$/.test(child.tagName)) { node.removeChild(child); continue; }
        walk(child);
        while (child.firstChild) node.insertBefore(child.firstChild, child);
        node.removeChild(child);
        continue;
      }
      for (const a of Array.from(child.attributes)) {
        const bad = !ATTRS.has(a.name) || (a.name === "style" && /url\s*\(|expression|@import/i.test(a.value));
        if (bad) child.removeAttribute(a.name);
      }
      walk(child);
    }
  };
  walk(doc.body);
  return doc.body.innerHTML;
}

/** The plain text for Copy as text: a Subject line first (the builder's text has none), then the email. */
export function textWithSubject(draft, bodyText) {
  const body = bodyText == null ? text(draft.text) : text(bodyText);
  return `Subject: ${text(draft.subject)}\n\n${body}`;
}

/** What each copy button puts on the clipboard, or the plain words why it cannot yet. `edited` is what the preview holds now
 *  ({html, text}) when the wording was changed there, else the builder's own. */
export function copyPayload(which, draft, edited) {
  const why = blocked(draft);
  if (why) throw new Error(why);
  // Wording changed in the preview may hold markup pasted in from a page or a document: it is cleaned like the drawn preview.
  const html = edited && edited.html != null ? safeHtml(edited.html) : text(draft.html);
  const plain = edited && edited.text != null ? text(edited.text) : text(draft.text);
  if (which === "outlook") return { "text/html": html, "text/plain": plain };
  if (which === "text") return { "text/plain": textWithSubject(draft, plain) };
  throw new Error("Choose Copy for Outlook or Copy as text.");
}

/** Copy to the clipboard (injected, so a test can refuse it): the words to show under the preview, and whether it worked.
 *  Never throws and never fails silently: a refused clipboard gives the fall-back (the caller then selects the preview). */
export async function copyNow(which, draft, edited, clip) {
  let payload;
  try { payload = copyPayload(which, draft, edited); } catch (e) { return { ok: false, blocked: true, message: e.message }; }
  try {
    await clip(payload);
    return { ok: true, message: COPIED };
  } catch (e) {
    return { ok: false, blocked: false, message: COPY_REFUSED };
  }
}

/** The real clipboard: both types for Outlook, one for text. Rejects when the browser refuses. */
export function browserClip(payload) {
  const nav = typeof navigator !== "undefined" ? navigator : null;
  if (!nav || !nav.clipboard) return Promise.reject(new Error("no clipboard"));
  if (payload["text/html"] != null && typeof ClipboardItem !== "undefined" && nav.clipboard.write) {
    const item = {};
    for (const k of Object.keys(payload)) item[k] = new Blob([payload[k]], { type: k });
    return nav.clipboard.write([new ClipboardItem(item)]);
  }
  return nav.clipboard.writeText(payload["text/plain"]);
}

/** The longest finished (encoded) mail link every mail app keeps whole; the same number as draft_email.MAILTO_LIMIT. A space is
 *  3 characters in a link and a line break 6, so the plain text's length says nothing about it. */
export const MAILTO_LIMIT = 2000;

/** A header line (To, Subject): control characters and line breaks become a space, white space is collapsed (as draft_email.one_line). */
export function oneLine(x) {
  return text(x).replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/g, " ").split(/\s+/).filter(Boolean).join(" ");
}

/** The mail link for Open in mail app, only when the finished link fits MAILTO_LIMIT; else the words. */
export function mailLink(draft, limit) {
  if (blocked(draft)) return { href: "", message: blocked(draft) };
  const href = `mailto:${encodeURIComponent(oneLine(draft.to))}?subject=${encodeURIComponent(oneLine(draft.subject))}&body=${encodeURIComponent(text(draft.text))}`;
  if (href.length > (limit || MAILTO_LIMIT)) return { href: "", message: MAIL_TOO_LONG };
  return { href, message: "" };
}

/** The entry "I sent it" hands to the history: the kind, the item ids (once each, at most 50), the day (YYYY-MM-DD) and the
 *  kind of email, never the email's text. Throws in plain words when nothing is ticked or the kind is unknown. The caller
 *  saves it as one undoable step (#31's path; not built here). */
export function sentEntry(ids, mode, day) {
  if (!modeKnown(mode)) throw new Error(`${CHOOSE_A_KIND} ${NOTHING_SAVED}`);
  const seen = Array.from(new Set((ids || []).filter((i) => typeof i === "string" && i.trim()))).slice(0, MAX_IDS);
  if (!seen.length) throw new Error(NOTHING_TO_RECORD);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text(day))) throw new Error("The date for this record is missing. Reload the page and try again. " + NOTHING_SAVED);
  return { kind: SENT_KIND, ids: seen, date: day, mode };
}
