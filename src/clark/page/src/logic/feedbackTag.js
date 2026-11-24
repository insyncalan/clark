// The Feedback tag's logic (#1298). Plain functions, no DOM and no Preact, so a test can run them alone. The tag sits on the right edge in
// Help and in Settings only; its dialog asks what is wrong or suggested, a kind (Problem, Idea, Question), and adds three lines of context on
// its own (clark's version, the system, the page the user was on). The wording and the mail route are Settings, Feedback's (logic/feedback.js):
// the same address, the same Draft email link rules, nothing sent by clark. No contact line (ruling 17-11).
import { MAILTO_LIMIT, mailLink, oneLine } from "./draftEmail.js";
import { ADDRESS, SUBJECT, LABELS, NOTHING_YET, TOO_LONG, COPIED, COPY_REFUSED } from "./feedback.js";

export { MAILTO_LIMIT, COPIED, COPY_REFUSED };
export const KINDS = ["Problem", "Idea", "Question"];
export const DEFAULT_KIND = "Problem";
export const TAG_LABELS = {
  tag: "Feedback",
  tagAria: "Give feedback",
  title: LABELS.title,
  intro: "Tell us what is wrong or what you would like to see.",
  message: LABELS.message,
  kind: "This is a",
  addedHead: "Added automatically",
  addedNote: "Nothing from your reports is included.",
  mailNote: "Your mail app opens with the message ready and you press send. Nothing is sent by clark itself.",
  mail: LABELS.mail,
  copy: LABELS.copy,
  close: "Close",
};
/** The error under the message box when Copy or Open in your mail app is pressed with nothing written (the 1298 mock-up's words). */
export const EMPTY_SEND = "Please write a line first.";
/** True when a send (copy or mail) has nothing to send: the message is empty or only spaces. */
export function emptySend(form) { return !text(form && form.message).trim(); }
// Settings pages' names (Views.jsx GROUPS); "" is the first page, Projects.
const SETTINGS_NAMES = { "": "Projects", projects: "Projects overview", people: "People", profile: "Profile", folder: "Folder", brand: "Brand and publishing", theme: "Theme", appearance: "Look", reports: "Reports and pages", backups: "Backups", data: "Data", claude: "ask clark", logs: "Logs and diagnostics", version: "Version and updates" };

function text(x) { return x == null ? "" : String(x); }
const kindOf = (k) => (KINDS.includes(k) ? k : DEFAULT_KIND);

/** Whether the tag is drawn: Help, or any Settings page; never in a published file or an as-at view. */
export function tagShown({ view, page, helpOpen, fromFile, past } = {}) {
  if (fromFile || past) return false;
  if (helpOpen) return true;
  return view === "settings";
}

/** The page the user was on, in words, for the added lines. */
export function pageWords({ view, page, helpOpen } = {}) {
  if (helpOpen) return "Help and about";
  if (view === "settings") return `Settings, ${SETTINGS_NAMES[page || ""] || text(page)}`;
  return text(view);
}

/** The macOS line of the server's diagnostics report ("System: macOS 14.5"): the version, or "" when the report has no such line. */
function macVersion(report) {
  const m = /^System: macOS(?: ([^\r\n]*))?$/m.exec(text(report));
  return m && m[1] ? oneLine(m[1]) : "";
}

/** The system in words: on a Mac, "macOS" and the version the server's diagnostics report gives (the browser's text is frozen at 10.15.7, so it is never read for a version); no report or no System line: just "macOS". Else the platform as the browser names it. */
export function systemWords(nav, report) {
  const n = nav || (typeof navigator !== "undefined" ? navigator : {});
  const plat = oneLine((n.userAgentData && n.userAgentData.platform) || n.platform || "");
  if (/mac/i.test(plat) || /Mac OS X/.test(n.userAgent || "")) {
    const v = macVersion(report);
    return v ? `macOS ${v}` : "macOS";
  }
  return plat;
}

/** The three lines the dialog shows and the email carries. */
export function contextLines(ctx) {
  const c = ctx || {};
  return [`Version of clark: ${oneLine(c.version) || "unknown"}`, `System: ${oneLine(c.platform) || "unknown"}`, `Page: ${oneLine(c.page) || "unknown"}`];
}

/** The email's body: the kind, the words, then exactly the context lines. */
export function emailText(form, ctx) {
  return [kindOf(form && form.kind), text(form && form.message).trim(), contextLines(ctx).join("\n")].join("\n\n");
}

const subject = (form) => `${SUBJECT} (${kindOf(form && form.kind)})`;

/** The mail link, only when there are words and the link fits; else the plain words why not. */
export function mail(form, ctx) {
  if (!text(form && form.message).trim()) return { href: "", message: NOTHING_YET };
  const r = mailLink({ to: ADDRESS, subject: subject(form), text: emailText(form, ctx) });
  return r.href ? r : { href: "", message: TOO_LONG };
}

/** What Copy as text puts on the clipboard. */
export function copyText(form, ctx) {
  return `To: ${ADDRESS}\nSubject: ${subject(form)}\n\n${emailText(form, ctx)}`;
}
