// Row 1046: the message that only informs: a database icon, the lead "Database refreshed", a sentence, and Close. No Undo. A teal edge marks
// the kind (shell.css, .toast.informed); it has its own place beside the change toast, and is announced politely when it arrives.
import { informed, informedTimer, dismissInformed } from "../stores/informed.js";
import { holdOn, INFORMED_MS } from "../stores/toastClock.js";
import { Icon } from "../components/Icon.jsx";
import { keepFocus, startHeld } from "./ToastCard.jsx";

export function InformedToast() {
  const t = informed.value;
  return (
    <div class="toasts toasts-informed" role="status" aria-live="polite">
      {t ? (
        <div class="toast informed" key={t.id} data-kind="informed" ref={startHeld(informedTimer)} {...holdOn(informedTimer)}>
          <Icon name="database" cls="toast-ico" />
          <span class="toast-text"><b class="toast-lead">{t.lead}</b>{t.text ? " " + t.text : ""}</span>
          <button type="button" class="toast-btn" data-dismiss aria-label="Dismiss this message" onClick={() => { keepFocus(); dismissInformed(); }}>Close</button>
          <span class="toast-bar" aria-hidden="true" style={`--dur-toast:${INFORMED_MS}ms`} />
        </div>
      ) : null}
    </div>
  );
}
