// Settings › Personal (#45, #179): how the page looks for you: Appearance (Light, Dark or System) and how the Dashboard's sections look. It applies at once and is remembered on this computer. Edit's page only:
// a published file has no Settings.
import { style, setStyle } from "../stores/style.js";
import { useEffect, useRef, useState } from "preact/hooks";
import { appearance, setAppearance } from "../stores/appearance.js";
import { profile, loadProfile, profileKnown, setProfile, wantName } from "../stores/profile.js";
import { singleKeys, setSingleKeys } from "../stores/keyPrefs.js";

export const STYLES = [
  ["slim", "Slim gaps", "Each section is its own card, with a slim gap that shows the page picture."],
  ["roomy", "Roomy gaps", "The same, with more space between the sections."],
  ["grey", "Grey headers", "Slim gaps, and each section title in a grey band, like the Work items groups."],
  ["card", "One card", "All the sections in one long card."],
];

export const APPEARANCES = [                                 // the ruled order: System first, the default
  ["system", "System", "Follows your Mac's setting."],
  ["light", "Light", "Always light."],
  ["dark", "Dark", "Always dark."],
];

// About you (#180): the two optional boxes. Each is saved when it is left (or on Enter); a refusal says why under the box and writes
// nothing, and what was typed stays in the box so it can be mended. Emptying the name returns the menu's top line to its link.
const UNREAD = "Your saved name and email could not be read. Reload the page and try again. Nothing was saved.";

function AboutYou() {
  const name = useRef(null), email = useRef(null);
  const [typed, setTyped] = useState({ name: profile.value.name, email: profile.value.email });
  const [said, setSaid] = useState({ name: "", email: "" });
  useEffect(() => { loadProfile(); }, []);
  const typedIn = useRef({ name: false, email: false });
  const edits = useRef({ name: 0, email: 0 });          // how many times each box has been typed in: a box has moved if this has changed, whatever it now says
  // The boxes follow what clark has when it is read late (a read that finished after Settings opened), but only a box nobody has typed in:
  // a person who keeps typing while a save is on its way must never see the box go back to what was saved (and a box typed in before that
  // effect ran must not be emptied by it). A saved value is put back in its box by save(), below, and only when the box still holds what was sent.
  useEffect(() => {
    setTyped((t) => ({ name: typedIn.current.name ? t.name : profile.value.name, email: typedIn.current.email ? t.email : profile.value.email }));
  }, [profile.value.name, profile.value.email]);
  useEffect(() => { if (wantName.value && name.current) { wantName.value = false; name.current.focus(); } });
  const save = async (field) => {
    // A save made before the first read has landed would send a blank for the other box and so blank what clark has saved there: wait for the
    // read first. If it cannot be read, nothing is sent.
    if (!(await profileKnown())) { setSaid({ name: field === "name" ? UNREAD : "", email: field === "email" ? UNREAD : "" }); return; }
    // the box left is read as it is now (not from an earlier draw); the other box is sent as it is now only if it has been typed in, else as clark has it
    const now = (f) => (typedIn.current[f] && (f === "name" ? name : email).current ? (f === "name" ? name : email).current.value : profile.value[f]);
    const sent = { name: field === "name" ? (name.current ? name.current.value : typed.name) : now("name"),
                   email: field === "email" ? (email.current ? email.current.value : typed.email) : now("email") };
    const seen = { ...edits.current };
    const r = await setProfile(sent.name, sent.email);
    // One rule: an answer speaks only for the newest save. A late answer to an older save changes nothing on the page (it can neither clear
    // nor replace what a newer save said), so a refusal is never lost and an old refusal never shows over text that was saved. A refusal is
    // also shown only while the box still holds the text that was refused (text typed since has not been sent yet).
    if (!r.newest) return;
    if (r.ok) {
      // what clark kept (it may be tidied, such as spaces cut off the ends) goes back in a box only if the box still holds what was sent:
      // a box changed since is left as it is
      setTyped((t) => ({ name: t.name === sent.name ? r.name : t.name, email: t.email === sent.email ? r.email : t.email }));
      // a box that still holds what was sent now agrees with clark again, so it follows clark again
      for (const f of ["name", "email"]) if (edits.current[f] === seen[f]) typedIn.current[f] = false;
      setSaid({ name: "", email: "" });
      return;
    }
    if (edits.current[field] !== seen[field]) return;      // the box was typed in since (even back to the same words): the refusal is not about what it holds now
    setSaid({ name: field === "name" ? r.message : "", email: field === "email" ? r.message : "" });
  };
  const box = (field, label, type, line, ref) => (
    <div class="fld">
      <label for={`about-${field}`}>{label}</label>
      <input id={`about-${field}`} ref={ref} type={type} value={typed[field]} autocomplete={field === "name" ? "name" : "email"} data-about={field}
        aria-describedby={`about-${field}-line`} aria-invalid={said[field] ? "true" : undefined}
        onInput={(e) => { const v = e.currentTarget.value; typedIn.current[field] = true; edits.current[field]++; setTyped((t) => ({ ...t, [field]: v })); }}
        onBlur={() => save(field)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); save(field); } }} />
      <small id={`about-${field}-line`}>{line}</small>
      <p class="fld-bad" role="alert">{said[field]}</p>
    </div>
  );
  return (
    <fieldset class="styles about" data-about-you>
      <legend>About you</legend>
      {box("name", "Your name", "text", "Shown at the top of your menu, as the name on each change you make, and on Excel exports and publications. Optional.", name)}
      {box("email", "Your email", "email", "Optional. Used only to tell which email addresses are your own. Nothing here sends email.", email)}
    </fieldset>
  );
}

export function Personal() {
  return (
    <section class="frame personal" id="personal" aria-labelledby="personal-h">
      <h2 id="personal-h">Personal</h2>
      <p class="muted">These are for you, on this computer. The section style is used on the published report too; Light or Dark is yours alone.</p>
      <fieldset class="styles secstyles" role="radiogroup" data-secstyles>
        <legend>Dashboard sections</legend>
        {STYLES.map(([id, name, line]) => (
          <label key={id} class={`secpick sk-${id}`}>
            <input type="radio" name="secstyle" value={id} checked={style.value === id} onChange={() => setStyle(id)} />
            <span class="secpick-card">
              <span class="secpick-pic" aria-hidden="true"><i></i><i></i><i></i></span>
              <span class="secpick-name"><b>{name}</b>
                <span class="secpick-tick" aria-hidden="true"><svg viewBox="0 0 16 16" width="14" height="14"><path d="M3 8.5l3.2 3.2L13 4.8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" /></svg></span></span>
              <small>{line}</small>
            </span>
          </label>
        ))}
      </fieldset>
      <fieldset class="styles" data-appearance>
        <legend>Appearance</legend>
        {APPEARANCES.map(([id, name, line]) => (
          <label key={id} class="stylepick"><input type="radio" name="appearance" value={id} checked={appearance.value === id} onChange={() => setAppearance(id)} />
            <span><b>{name}</b><small>{line}</small></span></label>
        ))}
      </fieldset>
      <AboutYou />
      <fieldset class="keys">
        <legend>Keys</legend>
        <label class="stylepick"><input type="checkbox" checked={singleKeys.value} onChange={(e) => setSingleKeys(e.currentTarget.checked)} />
          <span><b>Single-key shortcuts</b><small>Letter keys such as V and E work alone on the page. Turn them off if you type by voice or hit keys by accident. Arrows, Enter, Esc and Ctrl or Cmd combinations still work.</small></span></label>
      </fieldset>
    </section>
  );
}
