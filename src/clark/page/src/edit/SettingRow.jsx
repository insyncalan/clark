// The one setting row (row 1115, S1): the name and one help line at the left, the control at the right, a thin rule between two rows.
// It only lays a setting out; what the control does stays with the card. The name is the control's label (for = id), the help line is
// the control's description (aria-describedby = help id), and a refusal line (role alert) stands under the help line when the card has one.
// Extra attributes (a data-... hook the page or a test reads) go on the row itself. Edit parts only.
export function SettingRow({ id, name, help, helpId, bad, children, ...rest }) {
  return (
    <div class="set-row" {...rest}>
      <div class="set-row-text">
        <label for={id}>{name}</label>
        {help ? <small id={helpId}>{help}</small> : null}
        {bad ? bad : null}
      </div>
      <div class="set-row-ctl">{children}</div>
    </div>
  );
}
