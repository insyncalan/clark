// Placeholder for one use case's own page: its crumb and its name. The full page replaces this file.
import { data, project, openUseCases } from "../stores/report.js";
import { format } from "../router.js";
import { refOf } from "../logic/useCasesList.js";

export function UseCaseDetail({ id }) {
  const u = ((data.value && data.value.use_cases) || []).find((x) => x.id === id);
  if (!u) return null;
  return (
    <section class="frame" id="usecase">
      <p class="crumbs"><a href={format({ view: "usecases", project: project.value })} onClick={(e) => { e.preventDefault(); openUseCases(); }}>Use cases</a> › {refOf(u) || "Use case"}</p>
      <h1>{u.title}</h1>
    </section>
  );
}
