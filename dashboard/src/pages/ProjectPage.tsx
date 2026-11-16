import { useCallback } from "react";
import { Link, useParams } from "react-router";
import { api, type ProjectInFull } from "../api";
import { PageHeader } from "../components/PageHeader";
import { PayrollUpload } from "../components/PayrollUpload";
import { StateMessage } from "../components/StateMessage";
import { date } from "../format";
import { PROJECTS } from "../paths";
import { useLoad } from "../useLoad";

export function ProjectPage() {
  const { projectId = "" } = useParams();
  const load = useCallback(() => api.getProject(projectId), [projectId]);
  const { data: project, error } = useLoad(load);
  const eyebrow = (
    <>
      <Link to={PROJECTS}>Projects</Link>{" "}
      <span className="mono">/ {projectId}</span>
    </>
  );

  if (!project)
    return (
      <>
        <PageHeader eyebrow={eyebrow} title={projectId} />
        <StateMessage
          error={error}
          notFound="Project not found. Choose one from the projects."
        />
      </>
    );

  return (
    <>
      <PageHeader
        eyebrow={eyebrow}
        title={project.name}
        lead={`${project.location}, ${project.county} County`}
      />
      <div className="column">
        <ProjectDetails project={project} />
        <Subcontractors project={project} />
        <PayrollUpload key={project.project_id} project={project} />
      </div>
    </>
  );
}

function ProjectDetails({ project }: Readonly<{ project: ProjectInFull }>) {
  return (
    <section className="panel" aria-labelledby="project-title">
      <h2 id="project-title">Project</h2>
      <dl className="facts">
        <div>
          <dt>Public body</dt>
          <dd>{project.public_body}</dd>
        </div>
        <div>
          <dt>Contract</dt>
          <dd className="mono">{project.contract_no}</dd>
        </div>
        <div>
          <dt>Awarded</dt>
          <dd>{date(project.award_date)}</dd>
        </div>
        <div>
          <dt>County</dt>
          <dd>{project.county}</dd>
        </div>
      </dl>
    </section>
  );
}

function Subcontractors({ project }: Readonly<{ project: ProjectInFull }>) {
  return (
    <section className="panel" aria-labelledby="subcontractors-title">
      <h2 id="subcontractors-title">Subcontractors</h2>
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Subcontractor</th>
              <th>Id</th>
              <th>FEIN</th>
              <th>Registration</th>
              <th>First week ending</th>
              <th>Last week ending</th>
            </tr>
          </thead>
          <tbody>
            {project.subcontractors.map((engagement) => (
              <tr key={engagement.subcontractor_id}>
                <td>{engagement.legal_name}</td>
                <td className="mono nowrap">{engagement.subcontractor_id}</td>
                <td className="mono nowrap">{engagement.fein}</td>
                <td className="mono nowrap">{engagement.registration_no}</td>
                <td className="nowrap">{date(engagement.first_week_ending)}</td>
                <td className="nowrap">{date(engagement.last_week_ending)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
