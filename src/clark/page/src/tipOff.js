// Row 774: Esc hides a showing tooltip (shell.css, [data-tip]) until the pointer moves or another key is pressed. The tip also hides
// on pointer leave and blur by itself (it shows on :hover and :focus-visible only) and while a button's menu is open (aria-expanded).
const root = document.documentElement;
document.addEventListener("keydown", (e) => { if (e.key === "Escape") root.setAttribute("data-tip-off", "1"); else root.removeAttribute("data-tip-off"); }, true);
document.addEventListener("pointermove", () => root.removeAttribute("data-tip-off"), true);
