import { boot } from "./boot.jsx";
import { EDIT } from "./edit/index.js";
import { startApp } from "./app.js";

import "./lineInstall.js";   // the filter line: the app's only (see lineInstall.js)
import "./tipOff.js";   // row 774: Esc hides a showing tooltip
boot(EDIT);
// The live page only: it needs the token in the page, which a published file does not have. The server puts the token's data
// block before this script (row 1604), and the wait for the whole page stays as boot.jsx has it.
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startApp); else startApp();
