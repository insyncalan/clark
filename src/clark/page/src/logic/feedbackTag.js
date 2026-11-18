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
// Settings pages' names (Views.jsx GROUPS); "" is the first page, Projects.
const SETTINGS_NAMES = { "": "Projects", projects: "Projects", people: "People", profile: "Profile", folder: "Folder", brand: "Brand", theme: "Theme", appearance: "Appearance", reports: "Reports", backups: "Backups", data: "Export and import", claude: "Claude and AI", logs: "Logs and diagnostics", version: "Version and updates" };

function text(x) { return x == null ? "" : String(x); }
const kindOf = (k) => (KINDS.includes(k) ? k : DEFAULT_KIND);

/** Whether the tag is drawn: Help, or a Settings page other than the one that holds the Feedback card (and not while a search shows that card); never in a published file or an as-at view. */
export function tagShown({ view, page, helpOpen, fromFile, past, feedbackCard } = {}) {
  if (fromFile || past) return false;
  if (helpOpen) return true;
  return view === "settings" && page !== "version" && !feedbackCard;   // feedbackCard: Settings search is showing the Feedback card
}

/** The page the user was on, in words, for the added lines. */
export function pageWords({ view, page, helpOpen } = {}) {
  if (helpOpen) return "Help and about";
  if (view === "settings") return `Settings, ${SETTINGS_NAMES[page || ""] || text(page)}`;
  return text(view);
}

/** The system in words: macOS with its version when the browser's own text gives one, else the platform as the browser names it. */
export function systemWords(nav) {
  const n = nav || (typeof navigator !== "undefined" ? navigator : {});
  const plat = oneLine((n.userAgentData && n.userAgentData.platform) || n.platform || "");
  if (/mac/i.test(plat) || /Mac OS X/.test(n.userAgent || "")) {
    const m = /Mac OS X (\d+)[_.](\d+)(?:[_.](\d+))?/.exec(n.userAgent || "");
    return m ? `macOS ${m[1]}.${m[2]}${m[3] && m[3] !== "0" ? "." + m[3] : ""}` : "macOS";
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
