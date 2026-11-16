import { api } from "../api";
import { PageHeader } from "../components/PageHeader";
import { ProjectLink } from "../components/ProjectLink";
import { StateMessage } from "../components/StateMessage";
import { date } from "../format";
import { useLoad } from "../useLoad";

export function ProjectsPage() {
  const { data: projects, error } = useLoad(api.listProjects);
  return (
    <>
      <PageHeader
        title="Projects"
        lead="Our public works jobs. Open one to see its subcontractors and upload a payroll."
      />
      <section className="panel" aria-labelledby="projects-title">
        <h2 id="projects-title">Projects</h2>
        {projects ? (
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Project</th>
                  <th>Id</th>
                  <th>County</th>
                  <th>Location</th>
                  <th>Public body</th>
                  <th>Awarded</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project) => (
                  <tr key={project.project_id}>
                    <td>
                      <ProjectLink
                        projectId={project.project_id}
                        name={project.name}
                      />
                    </td>
                    <td className="mono nowrap">{project.project_id}</td>
                    <td>{project.county}</td>
                    <td>{project.location}</td>
                    <td>{project.public_body}</td>
                    <td className="nowrap">{date(project.award_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <StateMessage error={error} />
        )}
      </section>
    </>
  );
}
