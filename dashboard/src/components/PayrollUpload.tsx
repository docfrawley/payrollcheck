import { Upload } from "lucide-react";
import { useState } from "react";
import { api, type Case, type ProjectInFull } from "../api";
import { ActionForm } from "./ActionForm";
import { statusLabels } from "../format";
import { CaseLink } from "./CaseLink";

// Uploads a subcontractor's payroll CSV to the project on their behalf, which
// creates its Received case, or reopens the case a correction is for, or
// shows why the app refused it.
export function PayrollUpload({
  project,
}: Readonly<{ project: ProjectInFull }>) {
  const [subcontractorId, setSubcontractorId] = useState(
    project.subcontractors.at(0)?.subcontractor_id ?? "",
  );
  const [file, setFile] = useState<File>();
  const [uploaded, setUploaded] = useState<Case>();

  async function upload() {
    if (!file) return;
    setUploaded(undefined);
    const content = await file.text();
    setUploaded(
      await api.uploadPayroll(
        project.project_id,
        subcontractorId,
        file.name,
        content,
      ),
    );
  }

  return (
    <section className="panel" aria-labelledby="upload-title">
      <h2 id="upload-title">Upload a payroll</h2>
      <p className="muted small">
        A certified payroll in our CSV template, uploaded on the subcontractor's
        behalf. It becomes a Received case for the payroll agent to check.
      </p>
      <ActionForm
        label="Upload"
        icon={<Upload />}
        ready={file !== undefined && subcontractorId !== ""}
        action={upload}
      >
        <label>
          Subcontractor
          <select
            value={subcontractorId}
            onChange={(event) => {
              setSubcontractorId(event.target.value);
            }}
          >
            {project.subcontractors.map((engagement) => (
              <option
                key={engagement.subcontractor_id}
                value={engagement.subcontractor_id}
              >
                {engagement.legal_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Payroll file
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => {
              setFile(event.target.files?.[0]);
            }}
          />
        </label>
      </ActionForm>
      {uploaded && (
        <p role="status">
          Uploaded as <CaseLink caseId={uploaded.case_id} />,{" "}
          {statusLabels[uploaded.status]}.
        </p>
      )}
    </section>
  );
}
