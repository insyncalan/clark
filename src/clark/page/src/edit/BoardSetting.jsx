// Settings › Reports (row 1533): whether a published report offers the client the Work items board (read only). One tick, saved at once as one
// change with Undo (project-update, like the Gantt ticks). Default off (ruled 23-11-2026: "board view as a switch, default off"). Edit part only.
import { data } from "../stores/report.js";
import { change } from "../stores/changes.js";
import { SettingRow, focusControl } from "./SettingRow.jsx";
import { defaultOf } from "./settingsDefaults.js";

export const BOARD_FIELD = "show_board_client";
const on = (v) => v === 1 || v === true || v === "1";
const request = (value) => ({ kind: "projects", op: "update", changes: { [BOARD_FIELD]: value ? 1 : 0 }, place: "menu" });
const SAID = ["The board will be offered in the client's report.", "The board will not be offered in the client's report."];

export function BoardSetting() {
  const p = data.value && data.value.project, now = !!p && on(p[BOARD_FIELD]);
  const tick = async (e) => {
    const next = e.currentTarget.checked;
    if (next === now) return;
    await change(request(next), next ? SAID[0] : SAID[1]);      // the page reads the project again: a refused tick is drawn as it was
  };
  const reset = async () => {
    await change(request(defaultOf("board-client")), SAID[1], { focus: "#board-client" });
    focusControl("board-client");
  };
  return (
    <section class="frame setting" id="board-setting" aria-labelledby="board-setting-h">
      <h2 id="board-setting-h" tabIndex={-1}>Work items board</h2>
      <p class="muted">Whether a published report lets the client switch the Work items page from the list to the board. The client can look and open a card, never change anything.</p>
      <SettingRow id="board-client" name="Show the board to clients" data-board-client changed={now !== defaultOf("board-client")} onReset={reset}
        help="The list stays the first view. A printed or saved page is always the list.">
        <input type="checkbox" id="board-client" checked={now} onChange={tick} />
      </SettingRow>
    </section>
  );
}
