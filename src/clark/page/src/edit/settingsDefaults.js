// The one list of defaults (row 1115, S4), as creaite's settings-defaults.json: every setting row that can be reset has an entry here with
// the default and a written reason. A test fails when a row that offers Reset has no entry. Pure: no store, no page.
import LIST from "./settingsDefaults.json";

/** The default for a setting row id. A missing entry is a mistake in the code, so it throws rather than guessing. */
export function defaultOf(id) {
  const e = LIST[id];
  if (!e) throw new Error("no default recorded for setting: " + id);
  return e.value;
}
