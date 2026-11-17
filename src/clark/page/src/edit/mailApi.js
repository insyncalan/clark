// Open in your mail app (row 1297): the finished mailto link goes to POST /api/open-mail, so clark's own server hands it to the system's mail
// app. {ok, message}: never a throw. `message` is the server's own plain words when it refused; "" when there is no answer at all.
import { token } from "../stores/report.js";
import { zoneFetch } from "../api.js";

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

// The click on the mail link: the server opens it; with no answer from the server the plain link is followed as before.
export async function mailClick(e, href, say) {
  e.preventDefault();
  const r = await openMail(href);
  if (r.ok) return;
  if (r.message) say(r.message);
  else window.location.href = href;
}
