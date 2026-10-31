// Settings › Personal (#45): how the Dashboard's sections look. It applies at once and is remembered on this computer. Edit's page only:
// a published file has no Settings.
import { style, setStyle } from "../stores/style.js";

export const STYLES = [
  ["slim", "Slim gaps", "Sections close together, divided by a thin line."],
  ["roomy", "Roomy gaps", "More space between sections."],
  ["grey", "Grey headers", "Each section's title sits on a grey band."],
  ["card", "One card", "All the sections inside a single card."],
];

export function Personal() {
  return (
    <section class="frame personal" id="personal" aria-labelledby="personal-h">
      <h2 id="personal-h">Personal</h2>
      <p class="muted">These are for you, on this computer. This changes the page you edit. The published page uses Slim gaps for now.</p>
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
