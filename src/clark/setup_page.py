"""#836 step 5: the setup page (design-836-setup-mode.md; the words are the owner's approved table, logged on the row).

One plain HTML page with one inline style and one inline script, drawn by the setup server instead of the stand-in. It shows the doctor's
checks, a "Choose a folder" button (only when a folder check needs fixing) and "Check again". Its sentences are in WORDS and LABELS below
and reach the page in a JSON data block (never run, so it needs no hash); the page writes text with textContent only, never markup.

`page_words` is the page version of a doctor line: the doctor's lines are written for Terminal (`python3 -m clark.doctor`, "start clark
again", drag a folder into Terminal), which a page must never say, so the service sends each check's page line beside the doctor's own.
Standard library only; this module imports nothing that reaches the store or publishes.
"""
import json
import re

from clark import doctor, typed

WORDS = {
    "title": "Setting up clark",
    "notice": "clark is being set up. Nothing is saved until the checks below pass.",
    "again": "Check again",
    "choose": "Choose a folder",
    "waiting": "Waiting for you to choose a folder.",
    "open_window": "A folder window is already open.",
    "ready": "Everything clark needs is ready. Opening clark.",
    "fix_one": "1 thing to fix before clark can start. Fix it, then choose Check again.",
    "fix_many": "{n} things to fix before clark can start. Fix each one, then choose Check again.",
    "unknown": ("Some checks can't run on this computer yet, so we can't say whether clark will start. Try starting it; if it won't, "
                "tell the clark team."),
}
LABELS = {kind: label.rstrip(":") for kind, label in doctor.LABELS.items()}

CHOOSE_CHECKS = ("data_folder", "data_not_in_onedrive")       # the checks a folder choice can mend: the page shows "Choose a folder" for these
AGAIN = "choose Check again"


def page_words(check_id, status, words, seen):
    """The page version of one check's line. A line that is right on a page comes back unchanged; one that sends a person to Terminal,
    to a command, or to "start clark again" is said again for a page (approved table, rows 14, 16, 20, 22, 24, 25)."""
    if check_id == "data_folder" and status == doctor.FIX:
        return page_cant_save(seen.tilde(seen.folder()))
    if check_id == "data_not_in_onedrive" and status == doctor.FIX:
        return (f"Your clark data is set to go in {seen.tilde(seen.folder())}, which is inside OneDrive. OneDrive copies files while "
                "they are being written, which damages the data. Choose a folder on this computer that OneDrive doesn't sync. "
                "Backups can still go to OneDrive.")
    if check_id == "browser":
        return ("Chrome is there, so clark opens in Chrome." if status == doctor.READY else
                "Chrome wasn't found, so clark will open in your usual browser. Install Chrome to open clark there.")
    if check_id == "port" and status == doctor.FIX:
        if words.startswith("Another copy of clark"):
            return words.split(" Close that copy,")[0] + f" Close that copy, then {AGAIN}."
        if words.startswith("Nothing was started"):
            return f"Nothing was started: clark is already open, or another program is using the connection it needs. Close it, then {AGAIN}."
    if status == doctor.NOT_CHECKED:
        return words.replace(f"Run {typed.doctor()} again.", "Choose Check again.")
    words = words.replace(f"Run {typed.doctor()} again.", "Choose Check again.")
    words = words.replace(f"run {typed.doctor()} again.", f"{AGAIN}.")
    words = words.replace("Type xcode-select --install in Terminal, then start clark again.", f"Install a newer Python, then {AGAIN}.")
    return words.replace("start clark again.", f"{AGAIN}.")


def page_cant_save(folder_text):
    """The page line for a data folder that can't be saved in (also the reason a chosen folder that is a link, a file or not writable is refused)."""
    return f"Your clark data can't be saved in {folder_text}. Choose a different folder."


STYLE = """
:root { color-scheme: light dark; --bg: #F3F6FC; --surface: #FFFFFF; --text: #0E2430; --muted: #475577; --border: #C4CEE3; --link: #4A37C2;
  --focus: #5B47D8; --on-brand: #FFFFFF; --ready: #006B5E; --ready-bg: #D9F1EC; --fix: #A3301F; --fix-bg: #F6E0DD; --note: #8A5200;
  --note-bg: #FCEFCF; --unknown: #475577; --unknown-bg: #E6EBF6; --size: 15px; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #08232D; --surface: #0E2D38; --text: #E8FAFC; --muted: #A9CBD4; --border: #2B5868; --link: #B7A9FF; --focus: #8F7BFF;
    --on-brand: #04222A; --ready: #5CCBA9; --ready-bg: #0F3A36; --fix: #F08A7C; --fix-bg: #3D1F1B; --note: #F0B84A; --note-bg: #3A2C16;
    --unknown: #A9CBD4; --unknown-bg: #123846; }
}
* { box-sizing: border-box; }
html { background: var(--bg); }
body { margin: 0; background: var(--bg); color: var(--text); font: var(--size)/1.5 system-ui, sans-serif; }
main { max-width: 42rem; margin: 0 auto; padding: 32px 16px 48px; }
h1 { margin: 0 0 8px; font-size: 1.6rem; line-height: 1.25; }
p { margin: 0 0 16px; overflow-wrap: anywhere; }
.notice { color: var(--muted); }
ul { list-style: none; margin: 0 0 16px; padding: 0; display: grid; gap: 8px; }
li { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: baseline; padding: 12px 16px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; }
.label { flex: 0 0 auto; min-width: 7.5rem; font-weight: 700; font-size: .9rem; padding: 2px 10px; border-radius: 999px; text-align: center; }
.words { flex: 1 1 14rem; min-width: 0; overflow-wrap: anywhere; }
li[data-status="ready"] .label { color: var(--ready); background: var(--ready-bg); }
li[data-status="fix"] .label { color: var(--fix); background: var(--fix-bg); }
li[data-status="advice"] .label { color: var(--note); background: var(--note-bg); }
li[data-status="not checked"] .label { color: var(--unknown); background: var(--unknown-bg); }
.line { font-weight: 700; }
.problem { color: var(--fix); font-weight: 700; }
.row { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; }
button { font: inherit; font-weight: 700; min-height: 44px; padding: 8px 20px; border-radius: 8px; border: 2px solid var(--focus);
  background: var(--surface); color: var(--text); cursor: pointer; }
button.main { background: var(--focus); color: var(--on-brand); }
button:disabled { opacity: .6; cursor: default; }
button:focus-visible { outline: 3px solid var(--focus); outline-offset: 3px; }
[hidden] { display: none !important; }
@media (forced-colors: active) { li, button { border: 1px solid CanvasText; } }
"""

SCRIPT = """
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("setup-words").textContent);
  var words = data.words, labels = data.labels;
  var token = "";                     // read once the page is parsed: the server puts the clark-boot block after this script
  var CHOOSE = %(choose_checks)s;
  var list = document.getElementById("checks"), line = document.getElementById("line"), status = document.getElementById("status");
  var problem = document.getElementById("problem"), choose = document.getElementById("choose"), again = document.getElementById("again");
  var busy = false, finishing = false;

  function call(method, path) {
    var opt = { method: method, cache: "no-store", headers: { "X-Clark-Token": token } };
    if (method === "POST") { opt.headers["Content-Type"] = "application/json"; opt.body = "{}"; }
    return fetch(path, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (b) { return { status: r.status, body: b }; });
    });
  }
  function stale(answer) {
    if (answer.status === 403 && answer.body && answer.body.code === "stale") { location.reload(); return true; }
    return false;
  }
  function say(el, text) { el.textContent = text; el.hidden = !text; }

  function summary(report) {
    var fix = 0, unknown = 0;
    report.checks.forEach(function (c) {
      if (c.status === "fix") fix += 1;
      if (c.required && c.status === "not checked") unknown += 1;
    });
    if (report.ready) return words.ready;
    if (fix === 1) return words.fix_one;
    if (fix > 1) return words.fix_many.replace("{n}", String(fix));
    return unknown ? words.unknown : "";
  }

  function render(report) {
    list.textContent = "";
    var needs = false;
    report.checks.forEach(function (c) {
      var li = document.createElement("li"), label = document.createElement("span"), text = document.createElement("span");
      li.setAttribute("data-status", c.status);
      li.setAttribute("data-id", c.id);
      label.className = "label";
      label.textContent = labels[c.status] || "";
      text.className = "words";
      text.textContent = c.page || c.words;
      li.appendChild(label);
      li.appendChild(text);
      list.appendChild(li);
      if (c.status === "fix" && CHOOSE.indexOf(c.id) >= 0) needs = true;
    });
    list.removeAttribute("aria-busy");
    choose.hidden = !needs || report.ready;
    say(line, summary(report));
    document.body.setAttribute("data-state", report.ready ? "ready" : "fix");
    if (report.ready) finish();
  }

  function setBusy(on) {
    busy = on;
    choose.disabled = on || finishing;
    again.disabled = on || finishing;
  }

  function finish() {
    if (finishing) return;
    finishing = true;
    setBusy(false);
    call("POST", "/api/setup/done").then(function (a) {
      if (stale(a)) return;
      if (a.status === 200 && a.body.restart === true) { waitForClark(); return; }
      finishing = false;
      setBusy(false);
      if (a.body && a.body.checks) render({ ready: false, checks: a.body.checks });
      else say(problem, a.body.message || "");
    }).catch(function () { waitForClark(); });
  }

  function waitForClark() {
    document.body.setAttribute("data-state", "done");
    setInterval(function () {
      call("GET", "/api/setup/checks").then(stale).catch(function () {});
    }, 1000);
  }

  function load() {
    if (busy || finishing) return;
    say(problem, "");
    setBusy(true);
    call("GET", "/api/setup/checks").then(function (a) {
      setBusy(false);
      if (stale(a)) return;
      if (a.status === 200 && a.body.checks) render(a.body);
      else say(problem, a.body.message || "");
    }).catch(function () { setBusy(false); });
  }

  choose.addEventListener("click", function () {
    if (busy || finishing) return;
    say(problem, "");
    setBusy(true);
    say(status, words.waiting);
    document.body.setAttribute("data-state", "waiting");
    call("POST", "/api/setup/folder").then(function (a) {
      say(status, "");
      setBusy(false);
      if (stale(a)) return;
      var b = a.body || {};
      if (a.status === 200 && b.chosen === true) { render(b); }
      else if (a.status === 200) { document.body.setAttribute("data-state", "fix"); }
      else {
        document.body.setAttribute("data-state", "refused");
        say(problem, b.code === "busy" ? words.open_window : (b.page || b.message || ""));
      }
      if (!finishing) choose.focus();
    }).catch(function () { say(status, ""); setBusy(false); });
  });
  again.addEventListener("click", load);

  function here() { call("POST", "/api/here").then(stale).catch(function () {}); }
  document.addEventListener("DOMContentLoaded", function () {
    token = JSON.parse(document.getElementById("clark-boot").textContent).token;
    setInterval(here, 10000);
    here();
    load();
  });
})();
""" % {"choose_checks": json.dumps(list(CHOOSE_CHECKS))}


def html():
    """The page, as the server sends it (the server adds this run's token in the clark-boot block)."""
    data = json.dumps({"words": WORDS, "labels": LABELS}).replace("<", "\\u003c")
    w = WORDS
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{w["title"]}</title>
<style>{STYLE}</style></head>
<body data-state="loading">
<main>
<h1>{w["title"]}</h1>
<p class="notice">{w["notice"]}</p>
<ul id="checks" aria-busy="true"></ul>
<p id="line" class="line" role="status" hidden></p>
<p id="status" role="status" hidden></p>
<p id="problem" class="problem" role="alert" hidden></p>
<div class="row">
<button type="button" id="choose" class="main" hidden>{w["choose"]}</button>
<button type="button" id="again">{w["again"]}</button>
</div>
</main>
<script type="application/json" id="setup-words">{data}</script>
<script>{SCRIPT}</script>
</body></html>
"""
