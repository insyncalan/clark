// Test-only (tests/test_feedback_tab.py): the Feedback logic and card on a bare page, never part of clark's bundle.
// T.mount draws the card with a version and a system the test hands in; T.clips records what a copy put on the clipboard.
import { render } from "preact";
import * as logic from "@src/logic/feedback.js";
import { Feedback } from "@src/edit/Feedback.jsx";

const T = { logic, clips: [], refuse: false, asked: 0 };
window.T = T;

T.mount = (version, platform) => {
  document.getElementById("root").innerHTML = '<div id="fb" style="padding:16px"></div>';
  const clip = (text) => {
    if (T.refuse) return Promise.reject(new Error("refused"));
    T.clips.push(text);
    return Promise.resolve();
  };
  const getVersion = () => { T.asked += 1; return Promise.resolve(version); };
  render(<Feedback getVersion={getVersion} platform={platform} clip={clip} />, document.getElementById("fb"));
};
