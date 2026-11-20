// Start the page. main.jsx (served by clark) passes the Edit parts; view.jsx (the published file) passes none.
import { render } from "preact";
import { load } from "./stores/report.js";
import { App } from "./components/App.jsx";
import { keepChoices } from "./stores/clientMemory.js";

const wantsEditor = () => { try { return new URLSearchParams(location.search).get("slash-editor") === "1" && !!document.getElementById("theme"); } catch (e) { return false; } };

export function boot(tools) {
  // Row 1295: the slash commands editor is a page of its own, opened in a new tab (Classic only). It holds the token in the page and needs no report data,
  // so none of the app's keys, panel or data read start here.
  if (tools && tools.SlashEditor && wantsEditor()) {
    render(<tools.SlashEditor />, document.getElementById("app"));
    document.documentElement.dataset.ready = "1";
    return;
  }
  if (tools && tools.help) tools.help.installKeys();
  if (!tools) keepChoices();                 // a published file remembers the client's choices in their own browser (#69)
  if (tools && tools.pageErrors) tools.pageErrors();        // page faults reach the log through the server (#110); a published file has none
  if (tools && tools.askPanel) tools.askPanel.installKeys();
  if (tools && tools.modeKeys) tools.modeKeys.install();      // V and E, and Cmd+Option+S for Settings (keys.js): heard from the start, not when the switch mounts (item 665)
  render(<App tools={tools} />, document.getElementById("app"));
  document.documentElement.dataset.ready = "1";
  // The server puts this run's token in a data block after this script, and a published file (#39) has its data in one: read
  // whichever is there once the whole page is parsed.
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load); else load();
}
