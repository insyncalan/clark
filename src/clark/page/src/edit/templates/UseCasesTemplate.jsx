// The Use Cases section's Edit part (item 1191), store type "usecases": the summary with its editing in place (the status, the
// commitment, the headline, the name, the eye, the standing and the next steps), the same tools.ucEdit parts as before. The Add control
// is its Head part, which Section.jsx draws in the section's header through tools.templateHead.
import { UseCases } from "../../components/UseCases.jsx";

export function Edit({ tools }) {
  return <UseCases tools={tools} />;
}

// The header hook: the Add control, drawn in the section's header.
export function Head({ tools }) {
  return tools.ucEdit ? <tools.ucEdit.Add /> : null;
}
