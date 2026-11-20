// Open in your mail app (row 1297): the finished mailto link goes to POST /api/open-mail, so clark's own server hands it to the system's mail
// app. {ok, message}: never a throw. `message` is the server's own plain words when it refused; "" when there is no answer at all.
import { token } from "../stores/report.js";
import { zoneFetch } from "../api.js";
import { openFile } from "../router.js";

export async function openMail(link) {
  try {
    const r = await zoneFetch("/api/open-mail", { method: "POST", headers: { "X-Clark-Token": token(), "Content-Type": "application/json" }, body: JSON.stringify({ link }), cache: "no-store" });
    const b = await r.json().catch(() => null);
    if (r.status === 200 && b && b.ok) return { ok: true, message: "" };
    return { ok: false, message: b && typeof b.message === "string" ? b.message : "" };
  } catch (e) {
    return { ok: false, message: "" };
  }
}

export const MAIL_NOTE = "No mail app opened. Use Copy as text and paste it into your mail.";   // ruled words (row 1297): shown only when the open fails

// The click on the mail link: the server opens it. `show(true)` when the open fails (the plain note under the button), `show(false)` otherwise;
// whenever the open fails (a refusal, as off the Mac, or no answer at all) the plain link is followed as before, so the mail link still works there.
export async function mailClick(e, href, show) {
  e.preventDefault();
  show(false);
  const r = await openMail(href);
  if (r.ok) return;
  if (r.message) show(true);
  openFile(href);   // the plain link, followed through the router (only the router sets the address)
}
