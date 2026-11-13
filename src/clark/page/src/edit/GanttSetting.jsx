// Settings › Gantt (#926): who sees the project's Gantt tab, and what the tab is called. Two ticks and a name, each saved on its own as one
// change with Undo (project-update, like Freshness). The wire format is in gantt/ganttTab.js. Edit parts only. Whether a client's file
// carries the tab is decided when it is published (the client tick, and at least one line shown to the client).
import { useRef, useState } from "preact/hooks";
import { data } from "../stores/report.js";
import { change } from "../stores/changes.js";
import { editorOn, clientOn, tabName, nameOf, requestFor, NAME_MAX } from "../gantt/ganttTab.js";
import { NAME_REFUSED } from "./ganttWords.js";
import { SettingRow } from "./SettingRow.jsx";
import { defaultOf } from "./settingsDefaults.js";

export function GanttSetting() {
  const p = data.value && data.value.project, now = tabName(p);
  const [typed, setTyped] = useState(null);          // null: the box shows the name in use
  const [said, setSaid] = useState("");
  const busy = useRef(false);
  const shown = typed === null ? now : typed;
  const tick = (which, was, words) => async (e) => {
    const next = e.currentTarget.checked;
    if (next === was) return;
    await change(requestFor(which, next), next ? words[0] : words[1]);      // the page reads the project again: a refused tick is drawn as it was
  };
  const save = async () => {
    if (typed === null || busy.current) return;
    const n = nameOf(typed);
    if (n === null) { setTyped(null); setSaid(NAME_REFUSED); return; }
    setSaid("");
    if (n === now) { setTyped(null); return; }
    busy.current = true;
    await change(requestFor("name", n), `Gantt tab renamed to ${n}.`);
    busy.current = false;
    setTyped(null);
  };
  const resetTick = (which, id, words) => () => change(requestFor(which, defaultOf(id)), words);
  const resetName = () => change(requestFor("name", defaultOf("gantt-name")), `Gantt tab renamed to ${defaultOf("gantt-name")}.`);
  return (
    <section class="frame setting" id="gantt-setting" aria-labelledby="gantt-setting-h">
      <h2 id="gantt-setting-h" tabIndex={-1}>Gantt</h2>
      <p class="muted">Whether this project has a Gantt tab, and who sees it. The client sees only the lines you have put on the client view.</p>
      <SettingRow id="gantt-editor" name="Show the Gantt to me" data-gantt-editor
        changed={editorOn(p) !== defaultOf("gantt-editor")} onReset={resetTick("editor", "gantt-editor", "The Gantt tab is off for you.")}>
        <input type="checkbox" id="gantt-editor" checked={editorOn(p)} onChange={tick("editor", editorOn(p), ["The Gantt tab is on for you.", "The Gantt tab is off for you."])} />
      </SettingRow>
      <SettingRow id="gantt-client" name="Show the Gantt to the client" data-gantt-client
        changed={clientOn(p) !== defaultOf("gantt-client")} onReset={resetTick("client", "gantt-client", "The Gantt will not be in the client's report.")}
        help="It appears in a published report only when at least one line is shown to the client.">
        <input type="checkbox" id="gantt-client" checked={clientOn(p)} onChange={tick("client", clientOn(p), ["The Gantt will be in the client's report.", "The Gantt will not be in the client's report."])} />
      </SettingRow>
      <SettingRow id="gantt-name" name="Tab name" helpId="gantt-name-line" data-gantt-name changed={now !== defaultOf("gantt-name")} onReset={resetName}
        help={`Up to ${NAME_MAX} characters. The default is Gantt. You can also click the tab's name while editing the Gantt page.`}
        bad={<p class="fld-bad" role="alert" data-gantt-name-bad>{said}</p>}>
        <input id="gantt-name" type="text" value={shown} maxLength={NAME_MAX + 20} aria-describedby="gantt-name-line" aria-invalid={said ? "true" : undefined}
          onInput={(e) => setTyped(e.currentTarget.value)} onBlur={save}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); save(); } else if (e.key === "Escape") { setTyped(null); setSaid(""); } }} />
      </SettingRow>
    </section>
  );
}
