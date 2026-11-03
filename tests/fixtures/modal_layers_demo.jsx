// Test-only (tests/test_modal_layers.py): the modal-layer helper (#425) on a bare page shaped like the real one: #app holds the top
// bar, #main, the peek, the ask panel, a palette, the toast region with a toast that has buttons, and a host for the dialog. The
// Draft email editor is mounted the way the right-click menu's host mounts it (a scrim in #app, inert set when it opens, undone when
// it closes), because no screen on main opens it yet. Never part of clark's bundle.
import { render } from "preact";
import { useEffect, useRef } from "preact/hooks";
import { inertBehind } from "@src/edit/modalLayers.js";
import { DraftEmail } from "@src/components/DraftEmail.jsx";

const T = { closed: 0, releases: [] };
window.T = T;

T.build = () => {
  document.getElementById("root").innerHTML =
    '<div id="app"><header class="top"><button id="top-b" type="button">Top</button></header>' +
    '<main id="main"><button id="main-b" type="button">Main</button></main>' +
    '<aside id="peek"><button id="peek-b" type="button">Peek</button></aside>' +
    '<aside id="ask-panel"><input id="ask-i"></aside>' +
    '<div id="help-layer"><button id="help-b" type="button">Help</button></div>' +
    '<div class="toasts" role="status" aria-live="polite"><div class="toast"><button id="undo-b" type="button">Undo</button></div></div>' +
    '<div id="host"></div></div>';
};

// What a dialog host does: its own element is never held; the rest of the page is, until release.
T.hold = (id) => { const r = inertBehind(document.getElementById(id)); T.releases.push(r); return T.releases.length - 1; };
T.release = (n) => T.releases[n]();

function Host({ onClose }) {
  const root = useRef(null);
  useEffect(() => {
    const first = root.current && root.current.querySelector("input, button");
    if (first) first.focus();
    return inertBehind(root.current);
  }, []);
  return <div class="ad-scrim" id="draft-scrim" ref={root}>{onClose ? <DraftEmail items={[]} state={{ mode: "update_request", picked: [] }} draft={null} today="2026-11-02" onClose={onClose} /> : null}</div>;
}

T.openDraft = () => {
  T.opener = document.activeElement;
  render(<Host onClose={() => { T.closed += 1; T.closeDraft(); }} />, document.getElementById("host"));
};
T.closeDraft = () => {
  render(null, document.getElementById("host"));
  if (T.opener && T.opener.isConnected) T.opener.focus();
};
