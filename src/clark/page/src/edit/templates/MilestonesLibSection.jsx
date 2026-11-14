// The Milestones library template (row 1192), store type "milestoneslib": its Edit part. The same block the built-in Milestones section
// draws in Edit (components/MsBlock.jsx with the tools: the eye on each row, the line that brings a left-out milestone back), so the
// milestones are edited in place here as they are there. Given { section, tools }.
import { MsBlock } from "../../components/MsBlock.jsx";

export function Edit({ section, tools }) {
  return <MsBlock place={`sec-${section.id}`} tools={tools} />;
}
