// The published page's entry (#65): the same components with no Edit parts, and no api.js or stores/changes.js, so the file has
// no way to change anything and no mention of the routes that do.
import { boot } from "./boot.jsx";
import { printWhenAsked } from "./stores/print.js";

boot(null);
printWhenAsked();      // a published file prints its tabs one after another, and opens the print box when its address asks (#438)
