import { boot } from "./boot.jsx";
import { EDIT } from "./edit/index.js";
import { install } from "./testhook.js";

install(EDIT);
import "./lineInstall.js";   // the filter line: the app's only (see lineInstall.js)
boot(EDIT);
