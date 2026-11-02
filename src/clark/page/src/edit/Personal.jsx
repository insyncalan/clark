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

// Profile (#180, #440): Settings' first card, the prototype's (views.js 1435-1439): Name, Alias, Email, Phone number and Organisation, each
// optional. Each box is saved when it is left (or on Enter); a refusal says why under the box and writes nothing, and what was typed stays
// in the box so it can be mended. Emptying the name returns the menu's top line to its link. Kept on this computer only: none of the five
// goes into a published file, a report, Word, Excel or an email.
// (The boxes' ids stay about-name, about-email and so on: tests and the menu's "Add your name in Settings" reach them by those.)
const UNREAD = "Your saved details could not be read. Reload the page and try again. Nothing was saved.";
export const FIELDS = [                                      // field, label, input type, placeholder, autocomplete: the prototype's words
  ["name", "Name", "text", "Your full name", "name"],
  ["alias", "Alias", "text", "What colleagues call you, or your initials", "nickname"],
  ["email", "Email", "email", "name@company.com", "email"],
  ["phone", "Phone number", "tel", "+971 50 123 4567", "tel"],
  ["org", "Organisation", "text", "Your company or team", "organization"],
];
const KEYS = FIELDS.map((f) => f[0]);
const each = (make) => Object.fromEntries(KEYS.map((k) => [k, make(k)]));

export function Profile() {
  const boxes = useRef({});                              // the five input elements, by field
  const [typed, setTyped] = useState(() => each((k) => profile.value[k]));
  const [said, setSaid] = useState(() => each(() => ""));
  useEffect(() => { loadProfile(); }, []);
  const typedIn = useRef(each(() => false));
  const edits = useRef(each(() => 0));                   // how many times each box has been typed in: a box has moved if this has changed, whatever it now says
  // The boxes follow what clark has when it is read late (a read that finished after Settings opened), but only a box nobody has typed in:
  // a person who keeps typing while a save is on its way must never see the box go back to what was saved (and a box typed in before that
  // effect ran must not be emptied by it). A saved value is put back in its box by save(), below, and only when the box still holds what was sent.
  useEffect(() => {
    setTyped((t) => each((k) => (typedIn.current[k] ? t[k] : profile.value[k])));
  }, KEYS.map((k) => profile.value[k]));
  useEffect(() => { if (wantName.value && boxes.current.name) { wantName.value = false; boxes.current.name.focus(); } });
  const save = async (field) => {
    // A save made before the first read has landed would send blanks for the other boxes and so blank what clark has saved there: wait for
    // the read first. If it cannot be read, nothing is sent.
    if (!(await profileKnown())) { setSaid(each((k) => (k === field ? UNREAD : ""))); return; }
    // the box left is read as it is now (not from an earlier draw); each other box is sent as it is now only if it has been typed in, else as clark has it
    const sent = each((k) => (k === field || typedIn.current[k]) && boxes.current[k] ? boxes.current[k].value : k === field ? typed[k] : profile.value[k]);
    const seen = { ...edits.current };
    const r = await setProfile(sent);
    // One rule: an answer speaks only for the newest save. A late answer to an older save changes nothing on the page (it can neither clear
    // nor replace what a newer save said), so a refusal is never lost and an old refusal never shows over text that was saved. A refusal is
    // also shown only while the box still holds the text that was refused (text typed since has not been sent yet).
    if (!r.newest) return;
    if (r.ok) {
      // what clark kept (it may be tidied, such as spaces cut off the ends) goes back in a box only if the box still holds what was sent:
      // a box changed since is left as it is
      setTyped((t) => each((k) => (t[k] === sent[k] ? r[k] : t[k])));
      // a box that still holds what was sent now agrees with clark again, so it follows clark again
      for (const k of KEYS) if (edits.current[k] === seen[k]) typedIn.current[k] = false;
      setSaid(each(() => ""));
      return;
    }
    if (edits.current[field] !== seen[field]) return;      // the box was typed in since (even back to the same words): the refusal is not about what it holds now
    setSaid(each((k) => (k === field ? r.message : "")));
  };
  return (
    <section class="frame personal" id="profile" aria-labelledby="profile-h" data-about-you data-profile>
      <h2 id="profile-h">Profile</h2>
      <p class="muted">Who you are in clark. Your name is on each change you make and signs the emails clark drafts, and your email tells it which addresses are your own. All five are optional. Kept on this computer only: none of it goes into a published report.</p>
      {FIELDS.map(([field, label, type, hint, auto]) => (
        <div class="fld" key={field}>
          <label for={`about-${field}`}>{label}</label>
          <input id={`about-${field}`} ref={(el) => { boxes.current[field] = el; }} type={type} value={typed[field]} placeholder={hint} autocomplete={auto} data-about={field}
            aria-describedby={`about-${field}-line`} aria-invalid={said[field] ? "true" : undefined}
            onInput={(e) => { const v = e.currentTarget.value; typedIn.current[field] = true; edits.current[field]++; setTyped((t) => ({ ...t, [field]: v })); }}
            onBlur={() => save(field)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); save(field); } }} />
          <p class="fld-bad" id={`about-${field}-line`} role="alert">{said[field]}</p>
        </div>
      ))}
    </section>
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
      <fieldset class="keys">
        <legend>Keys</legend>
        <label class="stylepick"><input type="checkbox" checked={singleKeys.value} onChange={(e) => setSingleKeys(e.currentTarget.checked)} />
          <span><b>Single-key shortcuts</b><small>Letter keys such as V and E work alone on the page. Turn them off if you type by voice or hit keys by accident. Arrows, Enter, Esc and Ctrl or Cmd combinations still work.</small></span></label>
      </fieldset>
    </section>
  );
}
