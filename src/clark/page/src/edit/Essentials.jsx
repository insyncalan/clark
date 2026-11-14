// Settings › Essentials (row 1115, S3): the first card of the long scroll and the first chip, holding the eight settings most people come for, each on the
// shared setting row (SettingRow.jsx): Your name, Appearance, Spacing, Motion, Single-key shortcuts, Backups, Publishing folder, Asking on or off.
// The originals stay in their own cards. Each control here is the same control (the same state, the same save), drawn again: its ids and data hooks
// start with "ess-" so the page never holds one twice. Edit parts only (a published file has no Settings).
import { useEffect, useRef, useState } from "preact/hooks";
import { data } from "../stores/report.js";
import { density } from "../stores/density.js";
import { motionOn, setMotion } from "../stores/motionPref.js";
import { profile, loadProfile, setProfile } from "../stores/profile.js";
import { announce } from "./aboutYouToast.js";
import { SettingRow } from "./SettingRow.jsx";
import { DENSITIES, AppearancePick, KeysSwitch, pickDensity } from "./Personal.jsx";
import { CopyFolder } from "./Safety.jsx";
import { listBackups, setCopyFolder } from "./safetyApi.js";
import { LocalFolderPick } from "./ClientFolder.jsx";
import { askOn, askStatus, ASK_OFF_LINE, ASK_CHECKING_LINE, ASK_UNAVAILABLE_LINE } from "./askState.js";
import { useAskFlip } from "./AskSettings.jsx";
import { leaveSwitch } from "./switchToast.js";

// Your name: saved when the box is left or on Enter, as in About you; a refusal stands under the box and the box keeps what was typed.
function NameRow() {
  const [typed, setTyped] = useState(profile.value.name);
  const [said, setSaid] = useState("");
  const dirty = useRef(false), box = useRef(null);
  useEffect(() => { loadProfile(); }, []);
  useEffect(() => { if (!dirty.current) setTyped(profile.value.name); }, [profile.value.name]);
  async function save() {
    if (!dirty.current) return;
    const sent = box.current ? box.current.value : typed;      // the box as it is now, not as it was last drawn
    const r = await setProfile(sent, undefined, undefined);
    if (!r.newest) return;
    if (r.ok) {
      dirty.current = false;
      setTyped(r.name);
      setSaid("");
      announce(r, (v) => setTyped(v.name));
    } else setSaid(r.message || "");
  }
  return (
    <SettingRow id="ess-name" name="Your name" bad={said ? <small class="fld-bad" id="ess-name-bad" role="alert">{said}</small> : null}>
      <input id="ess-name" ref={box} type="text" value={typed} autocomplete="name" aria-invalid={said ? "true" : undefined} aria-describedby={said ? "ess-name-bad" : undefined}
        onInput={(e) => { dirty.current = true; setTyped(e.currentTarget.value); }} onBlur={save} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); save(); } }} />
    </SettingRow>
  );
}

function SpacingRow() {
  return (
    <SettingRow id="ess-spacing-first" name="Spacing">
      <div class="seg" role="radiogroup" aria-label="Spacing" data-ess-density>
        {DENSITIES.map(([id, name], i) => (
          <button key={id} type="button" role="radio" id={i === 0 ? "ess-spacing-first" : undefined} data-ess-density-pick={id} aria-checked={density.value === id ? "true" : "false"} onClick={() => pickDensity(id)}>{name}</button>
        ))}
      </div>
    </SettingRow>
  );
}

function MotionRow() {
  return (
    <SettingRow id="ess-motion" name="Motion">
      <button type="button" id="ess-motion" class="switch" role="switch" data-ess-motion aria-checked={motionOn.value ? "true" : "false"} onClick={() => setMotion(!motionOn.value)}></button>
    </SettingRow>
  );
}

// Backups: the copy-folder box, with the backups' own status line as the help line (the server's words).
function BackupsRow() {
  const [list, setList] = useState(null);
  useEffect(() => {
    let live = true;
    listBackups().then((r) => { if (live && r.status === 200 && r.body && r.body.ok === true && Array.isArray(r.body.backups)) setList(r.body); });
    return () => { live = false; };
  }, []);
  if (!list) return <SettingRow id="ess-safety-copy-box" name="Backups"><span class="muted" /></SettingRow>;
  return (
    <SettingRow id="ess-safety-copy-box" name="Backups" help={list.status} helpId="ess-backups-line" data-ess-backups>
      <CopyFolder list={list} api={{ setCopyFolder }} saved={(folder) => setList((l) => ({ ...l, copy_folder: folder, copy_warning: null }))} row />
    </SettingRow>
  );
}

function AskRow() {
  const on = askOn.value, status = askStatus.value;
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const { switchRef, flip } = useAskFlip(on, busy, setBusy, setMsg);
  useEffect(() => leaveSwitch, []);      // the Asking card reads the switch each time Settings opens; this row shows the same state
  const bad = msg && msg.text ? <small class={msg.kind === "error" ? "fld-bad" : ""} role={msg.kind === "error" ? "alert" : "status"}>{msg.text}</small> : null;
  return (
    <SettingRow id="ess-ask" name="Asking on or off" help={status === "loading" ? ASK_CHECKING_LINE : status === "unavailable" ? ASK_UNAVAILABLE_LINE : on ? "Asking is on." : ASK_OFF_LINE} helpId="ess-ask-line" bad={bad}>
      <button type="button" id="ess-ask" class="btn" ref={switchRef} data-ess-ask aria-pressed={on ? "true" : "false"} aria-describedby="ess-ask-line" disabled={busy || status !== "ready"} onClick={flip}>{on ? "Turn off asking" : "Turn on asking"}</button>
    </SettingRow>
  );
}

export function Essentials() {
  const open = !!data.value;      // the Publishing folder is a project's setting: with no project open its row is left out, as the Publishing card is
  useEffect(() => leaveSwitch, []);
  return (
    <section class="frame setting essentials" id="essentials" aria-labelledby="essentials-h">
      <h2 id="essentials-h" tabIndex={-1}>Essentials</h2>
      <NameRow />
      <SettingRow id="ess-appearance-first" name="Appearance"><AppearancePick pick="data-ess-theme-pick" first="ess-appearance-first" /></SettingRow>
      <SpacingRow />
      <MotionRow />
      <SettingRow id="ess-keys" name="Single-key shortcuts"><KeysSwitch id="ess-keys" describedby="" data-ess-keys /></SettingRow>
      <BackupsRow />
      {open ? <SettingRow id="ess-local-folder" name="Publishing folder"><LocalFolderPick /></SettingRow> : null}
      <AskRow />
    </section>
  );
}
