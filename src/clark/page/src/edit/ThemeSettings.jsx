// Settings › Theme (row 1363): Classic is the only theme. Nothing is read from or written to the server here: the Cards theme stays in the
// repo but is not offered, and a value stored by an earlier choice is left alone and never applied. Edit parts only: a published file has no Settings.

export function ThemeSettings() {
  return (
    <section class="frame setting" id="theme-settings">
      <h2 id="theme-settings-h" tabIndex={-1}>Theme</h2>
      <div role="radiogroup" aria-label="Theme" data-theme-choice>
        <label class="pubopt">
          <input type="radio" name="theme-choice" value="classic" checked={true} readOnly />
          <span>Classic</span> <span class="muted">The only theme clark has.</span>
        </label>
      </div>
    </section>
  );
}
