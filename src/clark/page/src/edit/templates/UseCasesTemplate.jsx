// The Use Cases section's Edit part (item 1191), store type "usecases": the summary with its editing in place (the status, the
// commitment, the headline, the name, the eye, the standing and the next steps), the same tools.ucEdit parts as before. The Add control
// stays in the section's header (Section.jsx), as it was.
import { UseCases } from "../../components/UseCases.jsx";

export function Edit({ tools }) {
  return <UseCases tools={tools} />;
}
