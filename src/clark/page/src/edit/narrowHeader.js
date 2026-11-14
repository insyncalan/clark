// Item 1177: at 900 px and narrower the editor's header drops the search and ask clark buttons; they are the first two entries of the profile menu.
// One signal says which width the window is at, so the header and the menu agree.
import { signal } from "@preact/signals";

const QUERY = "(max-width: 900px)";
const now = () => typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(QUERY).matches;

export const narrowHeader = signal(now());
if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
  const mq = window.matchMedia(QUERY), set = () => { narrowHeader.value = mq.matches; };
  if (mq.addEventListener) mq.addEventListener("change", set); else if (mq.addListener) mq.addListener(set);
}
