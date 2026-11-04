// The banner over the Dashboard shown as at a day (item 349): the item 125 design note's past-view banner (the prototype's .pv-banner), in
// the "as at that date" form. It stays at the top, says the day and that the page is rebuilt from the change history and read only,
// and has the one way back: Back to now, this week's Dashboard. A published file never shows it (it is never rebuilt).
import { rebuilt, backToNow } from "../stores/report.js";
import * as L from "../logic/asAt.js";

export function AsAtBanner() {
  if (!rebuilt.value) return null;
  return (
    <div class="pv-banner" id="as-at-banner" role="status">
      <p><b>{L.say(rebuilt.value)}</b> <button type="button" class="link" id="as-at-back" onClick={backToNow}>{L.BACK}</button><br /><small>{L.SMALL}</small></p>
    </div>
  );
}
