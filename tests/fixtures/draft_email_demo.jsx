// Test-only (tests/test_draft_email_editor.py): the Draft email editor's logic and component on a bare page, never part of
// clark's bundle. window.T gives the tests the logic; mountEditor draws the component with a draft the test hands in and
// records what its callbacks were given in T.changed, T.sent and T.closed. T.clip records what a copy put on the clipboard.
import { render } from "preact";
import * as logic from "@src/logic/draftEmail.js";
import { DraftEmail } from "@src/components/DraftEmail.jsx";

const T = { logic, changed: [], sent: [], closed: 0, clips: [], refuse: false };
window.T = T;

T.mountEditor = (items, state, draft, today) => {
  const root = document.getElementById("root");
  root.innerHTML = '<div id="de" style="padding:16px"></div>';
  const clip = (payload) => {
    if (T.refuse) return Promise.reject(new Error("refused"));
    T.clips.push(payload);
    return Promise.resolve();
  };
  render(<DraftEmail items={items} state={state} draft={draft} today={today} clip={clip}
    onChange={(s) => T.changed.push(s)} onSent={(e) => T.sent.push(e)} onClose={() => { T.closed += 1; }} />, document.getElementById("de"));
};
