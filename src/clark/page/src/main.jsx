import "./stores/prefsSync.js";   // row 1535: first, so the preferences kept in the data folder are in the browser's store before anything reads it
import { boot } from "./boot.jsx";
import { EDIT } from "./edit/index.js";
import { startApp } from "./app.js";

import "./lineInstall.js";   // the filter line: the app's only (see lineInstall.js)
import "./tipOff.js";   // row 774: Esc hides a showing tooltip
boot(EDIT);
// The live page only: it needs the token in the page, which a published file does not have. The server puts the token's data
// block after this script, so wait until the whole page is parsed (as boot.jsx does).
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startApp); else startApp();
