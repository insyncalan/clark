// The foot of a published page (#437, the prototype's io.js): "Published <date>. Publication N · <date>. View only." The date is
// the day it was published, as the file says it (asAt), shown DD-MM-YYYY. A file with no date still says it is view only.
import { plainDate } from "./picker.js";

export function footerLine(n, asAt) {
  const d = asAt ? plainDate(asAt) : "";
  return d ? `Published ${d}. Publication ${n} · ${d}. View only.` : `Publication ${n}. View only.`;
}
