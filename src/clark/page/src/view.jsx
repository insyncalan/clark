// The published page's entry (#65): the same components with no Edit parts, and no api.js or stores/changes.js, so the file has
// no way to change anything and no mention of the routes that do.
import { boot } from "./boot.jsx";
import { printWhenAsked } from "./stores/print.js";
import { startLook } from "./stores/reader.js";

startLook();       // the reader's own light or dark choice, from their browser (issue 713)
boot(null);
printWhenAsked();      // a published file prints its tabs one after another, and opens the print box when its address asks (item 438)
