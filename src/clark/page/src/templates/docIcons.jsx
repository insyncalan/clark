// Documents and links (item 1194): the page-style type icon (a white page, its folded corner, a small drawing, a coloured label band;
// drawn here, not Microsoft's logos) and the icons of Open and Download. The colours and drawings are the approved mockup's.
const COLOURS = { PDF: "#E8410C", DOC: "#1F5FBF", XLS: "#1E9B4B", PPT: "#E8601C", JPG: "#6B46C1", PNG: "#E0358B", TXT: "#F2A400", URL: "#5B47D8", MAIL: "#0E7C86", FILE: "#5A6B77" };
const LINES = (c) => <path d="M12 12h14M12 17h16M12 22h10" stroke={c} />;
const GLYPHS = {
  PDF: LINES(COLOURS.PDF), DOC: LINES(COLOURS.DOC), FILE: LINES(COLOURS.FILE),
  XLS: <><rect x="11" y="11" width="18" height="14" stroke={COLOURS.XLS} /><path d="M11 16h18M11 21h18M17 11v14M23 11v14" stroke={COLOURS.XLS} /></>,
  PPT: <><path d="M12 12h16M20 12v13M14 25h12" stroke={COLOURS.PPT} /><rect x="13" y="12" width="14" height="8" stroke={COLOURS.PPT} /></>,
  JPG: <><rect x="11" y="11" width="18" height="14" stroke={COLOURS.JPG} /><circle cx="16" cy="16" r="1.6" stroke={COLOURS.JPG} /><path d="M11 24l6-5 4 3 4-4 4 4" stroke={COLOURS.JPG} /></>,
  PNG: <path d="M11 11h6v5h-6zM23 11h6v5h-6zM17 16h6v5h-6zM11 21h6v5h-6zM23 21h6v5h-6z" fill={COLOURS.PNG} stroke="none" />,
  TXT: <path d="M13 11h14v14H13zM16 15h8M16 19h8" stroke={COLOURS.TXT} />,
  URL: <g transform="translate(8.5 7) scale(.95)" stroke={COLOURS.URL}><path d="M10 14a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1M14 10a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1" transform="scale(.75) translate(-2 -1)" /></g>,
  MAIL: <><rect x="11" y="11" width="18" height="13" rx="1.5" stroke={COLOURS.MAIL} /><path d="M11 13l9 6 9-6" stroke={COLOURS.MAIL} /></>,
};
const INK = "#0E2430";

// The icon for a label (PDF DOC XLS PPT JPG PNG TXT URL MAIL, else FILE): 41px tall, the height of a row's two text lines.
export function PageIcon({ label }) {
  const key = GLYPHS[label] ? label : "FILE", colour = COLOURS[key];
  return (
    <span class="tpl-badge tpl-page">
      <svg viewBox="0 0 40 48" width="34" height="41" aria-hidden="true" focusable="false">
        <path d="M4 2h22l10 10v34H4z" fill="#fff" stroke={INK} stroke-width="2.2" stroke-linejoin="round" />
        <path d="M26 2v10h10" fill="none" stroke={INK} stroke-width="2.2" stroke-linejoin="round" />
        <g fill="none" stroke-width="2" stroke-linecap="round">{GLYPHS[key]}</g>
        <path d="M5.1 31h29.8v14.9H5.1z" fill={colour} />
        <text x="20" y="42" text-anchor="middle" font-family="system-ui, sans-serif" font-weight="800" font-size={label.length > 3 ? 8 : 9.5} fill="#fff">{label}</text>
      </svg>
    </span>
  );
}

const PATHS = { open: "M14 4h6v6M20 4l-9 9M18 14v5H5V6h5", download: "M12 4v11M7 11l5 5 5-5M5 20h14", trash: "M5 7h14M9 7V5h6v2M7 7l1 12h8l1-12" };
export const ActIcon = ({ which }) => <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d={PATHS[which]} /></svg>;
