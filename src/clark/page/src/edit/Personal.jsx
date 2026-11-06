// Settings › Personal (#45, #179): how the page looks for you: Appearance (Light, Dark or System) and how the Dashboard's sections look. It applies at once and is remembered on this computer. Edit's page only:
// a published file has no Settings.
import { style, setStyle } from "../stores/style.js";
import { useEffect, useRef, useState } from "preact/hooks";
import { appearance, setAppearance } from "../stores/appearance.js";
import { profile, profileRead, loadProfile, setProfile, wantName } from "../stores/profile.js";
import { singleKeys, setSingleKeys } from "../stores/keyPrefs.js";
import { announce, leave, noteTyped } from "./aboutYouToast.js";
import { announceSwitch, leaveSwitch } from "./switchToast.js";
import { aliasOffer } from "../logic/alias.js";

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

// The words of the Alias box under the name box, kept here in one place so they are easy to change (item 613).
export const ALIAS_WORDS = {
  label: "Alias",
  placeholder: "What colleagues call you, or your initials",
  help: "Your first name and your initials, worked out from your full name. You can change it.",
};
const ALIAS_MAX = 60;                                          // as settings.py ALIAS_MAX: a longer suggestion is not filled in

// The suggestion as it goes in the box: aliasOffer keeps its two parts comma-separated ("Jane,JD"); the box puts a space after the comma
// ("Jane, JD"). One word is just that word.
const showAlias = (alias) => alias.split(",").map((part) => part.trim()).filter(Boolean).join(", ");

// About you (#180): the optional boxes. Each is saved when it is left (or on Enter); a refusal says why under the box and writes
// nothing, and what was typed stays in the box so it can be mended. Emptying the name returns the menu's top line to its link.
// The Alias (item 613): while no Alias was saved and nobody has typed in its box, it is filled in from the name ("Jane Doe" gives
// "Jane, JD") and follows the name as it is typed, and is saved with the others. Once it is saved, or the person types or edits it, it is
// never filled in again: a later name change leaves it as it is; an Alias clark already has is never replaced by a suggestion (aliasOffer's rule).
function AboutYou() {
  const name = useRef(null), email = useRef(null), alias = useRef(null);
  const kept = useRef(profileRead.value ? profile.value.alias || "" : null);     // the Alias clark had when Settings opened; null: not read yet
  const ownAlias = useRef(false);                                                 // the person has typed in the Alias box (never reset)
  // what the Alias box holds when it is not the person's: the suggestion for `n`, else what clark had ("" when nothing)
  const follow = (n) => { const s = showAlias(aliasOffer(n, kept.current || "")); return s && s.length <= ALIAS_MAX ? s : kept.current || ""; };
  const [typed, setTyped] = useState(() => ({ name: profile.value.name, email: profile.value.email, alias: follow(profile.value.name) }));
  const [said, setSaid] = useState({ name: "", email: "", alias: "" });
  useEffect(() => { loadProfile(); }, []);
  const typedIn = useRef({ name: false, email: false, alias: false });
  // The boxes follow what clark has when it is read late (a read that finished after Settings opened), but only a box nobody has typed in
  // since it was last saved: a person who keeps typing while a save is on its way must never see the box go back to what was saved (and a
  // box typed in before that effect ran must not be emptied by it). A saved value is put back in its box by save(), below, and only when
  // the box still holds what was sent; that box is then no longer typed in, so a later read can fill it again.
  useEffect(() => {
    if (kept.current === null && profileRead.value) kept.current = profile.value.alias || "";
    setTyped((t) => {
      const n = typedIn.current.name ? t.name : profile.value.name;
      return { name: n, email: typedIn.current.email ? t.email : profile.value.email,
               alias: ownAlias.current ? (typedIn.current.alias ? t.alias : profile.value.alias || "") : follow(n) };
    });
  }, [profile.value.name, profile.value.email, profile.value.alias, profileRead.value]);
  useEffect(() => { if (wantName.value && name.current) { wantName.value = false; name.current.focus(); } });
  useEffect(() => { noteTyped(typed); }, [typed.name, typed.email, typed.alias]);      // the toast's Undo goes once the boxes hold something else (aboutYouToast.js, #429)
  useEffect(() => leave, []);                                             // leaving Settings takes the toast (and its Undo) with it, in View as in Edit
  const save = async (field) => {
    // the boxes are read as they are now (not from an earlier draw), so a box left a moment ago is never saved over another. An Alias that
    // is not the person's is the suggestion for the name now; before clark has said what Alias it has, none is sent (clark keeps its own)
    const sent = { name: name.current ? name.current.value : typed.name, email: email.current ? email.current.value : typed.email };
    sent.alias = ownAlias.current ? (alias.current ? alias.current.value : typed.alias) : kept.current === null ? undefined : follow(sent.name);
    // Before clark has answered a read, a box nobody has typed in holds only the empty draw, not what is saved: it is not sent, and the
    // store fills it from clark's own answer (#420), so saving one box first never blanks the other.
    const unread = !profileRead.value;
    const r = await setProfile(unread && !typedIn.current.name ? undefined : sent.name, unread && !typedIn.current.email ? undefined : sent.email, sent.alias);
    // One rule: an answer speaks only for the newest save. A late answer to an older save changes nothing on the page (it can neither clear
    // nor replace what a newer save said), so a refusal is never lost and an old refusal never shows over text that was saved. A refusal is
    // also shown only while the box still holds the text that was refused (text typed since has not been sent yet).
    if (!r.newest) return;
    if (r.ok) {
      // A saved Alias is frozen (item 613): it becomes what clark has, so the name no longer carries it and only the person changes it.
      // An empty one keeps following the name (an empty Alias cannot be told from one never set).
      kept.current = r.alias || "";
      // what clark kept (it may be tidied, such as spaces cut off the ends) goes back in a box only if the box still holds what was sent:
      // a box changed since is left as it is (and stays typed in)
      for (const [f, ref] of [["name", name], ["email", email], ["alias", alias]]) if ((ref.current ? ref.current.value : typed[f]) === sent[f]) typedIn.current[f] = false;
      setTyped((t) => {
        const n = t.name === sent.name ? r.name : t.name;
        return { name: n, email: t.email === sent.email ? r.email : t.email,
                 alias: !ownAlias.current ? follow(n) : t.alias === sent.alias ? r.alias : t.alias };
      });
      setSaid({ name: "", email: "", alias: "" });
      // "Name saved." or "Email saved." with Undo, when the save changed something (#429); the Alias is spoken of only when it is the person's
      announce(r, (v) => { kept.current = v.alias || ""; setTyped({ ...v, alias: ownAlias.current ? v.alias : follow(v.name) }); }, ownAlias.current);
      return;
    }
    // the refusal is shown under the box it is about (the route says which); a refusal that names none goes under the box that was left
    const about = r.field || field, mine = { name, email, alias }[about];
    if ((mine.current ? mine.current.value : typed[about]) !== sent[about]) return;
    setSaid({ name: about === "name" ? r.message : "", email: about === "email" ? r.message : "", alias: about === "alias" ? r.message : "" });
  };
  // The name box carries the Alias with it while the Alias is not the person's; typing in the Alias box makes it theirs.
  const onInput = (field, v) => {
    typedIn.current[field] = true;
    if (field === "alias") ownAlias.current = true;
    setTyped((t) => ({ ...t, [field]: v, ...(field === "name" && !ownAlias.current ? { alias: follow(v) } : {}) }));
  };
  const box = (field, label, type, line, ref, auto, placeholder) => (
    <div class="fld">
      <label for={`about-${field}`}>{label}</label>
      <input id={`about-${field}`} ref={ref} type={type} value={typed[field]} autocomplete={auto} data-about={field} placeholder={placeholder}
        aria-describedby={`about-${field}-line`} aria-invalid={said[field] ? "true" : undefined}
        onInput={(e) => onInput(field, e.currentTarget.value)}
        onBlur={() => save(field)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); save(field); } }} />
      <small id={`about-${field}-line`}>{line}</small>
      <p class="fld-bad" role="alert">{said[field]}</p>
    </div>
  );
  return (
    <fieldset class="styles about" data-about-you>
      <legend>About you</legend>
      {box("name", "Your name", "text", "Shown at the top of your menu, as the name on each change you make, and on Excel exports and publications. Optional.", name, "name")}
      {box("alias", ALIAS_WORDS.label, "text", ALIAS_WORDS.help, alias, "nickname", ALIAS_WORDS.placeholder)}
      {box("email", "Your email", "email", "Optional. Used only to tell which email addresses are your own. Nothing here sends email.", email, "email")}
    </fieldset>
  );
}

const KEYS_ON = "Single-key shortcuts are on";
const KEYS_OFF = "Single-key shortcuts are off";

// The switch changes at once; the toast says the new state and its Undo sets it back (row 849). The button is never disabled, so focus stays on it.
function flipKeys() {
  const now = !singleKeys.value;
  setSingleKeys(now);
  announceSwitch(now ? KEYS_ON : KEYS_OFF, () => { setSingleKeys(!now); return { ok: true }; }, now ? KEYS_OFF : KEYS_ON);
}

// Row 902: the Appearance control is a radio group: one stop in the Tab order (the chosen one); the arrows move to the next or previous
// choice and pick it, wrapping round; Home and End pick the first and last. Enter and Space pick the focused button as a click does.
function pickByArrow(e) {
  if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;     // browser shortcuts (Cmd+arrow and the like) are not ours
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
  if (!step && e.key !== "Home" && e.key !== "End") return;
  e.preventDefault();
  const at = APPEARANCES.findIndex(([id]) => id === appearance.value), last = APPEARANCES.length - 1;
  const next = APPEARANCES[e.key === "Home" ? 0 : e.key === "End" ? last : (Math.max(at, 0) + step + APPEARANCES.length) % APPEARANCES.length][0];
  setAppearance(next);
  const btn = e.currentTarget.querySelector(`[data-theme-pick="${next}"]`);
  if (btn) btn.focus();
}

export function Personal() {
  useEffect(() => leaveSwitch, []);
  return (
    <section class="frame personal" id="personal" aria-labelledby="personal-h">
      <h2 id="personal-h" tabIndex={-1}>Personal</h2>
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
        <div class="seg" role="radiogroup" aria-label="Appearance" onKeyDown={pickByArrow}>
          {APPEARANCES.map(([id, name]) => (
            <button key={id} type="button" role="radio" data-theme-pick={id} aria-checked={appearance.value === id ? "true" : "false"} tabIndex={appearance.value === id ? 0 : -1} onClick={() => setAppearance(id)}>{name}</button>
          ))}
        </div>
        <p class="muted appearance-line" data-appearance-line aria-live="polite">{(APPEARANCES.find(([id]) => id === appearance.value) || APPEARANCES[0])[2]}</p>
      </fieldset>
      <AboutYou />
      <fieldset class="styles keys">
        <legend>Keys</legend>
        <label class="sw key-sw"><button type="button" class="switch" role="switch" aria-label="Single-key shortcuts" aria-checked={singleKeys.value ? "true" : "false"} aria-describedby="keys-line"
          onClick={flipKeys}></button>
          <span><b>Single-key shortcuts</b><small id="keys-line">Letter keys such as V and E work alone on the page. Turn them off if you type by voice or hit keys by accident. Arrows, Enter, Esc and Ctrl or Cmd combinations still work.</small></span></label>
      </fieldset>
    </section>
  );
}
