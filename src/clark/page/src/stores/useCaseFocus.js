// The use case the person has just come back from (the Use cases page's detail leaves its id here). The list focuses that row when
// it draws and clears this, so Back and Esc land where the person was. Plain state, no network, no Edit part: the list may read it.
import { signal } from "@preact/signals";

export const cameBackFrom = signal("");
