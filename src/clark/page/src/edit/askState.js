// Settings: asking (#47). The on/off switch is a promise about THIS computer, so the database keeps it (app_settings.ask_enabled),
// not this browser: the same wherever clark is opened, changed only through the server (one step with History and Undo). The page
// asks GET /api/ask-enabled once and changes it with POST /api/ask-enabled; nothing is kept in the browser's storage.
// Fail closed: until the server has answered (or when it cannot be reached) asking reads as off, so nothing is sent to Claude on a
// guess. The panel's status-line link reads and changes this same choice through setAsk(), so there is one switch whichever place
// changes it.
import { signal } from "@preact/signals";
import { askEnabledRead, askEnabledChange, words } from "./publishApi.js";

export const askOn = signal(false);               // false until the server says otherwise
export const askStatus = signal("loading");      // "loading" | "ready" | "unavailable"
export const askSaved = signal(true);            // false: this computer's saved data cannot keep the choice yet (it reads as off)

let loading = null;

/** Ask the server for the switch (once; a second call while it is out shares the answer). `force` asks again. */
export function loadAsk(force) {
  if (loading && !force) return loading;
  loading = askEnabledRead().then((r) => {
    const b = r.body;
    if (r.status === 200 && b && b.ok === true && typeof b.ask_enabled === "boolean") {
      askOn.value = b.ask_enabled;
      askSaved.value = b.saved !== false;
      askStatus.value = "ready";
    } else {
      askOn.value = false;
      askStatus.value = "unavailable";
    }
  });
  return loading;
}

/** Turn asking on or off. The page changes only after the server has kept the choice. One exception, in the safe direction: if
 *  turning it OFF could not be kept, it is off in this window anyway and the answer says it was not saved. Resolves to
 *  {ok, message}. */
export async function setAsk(on) {
  const r = await askEnabledChange(!!on);
  const b = r.body;
  if (r.status === 200 && b && b.ok === true && typeof b.ask_enabled === "boolean") {
    askOn.value = b.ask_enabled;
    askStatus.value = "ready";
    return { ok: true, message: b.message || "" };
  }
  const why = words(r, "save the asking switch");
  if (!on) {
    askOn.value = false;
    return { ok: false, message: `Asking is off in this window, but that was not saved, so it will be on again after a reload. ${why}` };
  }
  return { ok: false, message: why };
}

// What the page says to the owner while asking is off (one place, so every place that shows the off state says the same).
export const ASK_OFF_LINE = "Asking is off. Turn it on in Settings.";
export const ASK_CHECKING_LINE = "Checking whether asking is on…";
export const ASK_UNAVAILABLE_LINE = "Asking is off, because clark could not check the setting just now. Reload the page to try again.";
