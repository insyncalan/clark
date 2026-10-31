// Settings › Personal (#45, #179): how the page looks for you: Appearance (Light, Dark or System) and how the Dashboard's sections look. It applies at once and is remembered on this computer. Edit's page only:
// a published file has no Settings.
import { style, setStyle } from "../stores/style.js";
import { appearance, setAppearance } from "../stores/appearance.js";

export const STYLES = [
  ["slim", "Slim gaps", "Sections close together, divided by a thin line."],
  ["roomy", "Roomy gaps", "More space between sections."],
  ["grey", "Grey headers", "Each section's title sits on a grey band."],
  ["card", "One card", "All the sections inside a single card."],
];

export const APPEARANCES = [                                 // the ruled order: System first, the default
  ["system", "System", "Follows your Mac's setting."],
  ["light", "Light", "Always light."],
  ["dark", "Dark", "Always dark."],
];

export function Personal() {
  return (
    <section class="frame personal" id="personal" aria-labelledby="personal-h">
      <h2 id="personal-h">Personal</h2>
      <p class="muted">These are for you, on this computer. This changes the page you edit. The published page uses Slim gaps for now.</p>
      <fieldset class="styles" data-appearance>
        <legend>Appearance</legend>
        {APPEARANCES.map(([id, name, line]) => (
          <label key={id} class="stylepick"><input type="radio" name="appearance" value={id} checked={appearance.value === id} onChange={() => setAppearance(id)} />
            <span><b>{name}</b><small>{line}</small></span></label>
        ))}
      </fieldset>
      <fieldset class="styles">
        <legend>Section style</legend>
        {STYLES.map(([id, name, line]) => (
          <label key={id} class="stylepick"><input type="radio" name="secstyle" value={id} checked={style.value === id} onChange={() => setStyle(id)} />
            <span><b>{name}</b><small>{line}</small></span></label>
        ))}
      </fieldset>
    </section>
  );
}
