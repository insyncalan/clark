// Page errors reach the log through the local server (#110). Only the error's kind and its message go, never a stack, a file name
// or the page's data; the server keeps only the browsers' own fault words and drops a flood. A page sends at most 20 a load.
import { token } from "../stores/report.js";

const MOST = 20;
let sent = 0;

function report(error, fallback) {
  if (sent >= MOST) return;
  sent += 1;
  try {
    const kind = error && typeof error.name === "string" ? error.name.slice(0, 40) : "Error";
    const message = String(error && error.message !== undefined ? error.message : fallback || "").slice(0, 300);
    fetch("/api/page-error", { method: "POST", headers: { "X-Clark-Token": token(), "Content-Type": "application/json" },
      body: JSON.stringify({ kind, message }), cache: "no-store", keepalive: true }).catch(() => {});
  } catch (e) { /* a report that cannot be sent is dropped */ }
}

export function installPageErrors() {
  window.addEventListener("error", (ev) => report(ev.error, ev.message));
  window.addEventListener("unhandledrejection", (ev) => report(ev.reason, ""));
}
