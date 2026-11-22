// Settings: Theme (row 1269). Which look the page and published files use is kept by the server for this computer
// (app_settings, GET and POST /api/theme); nothing is kept in the browser's storage. The choice applies on the next page load.
import { signal } from "@preact/signals";
import { themeRead, themeChange, words } from "./publishApi.js";

export const themeChoice = signal("");               // "" until the server answers; then "classic" or "cards"
export const themeStatus = signal("loading");      // "loading" | "ready" | "unavailable"

let latest = 0;       // the newest request: an older answer is ignored

const isTheme = (b) => b && b.ok === true && (b.theme === "classic" || b.theme === "cards");

export function loadTheme() {
  const mine = ++latest;
  themeStatus.value = "loading";
  return themeRead().then((r) => {
    if (mine !== latest) return;
    if (r.status === 200 && isTheme(r.body)) { themeChoice.value = r.body.theme; themeStatus.value = "ready"; }
    else { themeChoice.value = ""; themeStatus.value = "unavailable"; }
  });
}

/** Choose a theme. The page changes only after the server has kept it. Resolves to {ok, message}. */
export async function setTheme(theme) {
  const mine = ++latest;
  const r = await themeChange(theme);
  if (r.status === 200 && isTheme(r.body)) {
    if (mine === latest) { themeChoice.value = r.body.theme; themeStatus.value = "ready"; }
    return { ok: true, message: r.body.message || "" };
  }
  return { ok: false, message: words(r, "save the theme") };
}
