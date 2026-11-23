// The running version of clark, as /health gives it (row 1281: "clark ver. x.x" on the Classic profile menu's Help line). Read when the profile
// menu mounts (ProfileMenu calls this once, in its mount effect); "" until it arrives or when it cannot be read, so the menu shows nothing rather than a guess. A later call asks again after a failed read, but nothing makes one today. Never written in the page.
import { signal } from "@preact/signals";

export const version = signal("");
let asked = false;

export async function loadVersion() {
  if (asked) return;
  asked = true;
  try {
    const r = await fetch("/health", { cache: "no-store" });
    if (r.ok === false) { asked = false; return; }   // a 404 or 500 (a proxy or error page) may carry a JSON body with a version: show none
    const b = await r.json();
    if (b && typeof b.version === "string") version.value = b.version;
    else asked = false;
  } catch (e) {
    asked = false;                                     // a failed read may be asked for again by a later call (none is made after the mount)
  }
}
