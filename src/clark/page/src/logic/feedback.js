// The Feedback card's logic (#1069). Plain functions, no DOM and no Preact, so a test can run them alone. The user writes what is
// wrong or what they suggest; the card builds one email text from it and the app context, and the mail link or Copy carries it.
// clark never sends mail: the link opens the user's own mail app (which one is theirs to choose) and they press send.
// The link rules are Draft email's (logic/draftEmail.js): the same longest link, the same header clean-up.
import { MAILTO_LIMIT, mailLink, oneLine } from "./draftEmail.js";

export { MAILTO_LIMIT };
// Where the feedback goes: data, not wording. It is the only address in this file.
export const ADDRESS = "alan.mahon@inception42.ai";
export const SUBJECT = "clark feedback";

export const LABELS = {
  title: "Feedback",
  intro: "Tell us what is wrong or what you would like to see. Your mail app opens with the message ready and you press send. clark never sends it.",
  message: "What is wrong, or what would you suggest?",
  contact: "How can we reach you? (optional)",
  contextHead: "Added to the email",
  contextNote: "Only these lines are added to what you write. Nothing from your reports is included.",
  mail: "Open in your mail app",
  copy: "Copy as text",
};
export const NOTHING_YET = "Write your feedback first.";
export const TOO_LONG = "This is too long for a mail link. Use Copy as text and paste it into an email.";
export const COPIED = "Copied";
export const COPY_REFUSED = "The browser did not copy it. Press ⌘C to copy the selected text.";

function text(x) { return x == null ? "" : String(x); }

/** The app context, as the lines the card shows and the email carries: the version and the system, nothing else. */
export function contextLines(ctx) {
  const c = ctx || {};
  return [`clark version: ${oneLine(c.version) || "unknown"}`, `System: ${oneLine(c.platform) || "unknown"}`];
}

/** The email's body: the words, the contact line when given, then exactly the context lines. */
export function emailText(form, ctx) {
  const parts = [text(form && form.message).trim()];
  const contact = oneLine(form && form.contact);
  if (contact) parts.push(`Contact: ${contact}`);
  parts.push(contextLines(ctx).join("\n"));
  return parts.join("\n\n");
}

/** The mail link, only when there are words and the finished link fits the Draft email limit; else the plain words why not. */
export function mail(form, ctx) {
  if (!text(form && form.message).trim()) return { href: "", message: NOTHING_YET };
  const r = mailLink({ to: ADDRESS, subject: SUBJECT, text: emailText(form, ctx) });
  return r.href ? r : { href: "", message: TOO_LONG };
}

/** What Copy as text puts on the clipboard: the address and subject first (the body has neither), then the body. */
export function copyText(form, ctx) {
  return `To: ${ADDRESS}\nSubject: ${SUBJECT}\n\n${emailText(form, ctx)}`;
}

/** The system the page runs on, in the browser's own words. */
export function platformWords(nav) {
  const n = nav || (typeof navigator !== "undefined" ? navigator : {});
  return oneLine((n.userAgentData && n.userAgentData.platform) || n.platform || "");
}
