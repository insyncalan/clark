// The report's cover band (A-D1), shared by the Dashboard and, later, the Gantt page (#928): the title, then "Weekly report", the week
// ending and "for <client>". It takes what it shows as props and draws nothing else, so every page that uses it looks the same.
// `lines` is the words after "Weekly report" (logic/cover.js coverLine); a part with nothing to show is already left out of it.
// `kind` is the line's first words (default "Weekly report"); `children` come under the line, inside the band (the Published reports page's intro).
export function Cover({ title, lines, kind = "Weekly report", children }) {
  return (
    <header class="cover" id="cover">
      <h1>{title}</h1>
      <p class="cover-line"><b class="cover-kind">{kind}</b>{(lines || []).map((t) => <span key={t}>{t}</span>)}</p>
      {children}
    </header>
  );
}
