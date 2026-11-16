import { Link } from "react-router";
import { projectPage } from "../paths";

// A project's name, linked to its page.
export function ProjectLink({
  projectId,
  name,
}: Readonly<{ projectId: string; name: string }>) {
  return <Link to={projectPage(projectId)}>{name}</Link>;
}
