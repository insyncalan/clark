// Settings › Theme (row 1269): two choices, Classic (the default) and Cards. The server keeps the choice (themeState.js);
// it applies on the next page load. Edit parts only: a published file has no Settings.
import { useEffect, useState } from "preact/hooks";
import { themeChoice, themeStatus, loadTheme, setTheme } from "./themeState.js";

const CHOICES = [
  ["classic", "Classic (default)", "The same pages, in the folder look."],
  ["cards", "Cards", "The look clark has had until now."],
];

export function ThemeSettings() {
  const choice = themeChoice.value;
  const status = themeStatus.value;
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  useEffect(() => { loadTheme(); }, []);

  async function pick(theme) {
    if (busy || theme === choice) return;
    setBusy(true);
    setMsg(null);
    const r = await setTheme(theme);
    setBusy(false);
    if (!r.ok) setMsg({ kind: "error", text: r.message });
  }

  return (
    <section class="frame setting" id="theme-settings">
      <h2 id="theme-settings-h" tabIndex={-1}>Theme</h2>
      <p class="muted">Your choice applies the next time the page loads.</p>
      {status === "loading" ? <p id="theme-state">Checking the theme…</p> : null}
      {status === "unavailable" ? <p id="theme-state" class="error">The theme could not be read just now. Reload the page to try again.</p> : null}
      {status === "ready" ? (
        <div role="radiogroup" aria-label="Theme" data-theme-choice>
          {CHOICES.map(([id, name, line]) => (
            <label class="pubopt" key={id}>
              <input type="radio" name="theme-choice" value={id} checked={choice === id} disabled={busy} onChange={() => pick(id)} />
              <span>{name}</span> <span class="muted">{line}</span>
            </label>
          ))}
        </div>
      ) : null}
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </section>
  );
}
