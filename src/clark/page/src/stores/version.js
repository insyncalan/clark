// The running version of clark, as /health gives it (row 1281: "clark ver. x.x" on the Classic profile menu's Help line). Read when the profile
// menu mounts (ProfileMenu calls this once, in its mount effect); "" until it arrives or when it cannot be read, so the menu shows nothing rather than a guess. A later call asks again after a failed read, but nothing makes one today. Never written in the page.
import { signal } from "@preact/signals";

export const version = signal("");
let asked = false;

// The one /health read of this page, shared by the profile menu's version line (below) and the Bell's installed version (edit/noticesState.js): a good
// answer (a string version) is kept, so the page reads /health once; a failed or odd one is dropped, so a later call asks again. It never throws.
let health = null;
export function readHealth() {
  if (!health) {
    const mine = (async () => {
      try {
        const r = await fetch("/health", { cache: "no-store" });
        let body = null;
        try { body = await r.json(); } catch (e) { /* not JSON: no body */ }
        return { ok: r.ok !== false, status: r.status, body };
      } catch (e) {
        return { ok: false, status: undefined, body: null };
      }
    })();
    health = mine;
    mine.then((h) => { if (!h.ok || !h.body || typeof h.body.version !== "string") { if (health === mine) health = null; } });
  }
  return health;
}

export async function loadVersion() {
  if (asked) return;
  asked = true;
  const h = await readHealth();
  if (!h.ok) { asked = false; return; }   // a 404 or 500 (a proxy or error page) may carry a JSON body with a version: show none
  const b = h.body;
  if (b && typeof b.version === "string") version.value = b.version;
  else asked = false;
}
