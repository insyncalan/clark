import { boot } from "./boot.jsx";
import { EDIT } from "./edit/index.js";
import { install } from "./testhook.js";

install(EDIT);
import "./lineInstall.js";   // the filter line: the app's only (see lineInstall.js)
import "./tipOff.js";   // row 774: Esc hides a showing tooltip
boot(EDIT);
