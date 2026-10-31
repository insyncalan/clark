import { boot } from "./boot.jsx";
import { EDIT } from "./edit/index.js";
import { startApp } from "./app.js";

boot(EDIT);
// The live page only: it needs the token in the page, which a published file does not have. The server puts the token's data
// block after this script, so wait until the whole page is parsed (as boot.jsx does).
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startApp); else startApp();
